from Logger import Logger, LogLevel
from BotEnums import BanResult, RelayMessageType
from Config import Config
from BotConnections import RelayClient
import discord, asyncio, json
from discord.ext import tasks
from BotDatabase import ScamBotDatabase
from queue import SimpleQueue
from BotCommands import GlobalScamCommands
from CommandHelpers import CommandErrorHandler

__all__ = ["DiscordBot"]

ConfigData:Config=Config()

class DiscordBot(discord.Client):
    # Discord Channel that serves for notifications on bot activity/errors/warnings
    NotificationChannel = None
    ReportChannel = None
    ReportChannelTag = None
    BotID:int = None
    ClientHandler:RelayClient = None
    Database:ScamBotDatabase = None
    AsyncTasks = set()
    LoggingMessageQueue=SimpleQueue()
        
    def __init__(self, RelayFileLocation, AssignedBotID:int=-1):
        self.Database = ScamBotDatabase()
        self.BotID = AssignedBotID
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
        self.Commands.on_error = CommandErrorHandler
        self.ClientHandler = RelayClient(RelayFileLocation, self.BotID)
        self.SetupClientHooks()

    def __del__(self):
        Logger.Log(LogLevel.Notice, f"Closing the discord scam bot instance #{self.BotID} {self}")
        
    def SetupClientHooks(self):
        Logger.Log(LogLevel.Verbose, f"Instance #{self.BotID} is setting up function registration")
        # Register functions for handling basic client actions
        self.ClientHandler.RegisterFunction(RelayMessageType.BanUser, self.BanUser)
        self.ClientHandler.RegisterFunction(RelayMessageType.UnbanUser, self.UnbanUser)
        self.ClientHandler.RegisterFunction(RelayMessageType.ReprocessInstance, self.ScheduleReprocessInstance)
        self.ClientHandler.RegisterFunction(RelayMessageType.ReprocessBans, self.ScheduleReprocessBans)
        self.ClientHandler.RegisterFunction(RelayMessageType.LeaveServer, self.LeaveServer)
        self.ClientHandler.RegisterFunction(RelayMessageType.ProcessActivation, self.ProcessActivationForInstance)
        self.ClientHandler.RegisterFunction(RelayMessageType.ProcessDeactivation, self.ProcessDeactivationForInstance)
        self.ClientHandler.RegisterFunction(RelayMessageType.Ping, self.PostPongMessage)
            
    async def setup_hook(self):
        CommandControlServer=discord.Object(id=ConfigData["ControlServer"])
        
        GlobalCommands = GlobalScamCommands(name="scamguard",
                                            description="Handles ScamGuard commands", 
                                            # Allow only users that can submit bans
                                            default_permissions=discord.Permissions(1 << 2),
                                            extras={"instance": self})
        
        self.Commands.add_command(GlobalCommands)
        if (ConfigData.IsDevelopment()):
            # This copies the global commands over to your guild.
            self.Commands.copy_global_to(guild=CommandControlServer)
            await self.Commands.sync(guild=CommandControlServer)
            await self.Commands.sync()
        else:
            # Remove the report and check commands from any control servers
            self.Commands.remove_command(GlobalCommands, guild=CommandControlServer)
            await self.Commands.sync(guild=CommandControlServer)
            await self.Commands.sync()
            
        await super().setup_hook()
       
    ### Event Queueing ###
    def AddAsyncTask(self, TaskToComplete):
        try:
            CurrentLoop = self.loop
            if (CurrentLoop is None):
                Logger.Log(LogLevel.Debug, "Self loop is currently invalid, grabbing current running loop")
                CurrentLoop = asyncio.get_running_loop()
        except RuntimeError:
            return

        NewTask = CurrentLoop.create_task(TaskToComplete)
        self.AsyncTasks.add(NewTask)
        NewTask.add_done_callback(self.AsyncTasks.discard)
    
    ### Discord Tasks Handling ###
    @tasks.loop(seconds=0.5)
    async def HandleRelayMessages(self):
        await self.ClientHandler.RecvMessage()
        
    @HandleRelayMessages.before_loop
    async def BeforeClientRelay(self):
        await self.wait_until_ready()
        self.ClientHandler.SendHello()
    
    @tasks.loop(seconds=1)
    async def PostLogMessages(self):
        while (not self.LoggingMessageQueue.empty()):
            Message:str = self.LoggingMessageQueue.get_nowait()
            try:
                if (self.NotificationChannel is not None):
                    await self.NotificationChannel.send(Message)
            except discord.HTTPException as ex:
                Logger.Log(LogLevel.Log, f"WARN: Unable to send message to notification channel {str(ex)}")
            
    @PostLogMessages.before_loop
    async def BeforePostLogMessages(self):
        await self.wait_until_ready()
            
    ### Config Handling ###
    def ProcessConfig(self, ShouldReload:bool):
        if (ShouldReload):
            ConfigData.Load()
                
        if (ConfigData.IsValid("NotificationChannel", int)):
            self.NotificationChannel = self.get_channel(ConfigData["NotificationChannel"])
            
        if (ConfigData.IsValid("ReportChannel", int)):
            self.ReportChannel = self.get_channel(ConfigData["ReportChannel"])
            for tag in self.ReportChannel.available_tags:
                if (tag.name == ConfigData["ReportChannelTag"]):
                    self.ReportChannelTag = tag
                    break

        Logger.Log(LogLevel.Notice, f"Bot (#{self.BotID}) configs applied")
        
    ### Leaving Servers ###
    def LeaveServer(self, ServerId:int) -> bool:
        BotServerIsIn:int = self.Database.GetBotIdForServer(ServerId)
        # If the bot is in any server we know about
        if (BotServerIsIn != -1):
            # If the bot id == 0, then it is the control bot.
            if (BotServerIsIn == self.BotID):
                self.AddAsyncTask(self.ForceLeaveServer(ServerId))
            else:
                self.ClientHandler.SendLeaveServer(ServerId, BotServerIsIn)
            return True
        return False
    
    async def ForceLeaveServer(self, ServerId:int):
        ServerToLeave:discord.Guild = self.get_guild(ServerId)
        if (ServerToLeave is not None):
            Logger.Log(LogLevel.Notice, f"We have left the server {ServerToLeave.name}[{ServerId}]")
            await ServerToLeave.leave()
        else:
            Logger.Log(LogLevel.Warning, f"Could not find server with id {ServerId}, id is invalid")        
     
    ### Discord Information Gathering ###       
    async def GetServersWithElevatedPermissions(self, UserID:int, SkipActivated:bool):
        ServersWithPermissions = []
        for Server in self.guilds:
            ServerId:int = Server.id
            if (SkipActivated and self.Database.IsActivatedInServer(ServerId)):
                continue
            
            # Owners are an easy add
            if (Server.owner_id == UserID):
                ServersWithPermissions.append(ServerId)
            else:
                GuildMember:discord.Member = await self.LookupUser(UserID, ServerToInspect=Server)
                if (GuildMember is not None):
                    if (self.UserHasElevatedPermissions(GuildMember)):
                        ServersWithPermissions.append(ServerId)
                        Logger.Log(LogLevel.Log, f"User [{UserID}] is in server {Server.name} with permissions")
                    else:
                        Logger.Log(LogLevel.Verbose, f"User [{UserID}] does not have elevated permissions in {Server.name}")
                else:
                    Logger.Log(LogLevel.Verbose, f"User [{UserID}] is not in server {Server.name}")
        return ServersWithPermissions
    
    async def UserAccountExists(self, UserID:int) -> bool:
        try:
            await self.fetch_user(UserID)
            return True
        except discord.NotFound:
            return False
        except discord.HTTPException:
            return False
        
        return False

    async def LookupUser(self, UserID:int, ServerToInspect:discord.Guild=None) -> discord.User|discord.Member|None:
        GivenServer:bool = (ServerToInspect is not None)
        try:
            if (GivenServer):
                return await ServerToInspect.fetch_member(UserID)
            else:
                return await self.fetch_user(UserID)
        except discord.Forbidden:
            Logger.Log(LogLevel.Error, f"Bot does not have access to {ServerToInspect.name}")
        except discord.NotFound as ex:
            if (GivenServer):
                Logger.Log(LogLevel.Debug, f"Could not find user {UserID} in {ServerToInspect.name}")
            else:
                Logger.Log(LogLevel.Warn, f"UserID {UserID} was not found with error {str(ex)}")
        except discord.HTTPException as httpEx:
            Logger.Log(LogLevel.Warn, f"Failed to fetch user {UserID}, got {str(httpEx)}")
        return None
    
    def UserHasElevatedPermissions(self, User:discord.Member) -> bool:
        if (User is None):
            return False
         
        UserPermissions:discord.Permissions = User.guild_permissions 
        if (UserPermissions.administrator or (UserPermissions.manage_guild and UserPermissions.ban_members)):
            return True
        return False
    
    ### Activating/Deactivating Servers ###
    async def ActivateServersWithPermissions(self, UserID:int) -> int:
        ServersWithPermissions = await self.GetServersWithElevatedPermissions(UserID, True)
        NumServersWithPermissions:int = len(ServersWithPermissions)
        Logger.Log(LogLevel.Log, f"User [{UserID}] has {NumServersWithPermissions} servers with acceptable permissions...")
        if (NumServersWithPermissions > 0):
            # TODO: instead of activating and reprocessing on our own, have this be sent by the listener controller
            #self.ClientHandler.SendElevatedResults(ServersWithPermissions)
            self.Database.SetBotActivationForOwner(ServersWithPermissions, True, self.BotID, ActivatorId=UserID)
            for ServerId in ServersWithPermissions:
                self.AddAsyncTask(self.ReprocessBans(ServerId))
        return NumServersWithPermissions
    
    async def DeactivateServersWithPermissions(self, UserID:int) -> int:
        ServersWithPermissions = await self.GetServersWithElevatedPermissions(UserID, False)
        NumServersWithPermissions:int = len(ServersWithPermissions)
        if (NumServersWithPermissions > 0):
            self.Database.SetBotActivationForOwner(ServersWithPermissions, False, self.BotID, ActivatorId=UserID)
        return NumServersWithPermissions
    
    def ProcessActivationForInstance(self, UserID:int):
        self.AddAsyncTask(self.ActivateServersWithPermissions(UserID))
        
    def ProcessDeactivationForInstance(self, UserID:int):
        self.AddAsyncTask(self.DeactivateServersWithPermissions(UserID))
        
    ### Starting execution ###
    async def InitializeBotRuntime(self):
        self.ProcessConfig(False)
        # Set status
        if (ConfigData.IsValid("BotActivity", str)):
            activity = None
            IdPrefix:str = f"ID: #{self.BotID} "
            if (ConfigData.IsDevelopment()):
                activity = discord.CustomActivity(name=IdPrefix + ConfigData["BotActivityDevelopment"])
            else:
                activity = discord.CustomActivity(name=IdPrefix + ConfigData["BotActivity"])
            await self.change_presence(status=discord.Status.online, activity=activity)

        # Set logger callbacks for notifications
        if (self.NotificationChannel is not None):
            Logger.SetNotificationCallback(self.PostNotification)

        self.Database.ReconcileServers(self.guilds, self.BotID)
        
        # If our task is not already running, start it. 
        # We do this check because on_ready could be called again on reconnections.
        if (not self.HandleRelayMessages.is_running()):
            self.HandleRelayMessages.start()
            
        if (not self.PostLogMessages.is_running()):
            self.PostLogMessages.start()

        Logger.Log(LogLevel.Notice, f"Bot (#{self.BotID}) has started! Is Development? {ConfigData.IsDevelopment()}")
    
    ### Discord Eventing ###        
    async def on_ready(self):
        self.AddAsyncTask(self.InitializeBotRuntime())
    
    async def on_guild_update(self, PriorUpdate:discord.Guild, NewUpdate:discord.Guild):
        NewOwnerId:int = NewUpdate.owner_id
        if (PriorUpdate.owner_id != NewOwnerId):
            self.Database.SetNewServerOwner(NewUpdate.id, NewOwnerId, self.BotID)
            Logger.Log(LogLevel.Notice, f"Detected that the server {PriorUpdate.name}[{NewUpdate.id}] is now owned by {NewOwnerId}")
            
    async def on_guild_join(self, server:discord.Guild):
        OwnerName:str = "Admin"
        if (server.owner is not None):
            OwnerName = server.owner.display_name
            
        # Prevent ourselves from being added to a server we are already in.
        if (self.Database.IsInServer(server.id)):
            Logger.Log(LogLevel.Notice, f"Bot #{self.BotID} was attempted to be added to server {server.name}[{server.id}] but already in there")
            await server.leave()
            return

        self.Database.SetBotActivationForOwner([server.id], False, self.BotID, OwnerId=server.owner_id)
        Logger.Log(LogLevel.Notice, f"Bot (#{self.BotID}) has joined server {server.name}[{server.id}] of owner {OwnerName}[{server.owner_id}]")
        
    async def on_guild_remove(self, server:discord.Guild):
        OwnerName:str = "Admin"
        if (server.owner is not None):
            OwnerName = server.owner.display_name
        
        self.Database.RemoveServerEntry(server.id, self.BotID)
        Logger.Log(LogLevel.Notice, f"Bot (#{self.BotID}) has been removed from server {server.name}[{server.id}] of owner {OwnerName}[{server.owner_id}]")
        
    ### Report Handling ###
    async def PostScamReport(self, ReportData):
        if (self.ReportChannel is None or self.ReportChannelTag is None):
            return
        
        PostEmbeds:list[discord.Embed] = []
        if (ConfigData["AutoEmbedScamCheckOnReport"]):
            PostEmbeds.append(await self.CreateBanEmbed(ReportData['ReportedUserId']))
        
        ReasoningString:str = ""
        if (len(ReportData["Reasoning"])):
            ReasoningString = f"Reasoning: {ReportData['Reasoning']}"
        
        # Format the message that is going to be posted!
        ReportContent:str = f"""
        User ID: `{ReportData['ReportedUserId']}`
Username: {ReportData['ReportedUserName']}
Type Of Scam: {ReportData['TypeOfScam']}
{ReasoningString}
        
Reported Remotely By: {ReportData['ReportingUserName']}[{ReportData['ReportingUserId']}] from {ReportData['ReportedServer']}[{ReportData['ReportedServerId']}]
"""
        
        # Format all the image embeds into the list properly
        NumEmbeds:int = len(PostEmbeds)
        for Evidence in ReportData["Evidence"]:
            if (NumEmbeds >= 10):
                break
            
            if (Evidence.startswith("https")):
                NewEmbed:discord.Embed = discord.Embed()
                NewEmbed.set_image(url=Evidence)
                PostEmbeds.append(NewEmbed)
                NumEmbeds += 1
        
        try:
            await self.ReportChannel.create_thread(name=ReportData["ReportedUserGlobalName"],
                                         content=ReportContent,
                                         applied_tags=[self.ReportChannelTag],
                                         reason=f"ScamReportfrom {ReportData['ReportingUserName']}[{ReportData['ReportingUserId']}]",
                                         embeds=PostEmbeds)
        except discord.Forbidden:
            Logger.Log(LogLevel.Error, f"Unable to make report on user {ReportData['ReportedUserId']} as we do not have permissions to do so!")
        except discord.HTTPException as ex:
            Logger.Log(LogLevel.Error, f"Unable to make report on user {json.dumps(ReportData)} with exception {str(ex)}")

    ### Utils ###
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
            UserData.add_field(name="Banned By", value=f"{BanData.assigner_discord_user_name}", inline=False)
            # Create a date time format (all of the database timestamps are in iso format)
            UserData.add_field(name="Banned At", value=f"{discord.utils.format_dt(BanData.created_at)}", inline=False)
            # Push a last updated field if the time stamps aren't the same
            if (BanData.created_at != BanData.updated_at):
                UserData.add_field(name="Last Updated", value=f"{discord.utils.format_dt(BanData.updated_at)}", inline=False)

            UserData.colour = discord.Colour.red()
        elif (not HasUserData):
            UserData.colour = discord.Colour.dark_orange()
        else:
            UserData.colour = discord.Colour.green()

        UserData.set_footer(text=f"User ID: {TargetId}")
        return UserData
    
    def PostPongMessage(self):
        Logger.Log(LogLevel.Notice, "I have been pinged!")
        
    async def PostNotification(self, Message:str):
        self.LoggingMessageQueue.put(Message)

    ### Ban Handling ###        
    async def ReprocessBans(self, ServerId:int, LastActions:int=0) -> BanResult:
        Server:discord.Guild = self.get_guild(ServerId)
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

            UserId:int = int(Ban.discord_user_id)
            UserToBan = discord.Object(UserId)
            BanResponse = await self.PerformActionOnServer(Server, UserToBan, f"User banned by {Ban.assigner_discord_user_name}", True)
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
    
    async def ReprocessInstance(self, LastActions:int):
        BanQueryResult = self.Database.GetAllBans(LastActions)
        for Ban in BanQueryResult:
            UserId:int = Ban.discord_user_id
            AuthorizerName:str = Ban.assigner_discord_user_name
            await self.ProcessActionOnUser(UserId, AuthorizerName, True)
    
    def ScheduleReprocessInstance(self, LastActions:int):
        self.AddAsyncTask(self.ReprocessInstance(LastActions))
    
    def ScheduleReprocessBans(self, ServerId:int, LastActions:int=0):
        self.AddAsyncTask(self.ReprocessBans(ServerId, LastActions))
        
    def BanUser(self, TargetId:int, AuthName:str):
        self.AddAsyncTask(self.ProcessActionOnUser(TargetId, AuthName, True))
        
    def UnbanUser(self, TargetId:int, AuthName:str):
        self.AddAsyncTask(self.ProcessActionOnUser(TargetId, AuthName, False))
        
    # Handles pushing the ban/unban to every server we are in
    async def ProcessActionOnUser(self, TargetId:int, AuthorizerName:str, IsBan:bool):
        NumServersPerformed:int = 0
        ActionsAppliedThisLoop:int = 0
        DoesSleep:bool = ConfigData["UseSleep"]
        
        UserToWorkOn = discord.Object(TargetId)
        ScamStr:str = "scammer"
        if (not IsBan):
            ScamStr = "non-scammer"
        
        BanReason=f"Confirmed {ScamStr} by {AuthorizerName}"
        AllServers = self.Database.GetAllActivatedServers(self.BotID)
        NumServers:int = len(AllServers)
        
        # Instead of going through all servers it's added to, choose all servers that are activated.
        for ServerData in AllServers:
            if (DoesSleep):
                # Put in sleep functionality on this loop, as it could be heavy
                if (ActionsAppliedThisLoop >= ConfigData["ActionsPerTick"]):
                    await asyncio.sleep(ConfigData["SleepAmount"])
                    ActionsAppliedThisLoop = 0
                else:
                    ActionsAppliedThisLoop += 1
                
            ServerId:int = int(ServerData.discord_server_id)
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
        
    # Handles banning/unbanning an user in each individual server
    async def PerformActionOnServer(self, Server:discord.Guild, User:discord.Member, Reason:str, IsBan:bool) -> (bool, BanResult):
        IsDevelopmentMode:bool = ConfigData.IsDevelopment()
        BanId:int = User.id
        ServerOwnerId:int = Server.owner_id
        ServerInfo:str = f"{Server.name}[{Server.id}]"
        try:
            BanStr:str = "ban"
            if (not IsBan):
                BanStr = "unban"
            
            Logger.Log(LogLevel.Verbose, f"Performing {BanStr} action on {BanId} in {ServerInfo} owned by {ServerOwnerId}")
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