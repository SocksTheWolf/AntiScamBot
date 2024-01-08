from Logger import Logger, LogLevel
from BotEnums import BanResult, BanLookup
from Config import Config
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
    HasStartedInstances:bool = False
    SubProcess={}

    ### Initialization ###
    def __init__(self, AssignedBotID:int):
        self.ServerHandler = RelayServer(AssignedBotID, self)
        super().__init__(self.ServerHandler.GetFileLocation(), AssignedBotID)
        
    async def setup_hook(self):
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
        
        Logger.Log(LogLevel.Log, "Periodic Bot DB Backup Started...")    
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
    async def InitializeBotRuntime(self):
        await super().InitializeBotRuntime()
        await self.StartAllInstances()       

    ### Subprocess instances ###
    async def StartAllInstances(self, BypassCheck:bool=False, RestartMainClient:bool=False):
        # Prevent us from restarting instances when on_ready may run again.
        if (self.HasStartedInstances and not BypassCheck):
            return
        
        if (RestartMainClient):
            Logger.Log(LogLevel.Log, "Restarting client instance for control bot instance")
            await self.StartInstance(0)
        
        # Spin up all the subinstances of the other bot clients
        AllInstances = Config.GetAllSubTokens()
        for InstanceID in AllInstances:
            await self.StartInstance(int(InstanceID))
            
        self.HasStartedInstances = True
            
    async def StartInstance(self, InstanceID:int):
        RelayFileHandleLocation = self.ServerHandler.GetFileLocation()
        if (InstanceID == 0):
            self.ClientHandler = None
            self.SetupClientConnection(RelayFileHandleLocation)
            self.ClientHandler.SendHello()
            return
        
        # Make sure to exit out of any instances if they're already running for this index
        await self.StopInstanceIfExists(InstanceID)
        
        Logger.Log(LogLevel.Log, f"Spinning up instance #{InstanceID}")
        self.SubProcess[InstanceID] = Process(target=CreateBotProcess, args=(RelayFileHandleLocation, InstanceID))
        self.SubProcess[InstanceID].start()

    async def StopInstanceIfExists(self, InstanceID:int):       
        if (InstanceID in self.SubProcess and self.SubProcess[InstanceID] is not None):
            ExistingProcess:Process = self.SubProcess[InstanceID]
            ExistingProcess.terminate()
            ExistingProcess.close()
            self.SubProcess[InstanceID] = None

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
    
    async def ReprocessBansForInstance(self, InstanceID:int, LastActions:int):
        if (InstanceID == self.BotID):
            await self.ReprocessInstance(LastActions)
        else:
            self.ClientHandler.SendReprocessInstanceBans(InstanceId=InstanceID, InNumToRetry=LastActions)

    async def ReprocessBansForServer(self, ServerId:int, LastActions:int=0) -> BanResult:
        TargetBotId:int = self.Database.GetBotIdForServer(ServerId)
        if (TargetBotId == self.BotID):
            return await self.ReprocessBans(ServerId, LastActions)
        else:
            self.ClientHandler.SendReprocessBans(ServerId, InstanceId=TargetBotId, InNumToRetry=LastActions)
            return BanResult.Processed
        
    async def PropagateActionToServers(self, TargetId:int, Sender:discord.Member, IsBan:bool):
        SenderName:str = Sender.name
        if (IsBan):
            self.ClientHandler.SendBan(TargetId, SenderName)
        else:
            self.ClientHandler.SendUnban(TargetId, SenderName)
            
        await self.ProcessActionOnUser(TargetId, SenderName, IsBan)
        