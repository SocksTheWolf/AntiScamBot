from Logger import Logger, LogLevel
from BotEnums import BanResult, BanLookup
from Config import Config
from datetime import datetime
from BotMain import DiscordBot
from BotConnections import RelayServer
import discord
from discord.ext import tasks
from multiprocessing import Process
from BotSubprocess import CreateBotProcess

__all__ = ["ScamGuard"]

ConfigData:Config=Config()

class ScamGuard(DiscordBot):
    # Channel to send updates as to when someone is banned/unbanned
    AnnouncementChannel = None
    ServerHandler:RelayServer = None
    HasLooped:bool = False
    SubProcess={}

    ### Initialization ###
    def __init__(self, AssignedBotID:int):
        self.ServerHandler = RelayServer(AssignedBotID)
        super().__init__(self.ServerHandler.GetFileLocation(), AssignedBotID)
        self.Commands = discord.app_commands.CommandTree(self)
        
    async def setup_hook(self):
        CommandControlServer=discord.Object(id=ConfigData["ControlServer"])
        if (ConfigData.IsDevelopment()):
            # This copies the global commands over to your guild.
            self.Commands.copy_global_to(guild=CommandControlServer)
            await self.Commands.sync(guild=CommandControlServer)
            await self.Commands.sync()
        else:
            await self.Commands.sync(guild=CommandControlServer)
            await self.Commands.sync()

        if (ConfigData["RunPeriodicBackups"]):
            self.UpdateBackupInterval()
            self.PeriodicBackup.start()
            
        self.HandleListenRelay.start()
        await super().setup_hook()
            
    ### Discord Tasks Handling ###
    @tasks.loop(seconds=0.5)
    async def HandleListenRelay(self):
        await self.ServerHandler.TickRelay()
        
    @HandleListenRelay.before_loop
    async def BeforeListenRelay(self):
        await self.wait_until_ready()
    
    ### Backup handling ###
    def UpdateBackupInterval(self, SetToRetry:bool=False):
        if (SetToRetry == False):
            self.PeriodicBackup.change_interval(minutes=0, hours=ConfigData["RunBackupEveryXHours"])
        else:
            self.PeriodicBackup.change_interval(minutes=5, hours=0)
        
    @tasks.loop(minutes=5)
    async def PeriodicBackup(self):
        # Prevent us from running the backup immediately
        if (not self.HasLooped):
            self.HasLooped = True
            return
        
        # If we have active async tasks in progress, then delay this task until we are free.
        if (len(self.AsyncTasks) > 0):
            Logger.Log(LogLevel.Warn, "There are currently async tasks in progress, will try again in 5 minutes...")
            self.UpdateBackupInterval(SetToRetry=True)
            return
        
        # If we currently have the minutes value set, then we need to make sure we get back onto the right track
        if (self.PeriodicBackup.minutes != 0):
            self.UpdateBackupInterval()
        
        Logger.Log(LogLevel.Notice, "Periodic Bot DB Backup Started...")    
        self.Database.Backup()
        self.Database.CleanupBackups()
        
    @PeriodicBackup.before_loop
    async def BeforeBackup(self):
        # Wait until the bot is all set up before adding in the backup check
        await self.wait_until_ready()

    ### Config Handling ###
    def ProcessConfig(self, ShouldReload:bool):
        super().ProcessConfig(ShouldReload)
        
        if (ConfigData.IsValid("AnnouncementChannel", int)):
            self.AnnouncementChannel = self.get_channel(ConfigData["AnnouncementChannel"])
            
    ### Discord Eventing ###
    async def on_ready(self):
        await super().on_ready()
        
        # Spin up all the subinstances of the other bot clients
        AllInstances = Config.GetAllSubTokens()
        for InstanceID in AllInstances:
            ToNum:int = int(InstanceID)
            Logger.Log(LogLevel.Debug, f"Attempting to load {ToNum}")
            if (ToNum == 0):
                continue
            
            Logger.Log(LogLevel.Log, f"Spinning up instance #{ToNum}")
            self.SubProcess[ToNum] = Process(target=CreateBotProcess, args=(self.ServerHandler.GetFileLocation(), ToNum))
            self.SubProcess[ToNum].start()

    ### Command Processing & Utils ###    
    async def PublishAnnouncement(self, Message:str|discord.Embed):
        if (ConfigData.IsDevelopment()):
            Logger.Log(LogLevel.Notice, "Announcement message was dropped because this instance is in development mode")
            return
        try:
            NewMessage = None
            if (type(Message) == discord.Embed):
                NewMessage = await self.AnnouncementChannel.send(embed=Message)
            else:
                NewMessage = await self.AnnouncementChannel.send(Message)
            if (NewMessage is not None):
                await NewMessage.publish()
            elif (type(Message) == str):
                Logger.Log(LogLevel.Error, f"Could not publish message {str(Message)}! Did not send!")
            else:
                Logger.Log(LogLevel.Error, f"Could not publish message, as it did not send!")
        except discord.HTTPException as ex:
            Logger.Log(LogLevel.Log, f"WARN: Unable to publish message to announcement channel {str(ex)}")
    
    async def LookupUserForBanEmbed(self, UserID:int) -> discord.User|None:
        try:
            return await self.fetch_user(UserID)
        except discord.NotFound as ex:
            Logger.Log(LogLevel.Warn, f"UserID {UserID} was not found with error {str(ex)}")
        except discord.HTTPException as httpEx:
            Logger.Log(LogLevel.Warn, f"Failed to fetch user {UserID}, got {str(httpEx)}")
        return None
    
    async def CreateBanEmbed(self, TargetId:int) -> discord.Embed:
        BanData = self.Database.GetBanInfo(TargetId)
        UserBanned:bool = (BanData is not None)
        User:discord.User = await self.LookupUserForBanEmbed(TargetId)
        HasUserData:bool = (User is not None)
        UserData = discord.Embed(title="User Data")
        if (HasUserData):
            UserData.add_field(name="Name", value=User.display_name)
            UserData.add_field(name="Handle", value=User.mention)
            # This will always be an approximation, plus they may be in servers the bot is not in.
            if (ConfigData["ScamCheckShowsSharedServers"]):
                UserData.add_field(name="Shared Servers", value=f"~{len(User.mutual_guilds)}")
            UserData.add_field(name="Account Created", value=f"{discord.utils.format_dt(User.created_at)}", inline=False)
            UserData.set_thumbnail(url=User.display_avatar.url)
        
        UserData.add_field(name="Banned", value=f"{UserBanned}")
        
        # Figure out who banned them
        if (UserBanned):
            # BannerName, BannerId, Date
            UserData.add_field(name="Banned By", value=f"{BanData[0]}", inline=False)
            # Create a date time format (all of the database timestamps are in iso format)
            DateTime:datetime = datetime.fromisoformat(BanData[2])
            UserData.add_field(name="Banned At", value=f"{discord.utils.format_dt(DateTime)}", inline=False)
            UserData.colour = discord.Colour.red()
        elif (not HasUserData):
            UserData.colour = discord.Colour.dark_orange()
        else:
            UserData.colour = discord.Colour.green()

        UserData.set_footer(text=f"User ID: {TargetId}")
        return UserData

    ### Ban Handling ###            
    async def PrepareBan(self, TargetId:int, Sender:discord.Member) -> BanLookup:        
        DatabaseAction:BanLookup = self.Database.AddBan(TargetId, Sender.name, Sender.id)
        if (DatabaseAction != BanLookup.Good):
            return DatabaseAction
        
        self.AddAsyncTask(self.PropagateActionToServers(TargetId, Sender, True))
        
        # Send a message to the announcement channel
        NewAnnouncement:discord.Embed = await self.CreateBanEmbed(TargetId)
        NewAnnouncement.title="Ban in Progress"
        await self.PublishAnnouncement(NewAnnouncement)
        
        return BanLookup.Banned

    async def PrepareUnban(self, TargetId:int, Sender:discord.Member) -> BanLookup:
        DatabaseAction:BanLookup = self.Database.RemoveBan(TargetId)
        if (DatabaseAction != BanLookup.Good):
            return DatabaseAction
        
        self.AddAsyncTask(self.PropagateActionToServers(TargetId, Sender, False))
        
        # Send a message to the announcement channel
        NewAnnouncement:discord.Embed = await self.CreateBanEmbed(TargetId)
        NewAnnouncement.title = "Unban in Progress"
        await self.PublishAnnouncement(NewAnnouncement)
        
        return BanLookup.Unbanned
    
    async def ReprocessBansForServer(self, ServerId:int, LastActions:int=0) -> BanResult:
        TargetBotId:int = self.Database.GetBotIdForServer(ServerId)
        if (TargetBotId == self.BotID):
            return await self.ReprocessBans(ServerId, LastActions)
        else:
            self.ClientHandler.SendReprocessBans(ServerId, InstanceId=TargetBotId, InNumToRetry=LastActions)
        
    async def PropagateActionToServers(self, TargetId:int, Sender:discord.Member, IsBan:bool):
        SenderName:str = Sender.name
        if (IsBan):
            self.ClientHandler.SendBan(TargetId, SenderName)
        else:
            self.ClientHandler.SendUnban(TargetId, SenderName)
            
        await self.ProcessActionOnUser(TargetId, SenderName, IsBan)
        