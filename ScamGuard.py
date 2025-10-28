# The core main instance of ScamGuard, used as the primary instance. This should have code that only needs to be ran by a single instance
# Such as the host system that shares commands/messages to sub-instances and things like backup.
# It should not handle any recv instructions from ServerHandler except for requests by sub-instances.
from Logger import Logger, LogLevel
from BotEnums import BanResult, BanLookup, ModerationAction
from Config import Config
from BotBase import DiscordBot
from BotConnections import RelayServer
from datetime import datetime, timedelta
import discord, asyncio
from discord.ext import tasks
from multiprocessing import Process
from BotSubprocess import CreateBotProcess

__all__ = ["ScamGuard"]

ConfigData:Config=Config()

class ScamGuard(DiscordBot):
    ServerHandler:RelayServer = None # pyright: ignore[reportAssignmentType]
    HasStartedInstances:bool = False
    SubProcess={}

    ### Initialization ###
    def __init__(self, AssignedBotID:int):
        self.ServerHandler = RelayServer(AssignedBotID, self)
        super().__init__(self.ServerHandler.GetFileLocation(), AssignedBotID)
        
    async def setup_hook(self):
        # TODO: Make a fancy table for this in the future
        if (ConfigData["RunBackupEveryXHours"] > 0):
            self.ConfigBackupInterval()
            self.PeriodicBackup.start()
            
        if (ConfigData["RunIdleCleanupEveryXHours"] > 0):
            self.ConfigIdleInterval()
            self.PeriodicLeave.start()
            
        self.HandleListenRelay.start()
        await super().setup_hook()
            
    ### Discord Tasks Handling ###
    @tasks.loop(seconds=0.5)
    async def HandleListenRelay(self):
        await self.ServerHandler.TickRelay()
        
    @HandleListenRelay.before_loop
    async def BeforeListenRelay(self):
        await self.wait_until_ready()
    
    ### Task Interval Handling ###
    def ConfigBackupInterval(self):
        self.PeriodicBackup.change_interval(minutes=0.0, hours=float(ConfigData["RunBackupEveryXHours"]))

    def ConfigIdleInterval(self):
        self.PeriodicLeave.change_interval(minutes=0.0, hours=float(ConfigData["RunIdleCleanupEveryXHours"]))
        
    def RetryTaskInterval(self, task):
        task.change_interval(minutes=5.0, hours=0.0)
    
    ### Backup handling ###
    # By default, this runs every 5 minutes, however upon loading configurations, this will update the
    # backup interval to the proper settings
    @tasks.loop(minutes=5)
    async def PeriodicBackup(self):
        # If we have active async tasks in progress, then delay this task until we are free.
        if (len(self.AsyncTasks) > 0):
            Logger.Log(LogLevel.Warn, "There are currently async tasks in progress, will try backup again in 5 minutes...")
            self.RetryTaskInterval(self.PeriodicBackup)
            return
        
        # If we currently have the minutes value set, then we need to make sure we get back onto the right track
        if (self.PeriodicBackup.minutes != 0.0):
            self.ConfigBackupInterval()
        
        Logger.Log(LogLevel.Log, "Periodic Bot DB Backup Started...")    
        self.Database.Backup()
        self.Database.CleanupBackups()
        
    @PeriodicBackup.before_loop
    async def BeforeBackup(self):
        # Wait until the bot is all set up before adding in the backup check
        await self.wait_until_ready()
        
    ### Instance Cleanup ###
    @tasks.loop(minutes=5)
    async def PeriodicLeave(self):
        # If we are processing any async tasks, do not clean up the deactivated table
        if (len(self.AsyncTasks) > 0):
            self.RetryTaskInterval(self.PeriodicLeave)
            return
        
        # If the instances code hasn't been able to start, wait for when it's ready again.
        if (not self.HasStartedInstances):
            self.RetryTaskInterval(self.PeriodicLeave)
            return
        
        await self.RunPeriodicLeave(False)
        
    async def RunPeriodicLeave(self, DryRun:bool):
        # If this config is less than or equal to 0, then we don't execute the task
        InactiveInstanceWindow:int = ConfigData["InactiveServerDayWindow"]
        if (InactiveInstanceWindow <= 0):
            return
        
        if (self.PeriodicLeave.minutes != 0.0):
            self.ConfigIdleInterval()

        CurrentTime:datetime = datetime.now() - timedelta(days=float(InactiveInstanceWindow))
        AllDisabledServers = self.Database.GetAllDeactivatedServers()
        Logger.CLog(len(AllDisabledServers) > 0, LogLevel.Notice, f"Attempting to clean up old non-activated servers... Dry run? {DryRun}")
        ServersLeft:int = 0
        for ServerData in AllDisabledServers:
            if (CurrentTime > ServerData.created_at): # type: ignore
                ServerID:int = int(ServerData.discord_server_id)
                if (DryRun or self.LeaveServer(ServerID)):
                    ServersLeft += 1
                    Logger.Log(LogLevel.Verbose, f"Attempting to leave server {ServerID}.")
                    Logger.CLog(DryRun, LogLevel.Log, f"Attempting to leave server {ServerID}.")
                else:
                    Logger.Log(LogLevel.Warn, f"Could not send leave request for server {ServerID}")

                # Attempt to sleep the big scary rate limits away
                if (not DryRun):
                    await asyncio.sleep(1.0)
        
        Logger.CLog(ServersLeft > 0, LogLevel.Notice, f"Server Instance Cleanup Completed, left {ServersLeft} out of {len(AllDisabledServers)}")
        
    @PeriodicLeave.before_loop
    async def BeforeLeaveTask(self):
        # Wait until the bot is all set up before attempting periodic leaves
        await self.wait_until_ready()

    ### Config Handling ###
    def ProcessConfig(self, ShouldReload:bool):
        super().ProcessConfig(ShouldReload)
            
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
        self.SubProcess[InstanceID] = Process(target=CreateBotProcess, args=(RelayFileHandleLocation, InstanceID), name=f'Bot-{InstanceID}')
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
            NewMessage:discord.Message|None = None
            if (self.AnnouncementChannel is None):
                return
            
            if (type(Message) == discord.Embed):
                NewMessage = await self.AnnouncementChannel.send(embed=Message)
            else:
                NewMessage = await self.AnnouncementChannel.send(str(Message))
            if (NewMessage is not None):
                await NewMessage.publish()
            elif (type(Message) == str):
                Logger.Log(LogLevel.Error, f"Could not publish message {str(Message)}! Did not send!")
            else:
                Logger.Log(LogLevel.Error, f"Could not publish message, as it did not send!")
        except discord.HTTPException as ex:
            Logger.Log(LogLevel.Log, f"WARN: Unable to publish message to announcement channel {str(ex)}")

    ### Ban Handling ###
    async def HandleBanAction(self, TargetId:int, Sender:discord.Member|discord.User, Action:ModerationAction, ThreadId:int|None=None) -> BanLookup:
        DatabaseAction:BanLookup
        
        if (Action == ModerationAction.Ban):
            DatabaseAction = self.Database.AddBan(TargetId, Sender.name, Sender.id, ThreadId)
        elif (Action == ModerationAction.Unban):
            DatabaseAction = self.Database.RemoveBan(TargetId)
        else:
            Logger.Log(LogLevel.Error, f"An invalid moderation action was passed to HandleBanAction, {Action}")
            return BanLookup.DBError
        
        if (DatabaseAction != BanLookup.Good):
            return DatabaseAction
        
        self.AddAsyncTask(self.CreateBanAnnouncement(TargetId, Action))
        self.AddAsyncTask(self.PropagateActionToServers(TargetId, Sender, Action))
        
        return DatabaseAction
    
    async def CreateBanAnnouncement(self, TargetId:int, ActionTaken:ModerationAction):
        if ActionTaken is ModerationAction.Ban or ActionTaken is ModerationAction.Unban:
            # Send a message to the announcement channel
            NewAnnouncement:discord.Embed = await self.CreateBanEmbed(TargetId)
            NewAnnouncement.title = f"{str(ActionTaken)} in Progress"
            await self.PublishAnnouncement(NewAnnouncement)
    
    async def ReprocessBansForInstance(self, InstanceID:int, LastActions:int):
        if (InstanceID == self.BotID):
            await self.ReprocessInstance(LastActions)
        else:
            self.ClientHandler.SendReprocessInstanceBans(InstanceId=InstanceID, InNumToRetry=LastActions)

    async def ReprocessBansForServer(self, ServerId:int, LastActions:int=0) -> BanResult:
        TargetBotId:int|None = self.Database.GetBotIdForServer(ServerId)
        if (TargetBotId == self.BotID):
            return await self.ReprocessBans(ServerId, LastActions)
        elif (TargetBotId is None):
            return BanResult.Error
        else:
            self.ClientHandler.SendReprocessBans(ServerId, InstanceId=TargetBotId, InNumToRetry=LastActions)
            return BanResult.Processed
        
    async def PropagateActionToServers(self, TargetId:int, Sender:discord.Member|discord.User, Action:ModerationAction):
        SenderName:str = Sender.name
        if (Action == ModerationAction.Ban):
            self.ClientHandler.SendBan(TargetId, SenderName)
        elif (Action == ModerationAction.Unban):
            self.ClientHandler.SendUnban(TargetId, SenderName)
            
        await self.ProcessActionOnUser(TargetId, SenderName, Action)
        