# This is the base class for all of our Discord bots
# Any code that needs to be referenced by sub-instances and the main instance of ScamGuard should go here
# Usually for any core shared features. 
# 
# This separation was originally due to Discord politics when ScamGuard was first developed.
# Since then, everything can potentially envelop back into the main instance instead.
from Logger import Logger, LogLevel
from BotEnums import BanResult, RelayMessageType
from Config import Config
from BotConnections import RelayClient
import discord, asyncio, json, aiohttp, io
from discord.ext import tasks
from BotDatabase import ScamBotDatabase
from queue import SimpleQueue
from BotCommands import GlobalScamCommands
from CommandHelpers import CommandErrorHandler
from ServerActivation import ScamGuardServerSetup

__all__ = ["DiscordBot"]

ConfigData:Config=Config()

class DiscordBot(discord.Client):
    # Discord Channel that serves for notifications on bot activity/errors/warnings
    NotificationChannel = None
    ActivationChannel = None
    # Channel to send updates as to when someone is banned/unbanned
    AnnouncementChannel = None
    ReportChannel = None
    ReportChannelTag = None
    ServerSetupHelper = None
    BotID:int = -1

    def __init__(self, RelayFileLocation, AssignedBotID:int=-1):
        self.Database:ScamBotDatabase = None
        self.ClientHandler:RelayClient = None
        self.AsyncTasks = set()
        self.LoggingMessageQueue = SimpleQueue()
        self.Database = ScamBotDatabase()
        self.ServerSetupHelper = ScamGuardServerSetup(self)
        self.BotID = AssignedBotID
        intents = discord.Intents.none()
        intents.guilds = True
        intents.bans = True
        
        if (ConfigData["AllowWebhookInstall"]):
            intents.webhooks = True
        
        # bring in these intents so we can get an idea of shared servers scamcheck returns.
        # Do note, if these are enabled, the bot will take about 1 min to start up.
        if (ConfigData["ScamCheckShowsSharedServers"]):
            intents.members = True
            intents.presences = True
        elif (ConfigData["AllowSuspiciousUserKicks"]):
            intents.members = True

        super().__init__(intents=intents)
        self.Commands = discord.app_commands.CommandTree(self)
        self.Commands.on_error = CommandErrorHandler
        
        self.SetupClientConnection(RelayFileLocation)

    def __del__(self):
        Logger.Log(LogLevel.Notice, f"Closing the discord scam bot instance #{self.BotID} {self}")
        
    def SetupClientConnection(self, RelayLocation):
        Logger.Log(LogLevel.Log, f"Instance #{self.BotID} starting relay client")
        
        if (self.ClientHandler is None):
            self.ClientHandler = RelayClient(RelayLocation, self.BotID)
        
        Logger.Log(LogLevel.Verbose, f"Instance #{self.BotID} is setting up function registration")
        # Register functions for handling basic client actions
        self.ClientHandler.RegisterFunction(RelayMessageType.BanUser, self.BanUser)
        self.ClientHandler.RegisterFunction(RelayMessageType.UnbanUser, self.UnbanUser)
        self.ClientHandler.RegisterFunction(RelayMessageType.ReprocessInstance, self.ScheduleReprocessInstance)
        self.ClientHandler.RegisterFunction(RelayMessageType.ReprocessBans, self.ScheduleReprocessBans)
        self.ClientHandler.RegisterFunction(RelayMessageType.LeaveServer, self.LeaveServer)
        self.ClientHandler.RegisterFunction(RelayMessageType.ProcessActivation, self.ProcessActivationForInstance)
        self.ClientHandler.RegisterFunction(RelayMessageType.ProcessServerActivation, self.ProcessServerActivationForInstance)
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
            CurrentLoop = asyncio.get_running_loop()
        except RuntimeError:
            Logger.Log(LogLevel.Log, f"Encountered an error while trying to add async task {str(TaskToComplete)}")
            return

        Logger.Log(LogLevel.Log, f"Added task {str(TaskToComplete)} to task queue")
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
                    await self.NotificationChannel.send(Message) # type: ignore
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
            
        if (ConfigData.IsValid("ActivationChannel", int)):
            self.ActivationChannel = self.get_channel(ConfigData["ActivationChannel"])
            
        if (ConfigData.IsValid("AnnouncementChannel", int)):
            self.AnnouncementChannel = self.get_channel(ConfigData["AnnouncementChannel"])
            
        if (ConfigData.IsValid("ReportChannel", int)):
            self.ReportChannel = self.get_channel(ConfigData["ReportChannel"])
            for tag in self.ReportChannel.available_tags: # type: ignore
                if (tag.name == ConfigData["ReportChannelTag"]):
                    self.ReportChannelTag = tag
                    break

        Logger.Log(LogLevel.Notice, f"Bot (#{self.BotID}) configs applied")
        
    ### Leaving Servers ###
    def LeaveServer(self, ServerId:int) -> bool:
        BotServerIsIn:int|None = self.Database.GetBotIdForServer(ServerId)
        if (BotServerIsIn is None):
            return False
        
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
        ServerToLeave:discord.Guild|None = self.get_guild(ServerId)
        if (ServerToLeave is not None):
            ServerInfoStr:str = self.GetServerInfoStr(ServerToLeave)
            try:
                await ServerToLeave.leave()
                Logger.Log(LogLevel.Notice, f"We have left the server {ServerInfoStr}")
            except discord.errors.HTTPException:
                Logger.Log(LogLevel.Verbose, f"Could not leave server {ServerInfoStr}, we are getting rate limited")
        else:
            Logger.Log(LogLevel.Warn, f"Could not find server with id {ServerId}, id is invalid")        
     
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
                GuildMember:discord.Member|None = await self.LookupUser(UserID, ServerToInspect=Server)
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

    async def LookupUser(self, UserID:int, ServerToInspect:discord.Guild|None=None) -> discord.User|discord.Member|None:
        GivenServer:bool = (ServerToInspect is not None)
        try:
            if (GivenServer):
                return await ServerToInspect.fetch_member(UserID)
            else:
                return await self.fetch_user(UserID)
        except discord.Forbidden:
            Logger.CLog(GivenServer, LogLevel.Error, f"Bot does not have access to {ServerToInspect.name}")
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
    
    async def ActivateServerInstance(self, UserID:int, ServerID:int):
        if (self.Database.GetBotIdForServer(ServerID) != self.BotID):
            return
        
        Logger.Log(LogLevel.Notice, f"Activing ServerID {ServerID} from user {UserID}")
        self.Database.SetBotActivationForOwner([ServerID], True, self.BotID, ActivatorId=UserID)
        self.AddAsyncTask(self.ReprocessBans(ServerID))
        
    async def DeactivateServersWithPermissions(self, UserID:int) -> int:
        ServersWithPermissions = await self.GetServersWithElevatedPermissions(UserID, False)
        NumServersWithPermissions:int = len(ServersWithPermissions)
        if (NumServersWithPermissions > 0):
            self.Database.SetBotActivationForOwner(ServersWithPermissions, False, self.BotID, ActivatorId=UserID)
        return NumServersWithPermissions
    
    def ProcessActivationForInstance(self, UserID:int):
        self.AddAsyncTask(self.ActivateServersWithPermissions(UserID))
        
    def ProcessServerActivationForInstance(self, UserId:int, ServerId:int):
        self.AddAsyncTask(self.ActivateServerInstance(UserId, ServerId))
        
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
        NewOwnerId:int|None = NewUpdate.owner_id
        if (NewOwnerId is None):
            return
        
        if (PriorUpdate.owner_id != NewOwnerId):
            self.Database.SetNewServerOwner(NewUpdate.id, NewOwnerId, self.BotID)
            Logger.Log(LogLevel.Notice, f"Detected that the server {self.GetServerInfoStr(PriorUpdate)} is now owned by {NewOwnerId}")
            
    async def on_guild_join(self, server:discord.Guild):
        OwnerName:str = "Admin"
        if (server.owner is not None):
            OwnerName = server.owner.display_name
            
        # Prevent ourselves from being added to a server we are already in.
        if (self.Database.IsInServer(server.id)):
            Logger.Log(LogLevel.Notice, f"Bot #{self.BotID} was attempted to be added to server {self.GetServerInfoStr(server)} but already in there")
            # TODO: Print a message to the user?
            await server.leave()
            return

        self.Database.SetBotActivationForOwner([server.id], False, self.BotID, OwnerId=server.owner_id)
        Logger.Log(LogLevel.Notice, f"Bot (#{self.BotID}) has joined server {self.GetServerInfoStr(server)} of owner {OwnerName}[{server.owner_id}]")
        
    async def on_guild_remove(self, server:discord.Guild):
        OwnerName:str = "Admin"
        if (server.owner is not None):
            OwnerName = server.owner.display_name
        
        self.Database.RemoveServerEntry(server.id, self.BotID)
        Logger.Log(LogLevel.Notice, f"Bot (#{self.BotID}) has been removed from server {self.GetServerInfoStr(server)} of owner {OwnerName}[{server.owner_id}]")
        
    ### Report Handling ###
    async def PostScamReport(self, ReportData):
        if (self.ReportChannel is None or self.ReportChannelTag is None):
            return
        
        ImageFormats = ("image/png", "image/jpeg", "image/jpg", "image/bmp", "image/webp")
        PostEmbeds:list[discord.Embed] = []
        PostFiles:list[discord.File] = []
        if (ConfigData["AutoEmbedScamCheckOnReport"]):
            PostEmbeds.append(await self.CreateBanEmbed(ReportData['ReportedUserId']))
        
        ReasoningString:str = ""
        if (len(ReportData["Reasoning"])):
            ReasoningString = f"Reasoning: {ReportData['Reasoning']}"
            
        ReportUserId = ReportData['ReportedUserId']
        ReportUserHandle = ReportData['ReportedUserName']
        ReportUserName = ReportData['ReportedUserGlobalName']
        
        # Format the message that is going to be posted!
        ReportContent:str = f"""
        User ID: `{ReportUserId}`
Username: {ReportUserName}
Type Of Scam: {ReportData['TypeOfScam']}
{ReasoningString}
        
Reported Remotely By: {ReportData['ReportingUserName']}[{ReportData['ReportingUserId']}] from {ReportData['ReportedServer']}[{ReportData['ReportedServerId']}]

Failed Copied Evidence Links:

"""
        # Format all the image embeds into the list properly
        NumEvidences:int = len(PostFiles)
        
        async with aiohttp.ClientSession() as session:
            HadCopyFailure:bool = False
            for Evidence in ReportData["Evidence"]:
                if (NumEvidences >= 10):
                    break
                
                if (Evidence.startswith("https")):
                    async with session.get(Evidence) as response:
                        if (response.status != 200):
                            Logger.Log(LogLevel.Warn, f"Bot (#{self.BotID}) could not download file {Evidence} for report {ReportUserId}")
                            ReportContent += f"* {Evidence}\n"
                            HadCopyFailure = True
                            continue
                        ContentType = response.headers['content-type']
                        if ContentType not in ImageFormats:
                            Logger.Log(LogLevel.Warn, f"Bot (#{self.BotID}) was given {Evidence} for {ReportUserId} but that is of type {ContentType} which is not an image")
                            continue
                        EvidenceData = io.BytesIO(await response.read())
                        NewFile:discord.File = discord.File(EvidenceData, f'Evidence{NumEvidences}.png')
                        PostFiles.append(NewFile)
                        NumEvidences += 1
            if (not HadCopyFailure):
                ReportContent += "None"
        try:
            if (self.ReportChannel is None):
                return
            
            NewThread:discord.channel.ThreadWithMessage = await self.ReportChannel.create_thread(name=ReportData["ReportedUserGlobalName"],
                                         content=ReportContent,
                                         applied_tags=[self.ReportChannelTag],
                                         reason=f"ScamReportfrom {ReportData['ReportingUserName']}[{ReportData['ReportingUserId']}]",
                                         embeds=PostEmbeds, files=PostFiles)
            
            # Update the user with the ScamGuard thread that was created
            ThreadEmbed:discord.Embed = self.CreateBaseEmbed(f"Report created for {ReportUserName}")
            ThreadEmbed.add_field(name="User Name", value=f"{ReportUserName}")
            ThreadEmbed.add_field(name="User Handle", value=f"{ReportUserHandle}")
            ThreadEmbed.add_field(name="User ID", value=f"{ReportUserId}", inline=False)
            ThreadEmbed.add_field(name="Thread Link (for updates)", value=f"{NewThread.thread.mention}", inline=False)
            ThreadEmbed.set_footer(text="Can't see the thread? Join the server: https://scamguard.app/discord")
            await ReportData["Webhook"].send(embed=ThreadEmbed, ephemeral=False)
            
        except discord.NotFound:
            Logger.Log(LogLevel.Warn, "Unable to update the original command that sent a report with a new embed, the followup has expired.")
        except discord.Forbidden:
            Logger.Log(LogLevel.Error, f"Unable to make report on user {ReportData['ReportedUserId']} as we do not have permissions to do so!")
        except discord.HTTPException as ex:
            Logger.Log(LogLevel.Error, f"Unable to make report on user {json.dumps(ReportData)} with exception {str(ex)}")
            
    ### Webhook Management ###
    async def InstallWebhook(self, ServerId:int):
        if (self.AnnouncementChannel is None):
            Logger.Log(LogLevel.Notice, "Announcement channel is None, cannot manage webhooks!")
            return
        
        ChannelID:int|None = self.Database.GetChannelIdForServer(ServerId)
        if (ChannelID is None):
            Logger.Log(LogLevel.Warn, f"Could not install webhook for server {ServerId}, the ChannelID was None")
            return
        
        MessageChannel:discord.TextChannel = self.get_channel(ChannelID) # type: ignore
        
        # Check to see if a webhook is already installed.
        if (MessageChannel is not None):
            try:
                CurrentWebhooks = await MessageChannel.webhooks()
                for Webhook in CurrentWebhooks:
                    if (Webhook.source_channel is None):
                        continue
                    # The webhook is already installed, do not attempt to install again.
                    if (Webhook.type == discord.WebhookType.channel_follower and Webhook.source_channel.id == self.AnnouncementChannel.id):
                        return
            except discord.Forbidden:
                Logger.Log(LogLevel.Warn, f"Unable to check the currently installed webhooks to the channel {ChannelID} in server {ServerId} to see if it was already installed.")
        else:
            Logger.Log(LogLevel.Warn, f"Attempted to install a webhook for an invalid message channel object. Server: {ServerId}, ChannelId: {ChannelID}")
            return
        
        try:
            await self.AnnouncementChannel.follow(destination=MessageChannel, reason="ScamGuard Ban Notification Setup") # type: ignore
        except discord.Forbidden:
            await MessageChannel.send("ScamGuard was unable to install the ban notification webhook. You can try again later, or manually install from the TAG Server")
        except discord.HTTPException:
            Logger.Log(LogLevel.Warn, f"")
            
    async def DeleteWebhook(self, ServerId:int):
        if (self.AnnouncementChannel is None):
            Logger.Log(LogLevel.Notice, "Announcement channel is None, cannot manage webhooks!")
            return
        
        ChannelID:int|None = self.Database.GetChannelIdForServer(ServerId)
        if (ChannelID is None):
            Logger.Log(LogLevel.Warn, f"Could not uninstall webhook for server {ServerId}, the ChannelID was None")
            return
        MessageChannel:discord.TextChannel = self.get_channel(ChannelID)
        FoundWebhook:discord.Webhook|None = None
        
        # Check to see if a webhook is already installed.
        if (MessageChannel is not None):
            try:
                CurrentWebhooks = await MessageChannel.webhooks()
                for Webhook in CurrentWebhooks:
                    if (Webhook.source_channel is None):
                        continue
                    # The webhook is already installed, grab a reference to it.
                    if (Webhook.type == discord.WebhookType.channel_follower and Webhook.source_channel.id == self.AnnouncementChannel.id):
                        FoundWebhook = Webhook
                        break
            except discord.Forbidden:
                Logger.Log(LogLevel.Warn, f"Unable to handle enumerating webhooks for {MessageChannel.id} in {ServerId} to delete the webhook")
        else:
            return
        
        # If we didn't find any webhooks, then stop processing.
        if (FoundWebhook is None):
            return
        
        try:
            await FoundWebhook.delete(reason="ScamGuard Setting Change")
        except discord.Forbidden:
            await MessageChannel.send("ScamGuard does not have the appropriate permissions to delete the Ban Notification Webhook, you will have to do it manually.")
        except discord.HTTPException:
            await MessageChannel.send("Unable to delete the Ban Notification Webhook, you will have to do it manually.")

    ### Utils ###
    def GetServerInfoStr(self, Server:discord.Guild) -> str:
        return f"{Server.name}[{Server.id}]"
    
    def GetControlServerGuild(self) -> discord.Guild|None:
        return self.get_guild(ConfigData["ControlServer"])
    
    def PostPongMessage(self):
        Logger.Log(LogLevel.Notice, "I have been pinged!")
        
    async def PostNotification(self, Message:str):
        self.LoggingMessageQueue.put(Message)
        
    async def ApplySettings(self, NewSettings):
        ServerID:int = NewSettings.GetServerID()
        self.Database.SetFromServerSettings(ServerID, NewSettings)
        if (NewSettings.WantsWebhooks):
            await self.InstallWebhook(ServerID)
        else:
            await self.DeleteWebhook(ServerID)
    
    ### Embeds ###
    def CreateBaseEmbed(self, Title:str, ApplyThumbnail:bool=True) -> discord.Embed:
        ReturnEmbed:discord.Embed = discord.Embed(title=Title, colour=discord.Colour.from_rgb(0, 0, 0))
        if (ConfigData.IsValid("AppEmbedThumbnail", str) and ApplyThumbnail):
            ReturnEmbed.set_thumbnail(url=ConfigData["AppEmbedThumbnail"])
        
        ReturnEmbed.set_author(name="ScamGuard", url="https://scamguard.app")
        return ReturnEmbed
    
    def AddSettingsEmbedInfo(self, AddToEmbed:discord.Embed):
        AddToEmbed.add_field(name="Settings", value="", inline=False)
        AddToEmbed.add_field(name="Mod Message Channel", inline=False, value="Granting ScamGuard access to a channel for moderators only is highly suggested. Warnings about bot operation conflicts will be posted there. Messages are sent very infrequently.")
        AddToEmbed.add_field(name="Ban Notifications", inline=False, value="ScamGuard can also post a notification whenever it bans someone from your server, it is highly encouraged to subscribe to this notification, select Yes when prompted about installing a webhook. It is highly recommended, but not necessary.")
    
    def CreateInfoEmbed(self) -> discord.Embed:
        NumServers:int = self.Database.GetNumServers()
        NumActivated:int = self.Database.GetNumActivatedServers()
        ResponseEmbed:discord.Embed = self.CreateBaseEmbed("ScamGuard Info")
        ResponseEmbed.add_field(name="About", inline=False, value="ScamGuard is a free bot application that helps prevent scammers from entering your servers. It is managed by [SocksTheWolf](https://socksthewolf.com)")
        ResponseEmbed.add_field(name="Links", value="[Website](https://scamguard.app)\n[GitHub](https://github.com/SocksTheWolf/AntiScamBot)")
        ResponseEmbed.add_field(name="Help", value="[FAQ](https://scamguard.app/faq)\n[Usage](https://scamguard.app/usage)\n[Support Server](https://scamguard.app/discord)")
        ResponseEmbed.add_field(name="Terms", value="[TOS](https://scamguard.app/terms)\n[Privacy Policy](https://scamguard.app/privacy)")
        ResponseEmbed.set_footer(text=f"Scammers Defeated: {self.Database.GetNumBans()} | Servers: {NumActivated}/{NumServers}")
        return ResponseEmbed
        
    async def CreateBanEmbed(self, TargetId:int) -> discord.Embed:
        BanData = self.Database.GetBanInfo(TargetId)
        UserBanned:bool = (BanData is not None)
        User:discord.User = await self.LookupUser(TargetId)
        HasUserData:bool = (User is not None)
        UserData = self.CreateBaseEmbed("User Data", False)
        if (HasUserData):
            UserData.add_field(name="Name", value=User.display_name)
            UserData.add_field(name="Handle", value=User.name, inline=True)
            UserData.add_field(name="Mention", value=User.mention)
            # This will always be an approximation, plus they may be in servers the bot is not in.
            if (ConfigData["ScamCheckShowsSharedServers"]):
                UserData.add_field(name="Shared Servers", value=f"~{len(User.mutual_guilds)}")

            # If currently banned and has an evidence thread, display it.
            if (UserBanned and BanData.evidence_thread is not None):
                UserData.add_field(name="Evidence Thread (TAG Server)", value=f"<#{BanData.evidence_thread}>", inline=False)
            UserData.add_field(name="Account Created", value=f"{discord.utils.format_dt(User.created_at)}", inline=False)
            UserData.set_thumbnail(url=User.display_avatar.url)
        
        UserData.add_field(name="Banned", value=f"{UserBanned}")
        
        # Figure out who banned them
        if (UserBanned):
            UserData.add_field(name="Banned By", value=f"{BanData.assigner_discord_user_name}")
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

    ### Ban Handling ###        
    async def ReprocessBans(self, ServerId:int, LastActions:int=0) -> BanResult:
        Server:discord.Guild|None = self.get_guild(ServerId)
        if (Server is None):
            Logger.Log(LogLevel.Error, f"Could not look up the server {ServerId} while reprocessing bans")
            return BanResult.Error
        
        ServerInfoStr:str = self.GetServerInfoStr(Server)
        BanReturn:BanResult = BanResult.Processed
        Logger.Log(LogLevel.Log, f"Attempting to import ban data to {ServerInfoStr}")
        NumBans:int = 0
        NumFailures:int = 0
        BanQueryResult = self.Database.GetAllBans(LastActions)
        TotalBans:int = len(BanQueryResult)
        ActionsAppliedThisLoop:int = 0
        DoesSleep:bool = ConfigData["UseSleep"]
        DoesHaltOnFailures:bool = ConfigData["MaxBanFailures"] > 0
        for Ban in BanQueryResult:
            if (DoesSleep):
                # Put in sleep functionality on this loop, as it could be heavy
                if (ActionsAppliedThisLoop >= ConfigData["ActionsPerTick"]):
                    await asyncio.sleep(ConfigData["SleepAmount"])
                    ActionsAppliedThisLoop = 0
                else:
                    ActionsAppliedThisLoop += 1
                    
            if (DoesHaltOnFailures and NumFailures > ConfigData["MaxBanFailures"]):
                Logger.Log(LogLevel.Warn, f"Number of ban failures reached {NumFailures} for server {ServerInfoStr}, exiting subprocess.")
                break

            UserId:int = int(Ban.discord_user_id)
            UserToBan = discord.Object(UserId)
            BanResponse = await self.PerformActionOnServer(Server, UserToBan, f"User banned by {Ban.assigner_discord_user_name}", True)
            # See if the ban did go through.
            if (BanResponse[0] == False):
                NumFailures += 1
                BanResponseFlag:BanResult = BanResponse[1]
                self.AddAsyncTask(self.PostBanFailureInformation(Server, UserId, BanResponseFlag, True))
                if (BanResponseFlag == BanResult.LostPermissions):
                    Logger.Log(LogLevel.Error, f"Unable to process ban on user {UserId} for server {ServerInfoStr}")
                    BanReturn = BanResult.LostPermissions
                    break
                elif (BanResponseFlag == BanResult.BansExceeded):
                    Logger.Log(LogLevel.Error, f"Unable to process ban on user {UserId} for server {ServerInfoStr} due to exceed")
                    BanReturn = BanResult.BansExceeded
                    break
            else:
                NumBans += 1
        Logger.Log(LogLevel.Notice, f"Processed {NumBans}/{TotalBans} bans for {ServerInfoStr}!")
        return BanReturn
    
    async def ReprocessInstance(self, LastActions:int):
        BanQueryResult = self.Database.GetAllBans(LastActions)
        for Ban in BanQueryResult:
            UserId:int = int(Ban.discord_user_id)
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
        AllServers = self.Database.GetAllActivatedServersWithBans(self.BotID)
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

            ServerId:int = int(ServerData.discord_server_id) # type: ignore
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
                            Logger.Log(LogLevel.Error, f"Attempted to ban a server owner! {self.GetServerInfoStr(DiscordServer)} with user to work {UserToWorkOn.id} == {DiscordServer.owner_id}")
                            continue
                    elif (ResultFlag == BanResult.LostPermissions or ResultFlag == BanResult.Error or ResultFlag == BanResult.BansExceeded):
                        self.AddAsyncTask(self.PostBanFailureInformation(DiscordServer, TargetId, ResultFlag, IsBan))
            else:
                # TODO: Potentially remove the server from the list?
                Logger.Log(LogLevel.Warn, f"The server {ServerId} did not respond on a look up, does it still exist?")

        Logger.Log(LogLevel.Notice, f"Action execution on {TargetId} as a {ScamStr} performed in {NumServersPerformed}/{NumServers} servers")
        
    # Handles banning/unbanning an user in each individual server
    async def PerformActionOnServer(self, Server:discord.Guild, User:discord.Member, Reason:str, IsBan:bool) -> tuple[bool, BanResult]:
        IsDevelopmentMode:bool = ConfigData.IsDevelopment()
        BanId:int = User.id
        ServerOwnerId:int = Server.owner_id or 0
        ServerInfo:str = self.GetServerInfoStr(Server)
        try:
            BanStr:str = "ban" if IsBan else "unban"            
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
                #self.AddAsyncTask(self.PostBanFailureInformation(Server, BanId, BanResult.LostPermissions, IsBan))
                Logger.Log(LogLevel.Debug, "Action was dropped as we are currently in development mode")
            return (True, BanResult.Processed)
        except discord.NotFound:
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
            if (ex.code == 30035):
                Logger.Log(LogLevel.Warn, f"Hit the bans exceeded error while trying to perform actions on server {ServerInfo}")
                return (False, BanResult.BansExceeded)
            
            Logger.Log(LogLevel.Warn, f"We encountered an error {(str(ex))} while trying to perform for server {ServerInfo} owned by {ServerOwnerId}!")
        return (False, BanResult.Error)
    
    # Handles messaging to server moderators if a ban fails.
    async def PostBanFailureInformation(self, Server:discord.Guild, UserId:int, Reason:BanResult, IsBan:bool):
        if (ConfigData["CanSendServerErrorMessages"] == False):
            return
        
        ChannelIDToPost = self.Database.GetChannelIdForServer(Server.id)
        if (ChannelIDToPost == None):
            return
        
        ServerIDStr:str = self.GetServerInfoStr(Server)
        DiscordChannel = self.get_channel(ChannelIDToPost)
        if (DiscordChannel is None):
            Logger.Log(LogLevel.Error, f"Could not resolve the channel {ChannelIDToPost} for server {ServerIDStr}")
            return
        
        ErrorMsg:str = ""
        ResolutionMsg:str = ""
        if (Reason == BanResult.LostPermissions):
            ErrorMsg = "ScamGuard does not have significant permissions to ban this user"
            ResolutionMsg = "This usually happens if the user in question has grabbed roles that are higher than the bot's.\n\nYou can usually fix this by changing the order as seen in [this video](https://youtu.be/XYaQi3hM9ug), or giving ScamGuard a moderation role."
        elif (Reason == BanResult.Error or Reason == BanResult.BansExceeded):
            ErrorMsg = "ScamGuard encountered an unknown error"
            ResolutionMsg = "This can happen when the Discord API has a hiccup, a ban will retry again soon."
        else:
            return
        
        BanStr:str = "ban" if IsBan else "unban"
        User:discord.User|discord.Member|None = await self.LookupUser(UserId, Server)
        FailureEmbed:discord.Embed = self.CreateBaseEmbed(f"WARNING: Failed to {BanStr} user!")
        FailureEmbed.color = discord.Colour.dark_red()
        if (User is not None):
            FailureEmbed.add_field(name="User", value=User.mention)
        
        FailureEmbed.add_field(name="User ID", value=f"{UserId}")
        FailureEmbed.add_field(name="Is Ban", value=f"{IsBan}")
        FailureEmbed.add_field(inline=False, name="Error Code", value=ErrorMsg)
        FailureEmbed.add_field(inline=False, name="Resolution", value=ResolutionMsg)
        FailureEmbed.add_field(inline=False, name="Help Links", value="[Support Server](https://scamguard.app/discord) | [FAQ](https://scamguard.app/faq)")
        FailureEmbed.set_footer(text="scamguard.app")
        await DiscordChannel.send(embed=FailureEmbed) # type: ignore
        Logger.Log(LogLevel.Notice, f"A ban failure message was sent to {ServerIDStr} for the user id {UserId}")