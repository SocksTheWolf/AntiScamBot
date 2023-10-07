# Logging functionality
from Logger import Logger, LogLevel
from BotEnums import BanResult, BanLookup
from Config import Config
# Discord library
import discord
from discord import app_commands
import asyncio
import BotSetup
from BotDatabase import ScamBotDatabase

# Setup functions
ConfigData=Config()
CommandControlServer=discord.Object(id=ConfigData["ControlServer"])

class DiscordScamBot(discord.Client):
    # Channel to send updates as to when someone is banned/unbanned
    AnnouncementChannel = None
    # Channel that serves for notifications on bot activity/errors/warnings
    NotificationChannel = None
    Database:ScamBotDatabase = None
    AsyncTasks = set()

    ### Initialization ###
    def __init__(self, *args, **kwargs):
        self.Database = ScamBotDatabase()
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.Commands = app_commands.CommandTree(self)
        
    def __del__(self):
        Logger.Log(LogLevel.Notice, "Closing the discord scam bot")
        self.Database.Close()
        
    async def setup_hook(self):
        if (ConfigData.IsDevelopment()):
            # This copies the global commands over to your guild.
            self.Commands.copy_global_to(guild=CommandControlServer)
        else:
            await self.Commands.sync(guild=CommandControlServer)
            await self.Commands.sync()

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
            UserData.add_field(name="User", value=User.display_name)
            UserData.add_field(name="User Handle", value=User.mention)
            UserData.set_thumbnail(url=User.display_avatar.url)
        
        UserData.add_field(name="Banned", value=f"{UserBanned}")
        
        # Figure out who banned them
        if (UserBanned):
            # BannerName, BannerId, Date
            UserData.add_field(name="Banned By", value=f"{BanData[0]}")
            UserData.add_field(name="Time", value=f"{BanData[2]}", inline=False)
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
            OwnerName = server.owner.global_name
        
        Logger.Log(LogLevel.Notice, f"Bot has joined server {server.name} [{server.id}] of owner {OwnerName}[{server.owner_id}]")
        
    async def on_guild_update(self, PriorUpdate:discord.Guild, NewUpdate:discord.Guild):
        NewOwnerId:int = NewUpdate.owner_id
        if (PriorUpdate.owner_id != NewOwnerId):
            self.Database.SetNewServerOwner(NewUpdate.id, NewOwnerId)
            Logger.Log(LogLevel.Notice, f"Detected that the server {PriorUpdate.name} is now owned by {NewOwnerId}")
        
    async def on_guild_remove(self, server:discord.Guild):
        self.Database.RemoveServerEntry(server.id)
        OwnerName:str = "Admin"
        if (server.owner is not None):
            OwnerName = server.owner.global_name
        Logger.Log(LogLevel.Notice, f"Bot has been removed from server {server.name} [{server.id}] of owner {OwnerName}[{server.owner_id}]")
    
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
        
        BanReason=f"Reported {ScamStr} by {Sender.name}"
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

ScamBot = DiscordScamBot()

class TargetIdTransformer(app_commands.Transformer):
    async def transform(self, interaction: discord.Interaction, value: str) -> int:
        if (not value.isnumeric()):
            return -1
        ConvertedValue:int = int(value)
        # Prevent any targets on the bot
        if (ConvertedValue == interaction.client.user.id):
            return -1
        return ConvertedValue

async def CommandErrorHandler(interaction: discord.Interaction, error: app_commands.AppCommandError):
    ErrorType = type(error)
    ErrorMsg:str = ""
    InteractionName:str = interaction.command.name
    if (ErrorType == app_commands.CommandOnCooldown):
        ErrorMsg = f"This command {InteractionName} is currently on cooldown"
    elif (ErrorType == app_commands.MissingPermissions):
        ErrorMsg = f"You do not have permissions to use {InteractionName}"
    elif (ErrorType == app_commands.MissingRole):
        ErrorMsg = f"You are missing the roles necessary to run {InteractionName}"
    else:
        Logger.Log(LogLevel.Error, f"Encountered error running command {InteractionName}: {str(error)}")
        ErrorMsg = "An error has occurred while processing your request"
    
    await interaction.response.send_message(ErrorMsg, ephemeral=True, delete_after=5.0)

ScamBot.Commands.on_error = CommandErrorHandler

@ScamBot.Commands.command(name="backup", description="Backs up the current database", guild=CommandControlServer)
@app_commands.checks.has_role(ConfigData["MaintainerRole"])
async def BackupCommand(interaction:discord.Interaction):
    ScamBot.Database.Backup()
    await interaction.response.send_message("Backed up current database")
    
@ScamBot.Commands.command(name="forceleave", description="Makes the bot force leave a server", guild=CommandControlServer)
@app_commands.checks.has_role(ConfigData["MaintainerRole"])
@app_commands.describe(server='Discord ID of the server to leave')
async def LeaveServer(interaction:discord.Interaction, server:app_commands.Transform[int, TargetIdTransformer]):
    if (server <= -1):
        await interaction.response.send_message("Invalid id!", ephemeral=True)
        return
    
    ServerToLeave:discord.Guild = ScamBot.get_guild(server)
    if (ServerToLeave is not None):
        Logger.Log(LogLevel.Notice, f"We have left the server {ServerToLeave.name}[{server}]")
        await ServerToLeave.leave()
        await interaction.response.send_message(f"I am leaving server {server}")
    else:
        await interaction.response.send_message(f"Could not find server {server}, id is invalid")

@ScamBot.Commands.command(name="forceactivate", description="Force activates a server for the bot", guild=CommandControlServer)
@app_commands.checks.has_role(ConfigData["MaintainerRole"])
@app_commands.describe(server='Discord ID of the server to force activate')
async def ForceActivate(interaction:discord.Interaction, server:app_commands.Transform[int, TargetIdTransformer]):
    if (server <= -1):
        await interaction.response.send_message("Invalid id!", ephemeral=True)
        return
    
    ServerToProcess:discord.Guild = ScamBot.get_guild(server)
    if (ServerToProcess is not None):
        Logger.Log(LogLevel.Notice, f"Reprocessing bans for server {ServerToProcess.name} from {interaction.user.id}")
        ScamBot.AddAsyncTask(ScamBot.ReprocessBansForServer(ServerToProcess))
        ServersActivated = [server]
        ScamBot.Database.SetBotActivationForOwner(ServerToProcess.owner_id, ServersActivated, True)
        await interaction.response.send_message(f"Reprocessing bans for {ServerToProcess.name}")
    else:
        await interaction.response.send_message(f"I am unable to resolve that server id!")
        Logger.Log(LogLevel.Warn, f"Unable to resolve server {server} for reprocess")

@ScamBot.Commands.command(name="retryactions", description="Forces the bot to retry last actions", guild=CommandControlServer)
@app_commands.checks.has_role(ConfigData["MaintainerRole"])
@app_commands.describe(server='Discord ID of the server to force activate', numactions='The number of actions to perform')
async def RetryActions(interaction:discord.Interaction, server:app_commands.Transform[int, TargetIdTransformer], numactions:app_commands.Range[int, 1]):
    if (server <= -1):
        await interaction.response.send_message("Invalid id!", ephemeral=True)
        return
    
    ServerToProcess:discord.Guild = ScamBot.get_guild(server)
    if (ServerToProcess is None):
        await interaction.response.send_message(f"Could not look up {server} for retrying actions")
        return
    
    ScamBot.AddAsyncTask(ScamBot.ReprocessBansForServer(ServerToProcess, LastActions=numactions))
    ReturnStr:str = f"Reprocessing the last {numactions} actions in {ServerToProcess.name}..."
    Logger.Log(LogLevel.Notice, ReturnStr)
    await interaction.response.send_message(ReturnStr)
    
@ScamBot.Commands.command(name="print", description="Print stats and information about all bots in the server", guild=CommandControlServer)
@app_commands.checks.has_role(ConfigData["MaintainerRole"])
async def PrintServers(interaction:discord.Interaction):
    ReplyStr:str = "I am in the following servers:\n"
    RowNum:int = 1
    NumBans:int = len(ScamBot.Database.GetAllBans())
    ActivatedServers:int = 0
    QueryResults = ScamBot.Database.GetAllServers(False)
    for BotServers in QueryResults:
        IsActivated:bool = bool(BotServers[2])
        ReplyStr += f"#{RowNum}: Server {BotServers[0]}, Owner {BotServers[1]}, Activated {str(IsActivated)}\n"
        RowNum += 1
        if (IsActivated):
            ActivatedServers += 1
    # Final formatting
    ReplyStr = f"{ReplyStr}\nNumServers DB: {len(QueryResults)} | Discord: {len(ScamBot.guilds)} | Num Activated: {ActivatedServers} | Num Bans: {NumBans}"
    # Split the string so that it fits properly into discord messaging
    MessageChunkLen:int = 2000
    MessageChunks = [ReplyStr[i:i+MessageChunkLen] for i in range(0, len(ReplyStr), MessageChunkLen)]
    for MessageChunk in MessageChunks:
        await interaction.channel.send(MessageChunk)
        
    await interaction.response.send_message("Done printing", ephemeral=True, delete_after=2.0)

@ScamBot.Commands.command(name="scamban", description="Bans a scammer", guild=CommandControlServer)
@app_commands.checks.has_role(ConfigData["ApproverRole"])
@app_commands.describe(targetid='The discord id for the user to ban')
async def ScamBan(interaction:discord.Interaction, targetid:app_commands.Transform[int, TargetIdTransformer]):
    if (targetid <= -1):
        await interaction.response.send_message("Invalid id!", ephemeral=True)
        return 
    
    Sender:discord.Member = interaction.user
    Logger.Log(LogLevel.Verbose, f"Scam ban message detected from {Sender} for {targetid}")
    Result = await ScamBot.PrepareBan(targetid, Sender)
    ResponseMsg:str = ""
    if (Result is not BanLookup.Banned):
        if (Result == BanLookup.Duplicate):
            ResponseMsg = f"{targetid} already exists in the ban database"
            Logger.Log(LogLevel.Log, f"The given id {targetid} is already banned.")
        else:
            ResponseMsg = f"The given id {targetid} had an error while banning!"
            Logger.Log(LogLevel.Warn, f"{Sender} attempted ban on {targetid} with error {str(Result)}")
    else:
        ResponseMsg = f"The ban for {targetid} is in progress..."
        
    await interaction.response.send_message(ResponseMsg)

@ScamBot.Commands.command(name="scamunban", description="Unbans a scammer", guild=CommandControlServer)
@app_commands.checks.has_role(ConfigData["ApproverRole"])
@app_commands.describe(targetid='The discord id for the user to unban')
async def ScamUnban(interaction:discord.Interaction, targetid:app_commands.Transform[int, TargetIdTransformer]):
    if (targetid <= -1):
        await interaction.response.send_message("Invalid id!", ephemeral=True)
        return 

    Sender:discord.Member = interaction.user
    Logger.Log(LogLevel.Verbose, f"Scam unban message detected from {Sender} for {targetid}")
    Result = await ScamBan.PrepareUnban(targetid, Sender)
    ResponseMsg:str = ""
    if (Result is not BanLookup.Unbanned):
        if (Result is BanLookup.NotExist):
            ResponseMsg = f"The given id {targetid} is not an user we have in our database when unbanning!"
            Logger.Log(LogLevel.Log, f"The given id {targetid} is not in the ban database.")
        else:
            ResponseMsg = f"The given id {targetid} had an error while unbanning!"
            Logger.Log(LogLevel.Warn, f"{Sender} attempted unban on {targetid} with error {str(Result)}")
    else:
        ResponseMsg = f"The unban for {targetid} is in progress..."
        
    await interaction.response.send_message(ResponseMsg)
        
@ScamBot.Commands.command(name="activate", description="Activates a server and brings in previous bans if caller has any known servers owned", guild=CommandControlServer)
async def ActivateServer(interaction:discord.Interaction):
    Sender:discord.Member = interaction.user
    SendersId:int = Sender.id
    ServersActivated = []
    ServersToActivate = []
    for ServerIn in ScamBot.guilds:
        ServerId:int = ServerIn.id
        ServerInfo:str = f"{ServerIn.name}[{ServerIn.id}]"
        # Look for anything that is currently not activated
        if (not ScamBot.Database.IsActivatedInServer(ServerId)):
            Logger.Log(LogLevel.Debug, f"Activation looking in mutual server {ServerInfo}")
            # Any owners = easy activation :)
            if (ServerIn.owner_id == SendersId):
                Logger.Log(LogLevel.Verbose, f"User owns server {ServerInfo}")
                ServersToActivate.append(ServerIn)
            else:
                # Otherwise we have to look up the user's membership/permissions in the server
                GuildMember:discord.Member = await ScamBot.LookupUserInServer(ServerIn, SendersId)
                if (GuildMember is not None):
                    Logger.Log(LogLevel.Verbose, f"Found user in guild {ServerInfo}")
                    if (ScamBot.UserHasElevatedPermissions(GuildMember)):
                        Logger.Log(LogLevel.Verbose, f"User has the appropriate permissions in server {ServerInfo}")
                        ServersToActivate.append(ServerIn)
                    else:
                        Logger.Log(LogLevel.Debug, f"User does not have the permissions...")
                else:
                    Logger.Log(LogLevel.Debug, f"Did not get user information for {ServerInfo}, likely not in there")
        else:
            Logger.Log(LogLevel.Debug, f"Bot is already activated in {ServerId}")

    # Take all the servers that we found and process them
    for WorkServer in ServersToActivate:
        if (WorkServer is not None):
            ScamBot.AddAsyncTask(ScamBot.ReprocessBansForServer(WorkServer))
            ServersActivated.append(WorkServer.id)
    
    NumServersActivated:int = len(ServersActivated)
    MessageToRespond:str = ""
    if (NumServersActivated >= 1):
        ScamBot.Database.SetBotActivationForOwner(SendersId, ServersActivated, True)
        MessageToRespond = f"Activated in {NumServersActivated} of your servers!"
    elif (len(ScamBot.Database.GetAllServersOfOwner(SendersId)) == 0):
        # make sure that people have added the bot into the server first
        MessageToRespond = "I am not in any servers that you own! You must add me to your server before activating."
    else:
        MessageToRespond = "There are no servers that you own that aren't already activated!"
    await interaction.response.send_message(MessageToRespond)
    
@ScamBot.Commands.command(name="deactivate", description="Deactivates a server and prevents any future ban information from being shared", guild=CommandControlServer)
async def DeactivateServer(interaction:discord.Interaction):
    Sender:discord.Member = interaction.user
    SendersId:int = Sender.id
    ServersToDeactivate = []
    ServersOwnedResult = ScamBot.Database.GetAllServersOfOwner(SendersId)
    for OwnerServers in ServersOwnedResult:
        if (OwnerServers[0] == 1):
            ServersToDeactivate.append(OwnerServers[1])

    MessageToRespond:str = ""
    NumServersDeactivated:int = len(ServersToDeactivate)
    if (NumServersDeactivated >= 1):
        ScamBot.Database.SetBotActivationForOwner(SendersId, ServersToDeactivate, False)
        MessageToRespond = f"Deactivated in {NumServersDeactivated} of your servers!"
    elif (len(ServersOwnedResult) == 0):
        # make sure that people have added the bot into the server first
        MessageToRespond = "I am not in any servers that you own!"
    else:
        MessageToRespond = "There are no servers that you own that are activated!"
    await interaction.response.send_message(MessageToRespond)
    
@ScamBot.Commands.command(name="scamcheck", description="Checks to see if a discord id is banned")
@app_commands.describe(targetid='The discord user id to check')
@app_commands.checks.cooldown(1, 3.0)
@app_commands.guild_only()
async def ScamCheck(interaction:discord.Interaction, targetid:app_commands.Transform[int, TargetIdTransformer]):
    if (targetid <= -1):
        await interaction.response.send_message("Invalid id!", ephemeral=True)
        return
    
    if (ScamBot.Database.IsActivatedInServer(interaction.guild_id)):
        ResponseEmbed:discord.Embed = await ScamBot.CreateBanEmbed(targetid)
        await interaction.response.send_message(embed = ResponseEmbed)
    else:
        await interaction.response.send_message("You must be activated in order to run scam check!")

ScamBot.run(ConfigData.GetToken())