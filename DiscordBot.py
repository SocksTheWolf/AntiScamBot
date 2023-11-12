from Logger import Logger, LogLevel
from BotEnums import BanResult, BanLookup
from Config import Config
from datetime import datetime
import discord
from discord.ext import tasks
from BotDatabase import ScamBotDatabase
import asyncio

__all__ = ["DiscordScamBot"]

ConfigData:Config=Config()

class DiscordScamBot(discord.Client):
    # Channel to send updates as to when someone is banned/unbanned
    AnnouncementChannel = None
    # Channel that serves for notifications on bot activity/errors/warnings
    NotificationChannel = None
    Database:ScamBotDatabase = None
    HasLooped:bool = False
    AsyncTasks = set()

    ### Initialization ###
    def __init__(self, *args, **kwargs):
        self.Database = ScamBotDatabase()
        intents = discord.Intents.none()
        intents.guilds = True
        intents.bans = True
        
        # bring in these intents so we can get an idea of shared servers scamcheck returns.
        # Do note, if these are enabled, the bot will take about 1 min to start up.
        if (ConfigData["ScamCheckShowsSharedServers"]):
            intents.members = True
            intents.presences = True

        super().__init__(intents=intents)
        self.Commands = discord.app_commands.CommandTree(self)
        
    def __del__(self):
        Logger.Log(LogLevel.Notice, "Closing the discord scam bot")
        self.Database.Close()
        
    async def setup_hook(self):
        CommandControlServer=discord.Object(id=ConfigData["ControlServer"])
        if (ConfigData.IsDevelopment()):
            # This copies the global commands over to your guild.
            self.Commands.copy_global_to(guild=CommandControlServer)
        else:
            await self.Commands.sync(guild=CommandControlServer)
            await self.Commands.sync()

        if (ConfigData["RunPeriodicBackups"]):
            self.UpdateBackupInterval()
            self.PeriodicBackup.start()
    
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
    async def BeforeCheck(self):
        # Wait until the bot is all set up before adding in the backup check
        await self.wait_until_ready()

    ### Config Handling ###
    def ProcessConfig(self, ShouldReload:bool):
        if (ShouldReload):
            ConfigData.Load()
                
        if (ConfigData.IsValid("AnnouncementChannel", int)):
            self.AnnouncementChannel = self.get_channel(ConfigData["AnnouncementChannel"])
        if (ConfigData.IsValid("NotificationChannel", int)):
            self.NotificationChannel = self.get_channel(ConfigData["NotificationChannel"])
        
        Logger.Log(LogLevel.Notice, "Bot configs applied")

    ### Command Processing & Utils ###    
    async def PostNotification(self, Message:str):
        try:
            if (self.NotificationChannel is not None):
                await self.NotificationChannel.send(Message)
        except discord.HTTPException as ex:
            Logger.Log(LogLevel.Log, f"WARN: Unable to send message to notification channel {str(ex)}")
    
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
    
    async def LookupUser(self, UserID:int) -> discord.User|None:
        try:
            return await self.fetch_user(UserID)
        except discord.NotFound as ex:
            Logger.Log(LogLevel.Warn, f"UserID {UserID} was not found with error {str(ex)}")
        except discord.HTTPException as httpEx:
            Logger.Log(LogLevel.Warn, f"Failed to fetch user {UserID}, got {str(httpEx)}")
        return None
    
    async def LookupUserInServer(self, Server:discord.Guild, UserId:int) -> discord.Member:
        try:
            MemberResult:discord.Member = await Server.fetch_member(UserId)
            return MemberResult
        except discord.Forbidden:
            Logger.Log(LogLevel.Error, f"Bot does not have access to {Server.name}")
        except discord.HTTPException as ex:
            Logger.Log(LogLevel.Debug, f"Encountered http exception while looking up user {str(ex)}")
        except discord.NotFound:
            Logger.Log(LogLevel.Debug, f"Could not find user {UserId} in {Server.name}")
        return None
    
    async def CreateBanEmbed(self, TargetId:int) -> discord.Embed:
        BanData = self.Database.GetBanInfo(TargetId)
        UserBanned:bool = (BanData is not None)
        User:discord.User = await self.LookupUser(TargetId)
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
    
    def UserHasElevatedPermissions(self, User:discord.Member) -> bool:   
        UserPermissions:discord.Permissions = User.guild_permissions 
        if (UserPermissions.administrator or (UserPermissions.manage_guild and UserPermissions.ban_members)):
            return True
        return False
    
    ### Event Queueing ###
    def AddAsyncTask(self, TaskToComplete):
        try:
            CurrentLoop = asyncio.get_running_loop()
        except RuntimeError:
            return

        NewTask = CurrentLoop.create_task(TaskToComplete)
        self.AsyncTasks.add(NewTask)
        NewTask.add_done_callback(self.AsyncTasks.discard)

    ### Discord Eventing ###
    async def on_ready(self):
        self.ProcessConfig(False)
        # Set status
        if (ConfigData.IsValid("BotActivity", str)):
            activity = None
            if (ConfigData.IsDevelopment()):
                activity = discord.CustomActivity(name=ConfigData["BotActivityDevelopment"])
            else:
                activity = discord.CustomActivity(name=ConfigData["BotActivity"])
            await self.change_presence(status=discord.Status.online, activity=activity)

        # Set logger callbacks for notifications
        if (self.NotificationChannel is not None):
            Logger.SetNotificationCallback(self.PostNotification)

        self.Database.ReconcileServers(self.guilds)

        Logger.Log(LogLevel.Notice, f"Bot has started! Is Development? {ConfigData.IsDevelopment()}")
    
    async def on_guild_join(self, server:discord.Guild):
        self.Database.SetBotActivationForOwner(server.owner_id, [server.id], False)
        OwnerName:str = "Admin"
        if (server.owner is not None):
            OwnerName = server.owner.display_name
        
        Logger.Log(LogLevel.Notice, f"Bot has joined server {server.name}[{server.id}] of owner {OwnerName}[{server.owner_id}]")
        
    async def on_guild_update(self, PriorUpdate:discord.Guild, NewUpdate:discord.Guild):
        NewOwnerId:int = NewUpdate.owner_id
        if (PriorUpdate.owner_id != NewOwnerId):
            self.Database.SetNewServerOwner(NewUpdate.id, NewOwnerId)
            Logger.Log(LogLevel.Notice, f"Detected that the server {PriorUpdate.name}[{NewUpdate.id}] is now owned by {NewOwnerId}")
        
    async def on_guild_remove(self, server:discord.Guild):
        self.Database.RemoveServerEntry(server.id)
        OwnerName:str = "Admin"
        if (server.owner is not None):
            OwnerName = server.owner.display_name
        Logger.Log(LogLevel.Notice, f"Bot has been removed from server {server.name}[{server.id}] of owner {OwnerName}[{server.owner_id}]")
    
    ### Ban Handling ###
    async def ReprocessBansForServer(self, Server:discord.Guild, LastActions:int=0) -> BanResult:
        ServerInfoStr:str = f"{Server.name}[{Server.id}]"
        BanReturn:BanResult = BanResult.Processed
        Logger.Log(LogLevel.Log, f"Attempting to import ban data to {ServerInfoStr}")
        NumBans:int = 0
        BanQueryResult = self.Database.GetAllBans(LastActions)
        TotalBans:int = len(BanQueryResult)
        ActionsAppliedThisLoop:int = 0
        DoesSleep:bool = ConfigData["UseSleep"]
        for Ban in BanQueryResult:
            if (DoesSleep):
                # Put in sleep functionality on this loop, as it could be heavy
                if (ActionsAppliedThisLoop >= ConfigData["ActionsPerTick"]):
                    await asyncio.sleep(ConfigData["SleepAmount"])
                    ActionsAppliedThisLoop = 0
                else:
                    ActionsAppliedThisLoop += 1

            UserId:int = int(Ban[0])
            UserToBan = discord.Object(UserId)
            BanResponse = await self.PerformActionOnServer(Server, UserToBan, f"User banned by {Ban[1]}", True)
            # See if the ban did go through.
            if (BanResponse[0] == False):
                BanResponseFlag:BanResult = BanResponse[1]
                if (BanResponseFlag == BanResult.LostPermissions):
                    Logger.Log(LogLevel.Error, f"Unable to process ban on user {UserId} for server {ServerInfoStr}")
                    BanReturn = BanResult.LostPermissions
                    break
            else:
                NumBans += 1
        Logger.Log(LogLevel.Notice, f"Processed {NumBans}/{TotalBans} bans for {ServerInfoStr}!")
        return BanReturn
             
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

    async def PerformActionOnServer(self, Server:discord.Guild, User:discord.Member, Reason:str, IsBan:bool) -> (bool, BanResult):
        IsDevelopmentMode:bool = ConfigData.IsDevelopment()
        BanId:int = User.id
        ServerOwnerId:int = Server.owner_id
        ServerInfo:str = f"{Server.name}[{Server.id}]"
        try:
            BanStr:str = "ban"
            if (not IsBan):
                BanStr = "unban"
            
            Logger.Log(LogLevel.Verbose, f"Performing {BanStr} action in {ServerInfo} owned by {ServerOwnerId}")
            if (BanId == ServerOwnerId):
                Logger.Log(LogLevel.Warn, f"{BanStr.title()} of {BanId} dropped for {ServerInfo} as it is the owner!")
                return (False, BanResult.ServerOwner)
            
            # if we are in development mode, we don't do any actions to any other servers.
            if (IsDevelopmentMode == False):
                if (IsBan):
                    await Server.ban(User, reason=Reason)
                else:
                    await Server.unban(User, reason=Reason)
            else:
                Logger.Log(LogLevel.Debug, "Action was dropped as we are currently in development mode")
            return (True, BanResult.Processed)
        except(discord.NotFound):
            if (not IsBan):
                Logger.Log(LogLevel.Verbose, f"User {BanId} is not banned in server")
                return (True, BanResult.NotBanned)
            else:
                Logger.Log(LogLevel.Warn, f"User {BanId} is not a valid user while processing the ban")
                return (False, BanResult.InvalidUser)
        except discord.Forbidden as forbiddenEx:
            Logger.Log(LogLevel.Error, f"We do not have ban/unban permissions in this server {ServerInfo} owned by {ServerOwnerId}! Err: {str(forbiddenEx)}")
            return (False, BanResult.LostPermissions)
        except discord.HTTPException as ex:
            Logger.Log(LogLevel.Warn, f"We encountered an error {(str(ex))} while trying to perform for server {ServerInfo} owned by {ServerOwnerId}!")
        return (False, BanResult.Error)
        
    async def PropagateActionToServers(self, TargetId:int, Sender:discord.Member, IsBan:bool):
        NumServersPerformed:int = 0
        UserToWorkOn = discord.Object(TargetId)
        ScamStr:str = "scammer"
        if (not IsBan):
            ScamStr = "non-scammer"
        
        BanReason=f"Confirmed {ScamStr} by {Sender.name}"
        AllServers = self.Database.GetAllActivatedServers()
        NumServers:int = len(AllServers)
        ActionsAppliedThisLoop:int = 0
        DoesSleep:bool = ConfigData["UseSleep"]
        # Instead of going through all servers it's added to, choose all servers that are activated.
        for ServerData in AllServers:
            if (DoesSleep):
                # Put in sleep functionality on this loop, as it could be heavy
                if (ActionsAppliedThisLoop >= ConfigData["ActionsPerTick"]):
                    await asyncio.sleep(ConfigData["SleepAmount"])
                    ActionsAppliedThisLoop = 0
                else:
                    ActionsAppliedThisLoop += 1
                
            ServerId:int = ServerData[0]
            DiscordServer = self.get_guild(ServerId)
            if (DiscordServer is not None):
                BanResultTuple = await self.PerformActionOnServer(DiscordServer, UserToWorkOn, BanReason, IsBan)
                if (BanResultTuple[0]):
                    NumServersPerformed += 1
                else:
                    ResultFlag = BanResultTuple[1]         
                    if (IsBan):
                        if (ResultFlag == BanResult.InvalidUser):
                            # TODO: This might be a potential fluke
                            break
                        elif (ResultFlag == BanResult.ServerOwner):
                            # TODO: More logging
                            continue
                    # elif (ResultFlag == BanResult.LostPermissions):
                        # TODO: Mark this server as no longer active?
            else:
                # TODO: Potentially remove the server from the list?
                Logger.Log(LogLevel.Warn, f"The server {ServerId} did not respond on a look up, does it still exist?")

        Logger.Log(LogLevel.Notice, f"Action execution on {TargetId} as a {ScamStr} performed in {NumServersPerformed}/{NumServers} servers")
