from datetime import datetime
# Logging functionality
from Logger import Logger, LogLevel
from BotEnums import CommandPermission, BanResult, BanLookup
from Config import Config
# Discord library
import discord
import asyncio
import BotSetup
from BotDatabase import ScamBotDatabase

# Setup functions
ConfigData=Config()

# TODO:
# * Something that cleans up the database in the future based off of if the scam accounts are deleted

class DiscordScamBot(discord.Client):
    ControlServer = None
    ApproverRole = None
    MaintainerRole = None
    DeveloperRole = None
    # Channel to send updates as to when someone is banned/unbanned
    # this is an announcement channel
    AnnouncementChannel = None
    # Channel that serves for notifications on bot activity/errors/warnings
    NotificationChannel = None
    Database:ScamBotDatabase = None
    AsyncTasks = set()
    CommandList = [("?scamban", True, CommandPermission.Approver, "Bans a scammer using `?scamban targetid`"), 
                   ("?scamunban", True, CommandPermission.Approver, "Unbans a scammer using `?scamunban targetid`"), 
                   ("?scamcheck", True, CommandPermission.Anyone, "Checks to see if a discord id is banned `?scamcheck targetid`"), 
                   ("?activate", False, CommandPermission.ControlServerUser, "Activates a server and brings in previous bans if caller has any known servers owned"),
                   ("?deactivate", False, CommandPermission.ControlServerUser, "Deactivates a server and prevents any future ban information from being shared"),
                   ("?reloadconfig", False, CommandPermission.Maintainer, "Reloads the active bot's configuration data"),
                   ("?forceactivate", True, CommandPermission.Maintainer, "Force reprocesses a server for activation `?forceactivate serverid`"),
                   ("?print", False, CommandPermission.Maintainer, "Prints the servers that the bot is currently in"), 
                   ("?reloadservers", False, CommandPermission.Maintainer, "Regenerates the server database"), 
                   ("?commands", False, CommandPermission.Anyone, "Prints this list")]

    ### Initialization ###
    def __init__(self, *args, **kwargs):
        self.Database = ScamBotDatabase()
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        
    def __del__(self):
        Logger.Log(LogLevel.Notice, "Closing the discord scam bot")
        self.Database.Close()

    ### Config Handling ###
    def ProcessConfig(self, ShouldReload:bool):
        if (ShouldReload):
            ConfigData.Load()
        
        # Grab our control server
        if (ConfigData.IsValid("ControlServer", int)):
            self.ControlServer = self.get_guild(ConfigData["ControlServer"])
        else:
            Logger.Log(LogLevel.Error, "Missing the ControlServer configuration!")
            return
        
        # Pull the approver role
        if (ConfigData.IsValid("ApproverRole", int)):
            self.ApproverRole = self.ControlServer.get_role(ConfigData["ApproverRole"])
        else:
            Logger.Log(LogLevel.Error, "Missing the ApproverRole configuration!")
            return
        
        if (ConfigData.IsValid("AnnouncementChannel", int)):
            self.AnnouncementChannel = self.get_channel(ConfigData["AnnouncementChannel"])
        if (ConfigData.IsValid("NotificationChannel", int)):
            self.NotificationChannel = self.get_channel(ConfigData["NotificationChannel"])
        if (ConfigData.IsValid("MaintainerRole", int)):
            self.MaintainerRole = self.ControlServer.get_role(ConfigData["MaintainerRole"])
        if (ConfigData.IsValid("DeveloperRole", int)):
            self.DeveloperRole = self.ControlServer.get_role(ConfigData["DeveloperRole"])
        
        Logger.Log(LogLevel.Notice, "Bot configs applied")

    ### Command Processing & Utils ###
    def ParseCommand(self, text:str):
        for CommandTuple in self.CommandList:
            if (text.startswith(CommandTuple[0])):
                Arguments = text.split(" ")
                Arguments.pop(0)
                return (True, CommandTuple[0], CommandTuple[1], Arguments)
        return (False, "", False, [])
    
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
        
    async def on_guild_remove(self, server:discord.Guild):
        self.Database.RemoveServerEntry(server.id)
        OwnerName:str = "Admin"
        if (server.owner is not None):
            OwnerName = server.owner.global_name
        Logger.Log(LogLevel.Notice, f"Bot has been removed from server {server.name} [{server.id}] of owner {OwnerName}[{server.owner_id}]")
        
    async def on_message(self, message):
        # Prevent the bot from processing its own messages
        if (message.author.id == self.user.id):
            return
        
        MessageContents:str = message.content.lower()
        # If not a command, get out of here
        if (not MessageContents.startswith("?")):
            return
        
        CommandParse = self.ParseCommand(MessageContents)
        # If the command is not for us, then stop processing
        if (not CommandParse[0]):
            return
        
        Command = CommandParse[1]
        RequiresArguments = CommandParse[2]
        ArgList = CommandParse[3]
        TargetId:int = -1
        # Check if this command requires arguments
        if (RequiresArguments):
            # Not enough arguments were provided!
            if (len(ArgList) < 1):
                await message.reply(f"The command you have specified, {Command}, requires arguments!")
                Logger.Log(LogLevel.Debug, f"Command {Command} requires arguments but none were provided")
                return
            
            TargetIdStr:str = CommandParse[3][0]
            if (not TargetIdStr.isnumeric()):
                await message.reply("The format of this command is incorrect, the userid should be the second value")
                return
            
            # Set the target id properly
            TargetId = int(TargetIdStr)
            
            # Prevent any targets on the bot
            if (TargetId == self.user.id):
                return
        
        # Do not accept DMs, only channel messages
        if (message.guild is None):
            Logger.Log(LogLevel.Debug, f"There is no guild for this server instance!")
            return
        
        Sender:discord.Member = message.author      
        # Senders must also be discord server members, not random users
        if (type(Sender) is not discord.Member):
            Logger.Log(LogLevel.Debug, f"User is not a discord member, this must be a DM")
            return
        
        SendersId:int = Sender.id
        InControlServer:bool = (message.guild == self.ControlServer)
        IsApprover:bool = False
        IsMaintainer:bool = False
        IsDeveloper:bool = False
        # Do two if checks here, we want to make sure that we do role checks only
        # if we are in the control server to prevent potential overlap of role ids
        if (InControlServer):
            if (self.ApproverRole in Sender.roles):
                IsApprover = True
                
            if (self.MaintainerRole is not None and self.MaintainerRole in Sender.roles):
                IsMaintainer = True
                
            if (self.DeveloperRole is not None and self.DeveloperRole in Sender.roles):
                IsDeveloper = True
                
        if (InControlServer):       
            # If the first bit of the message is the command to ban
            if (Command.startswith("?scamban")):
                if (IsApprover):
                    Logger.Log(LogLevel.Verbose, f"Scam ban message detected from {Sender} for {TargetId}")
                    Result = await self.PrepareBan(TargetId, Sender)
                    if (Result is not BanLookup.Banned):
                        if (Result == BanLookup.Duplicate):
                            await message.reply(f"{TargetId} already exists in the ban database")
                            Logger.Log(LogLevel.Log, f"The given id {TargetId} is already banned.")
                        else:
                            await message.reply(f"The given id {TargetId} had an error while banning!")
                            Logger.Log(LogLevel.Warn, f"{Sender} attempted ban on {TargetId} with error {str(Result)}")
                    else:
                        await message.reply(f"The ban for {TargetId} is in progress...")
                else:
                    Logger.Log(LogLevel.Warn, f"A scam ban message was sent by a non-admin from {Sender} for {TargetId}")
                return
            elif (Command.startswith("?scamunban")):
                if (IsApprover):
                    Logger.Log(LogLevel.Verbose, f"Scam unban message detected from {Sender} for {TargetId}")
                    Result = await self.PrepareUnban(TargetId, Sender)
                    if (Result is not BanLookup.Unbanned):
                        if (Result is BanLookup.NotExist):
                            await message.reply(f"The given id {TargetId} is not an user we have in our database when unbanning!")
                            Logger.Log(LogLevel.Log, f"The given id {TargetId} is not in the ban database.")
                        else:
                            await message.reply(f"The given id {TargetId} had an error while unbanning!")
                            Logger.Log(LogLevel.Warn, f"{Sender} attempted unban on {TargetId} with error {str(Result)}")
                    else:
                        await message.reply(f"The unban for {TargetId} is in progress...")
                else:
                    Logger.Log(LogLevel.Warn, f"A scam unban message was sent by a non-admin from {Sender} for {TargetId}")

                return
            elif (Command.startswith("?activate")):
                ServersActivated = []
                ServersOwnedResult = self.Database.GetAllServersOfOwner(SendersId)
                for OwnerServers in ServersOwnedResult:
                    ServerId:int = OwnerServers[1]
                    # Check if not activated
                    if (OwnerServers[0] == 0):
                        server = self.get_guild(ServerId)
                        if (server is not None):
                            self.AddAsyncTask(self.ReprocessBansForServer(server))
                            ServersActivated.append(ServerId)
                
                NumServersActivated:int = len(ServersActivated)
                if (NumServersActivated >= 1):
                    self.Database.SetBotActivationForOwner(SendersId, ServersActivated, True)
                    await message.reply(f"Activated in {NumServersActivated} of your servers!")
                elif (len(ServersOwnedResult) == 0):
                    # make sure that people have added the bot into the server first
                    await message.reply("I am not in any servers that you own! You must add me to your server before activating.")
                else:
                    await message.reply("There are no servers that you own that aren't already activated!")
                return
            elif (Command.startswith("?deactivate")):
                ServersToDeactivate = []
                ServersOwnedResult = self.Database.GetAllServersOfOwner(SendersId)
                for OwnerServers in ServersOwnedResult:
                    if (OwnerServers[0] == 1):
                        ServersToDeactivate.append(OwnerServers[1])
                
                NumServersDeactivated:int = len(ServersToDeactivate)
                if (NumServersDeactivated >= 1):
                    self.Database.SetBotActivationForOwner(SendersId, ServersToDeactivate, False)
                    await message.reply(f"Deactivated in {NumServersDeactivated} of your servers!")
                elif (len(ServersOwnedResult) == 0):
                    # make sure that people have added the bot into the server first
                    await message.reply("I am not in any servers that you own!")
                else:
                    await message.reply("There are no servers that you own that are activated!")
                return
            elif (Command.startswith("?reloadconfig")):
                if (IsMaintainer):
                    self.ProcessConfig(True)
                    await message.reply("Configurations reloaded")
                else:
                    await message.reply("You are not allowed to use that command!")
                    Logger.Log(LogLevel.Error, f"User {Sender} attempted to reload config without proper permissions!")
                return
            elif (Command.startswith("?reloadservers")):
                if (IsMaintainer):
                    self.Database.Open()
                    self.Database.ReconcileServers(self.guilds)
                    await message.reply("Server list reloaded")
                else:
                    await message.reply("You are not allowed to use that command!")
                    Logger.Log(LogLevel.Error, f"User {Sender} attempted to reload servers without proper permissions!")
                return
            elif (Command.startswith("?forceactivate")):
                if (IsMaintainer):
                    ServerToProcess = self.get_guild(TargetId)
                    if (ServerToProcess is not None):
                        Logger.Log(LogLevel.Notice, f"Reprocessing bans for server {ServerToProcess.name} from {SendersId}")
                        self.AddAsyncTask(self.ReprocessBansForServer(ServerToProcess))
                        ServersActivated = [TargetId]
                        self.Database.SetBotActivationForOwner(ServerToProcess.owner_id, ServersActivated, True)
                        await message.reply(f"Reprocessing bans for {ServerToProcess.name}")
                    else:
                        await message.reply(f"I am unable to resolve that server id!")
                        Logger.Log(LogLevel.Warn, f"Unable to resolve server {TargetId} for reprocess")
                else:
                    await message.reply("You are not allowed to use that command!")
                    Logger.Log(LogLevel.Error, f"User {Sender} attempted to reload server bans for {TargetId} without permissions!")
                return
            elif (Command.startswith("?print")):
                if (IsMaintainer):
                    ReplyStr:str = "I am in the following servers:\n"
                    RowNum:int = 1
                    ActivatedServers:int = 0
                    QueryResults = self.Database.GetAllServers(False)
                    for BotServers in QueryResults:
                        IsActivated:bool = bool(BotServers[2])
                        ReplyStr += f"#{RowNum}: Server {BotServers[0]}, Owner {BotServers[1]}, Activated {str(IsActivated)}\n"
                        RowNum += 1
                        if (IsActivated):
                            ActivatedServers += 1
                    # Final formatting
                    ReplyStr = f"{ReplyStr}\nNumServers DB: {len(QueryResults)} | Discord: {len(self.guilds)} | Num Activated: {ActivatedServers}"
                    # Split the string so that it fits properly into discord messaging
                    MessageChunkLen:int = 2000
                    MessageChunks = [ReplyStr[i:i+MessageChunkLen] for i in range(0, len(ReplyStr), MessageChunkLen)]
                    for MessageChunk in MessageChunks:
                        await message.channel.send(MessageChunk)
                return
            
        if (Command.startswith("?scamcheck")):
            if (self.Database.IsActivatedInServer(message.guild.id)):
                ResponseEmbed:discord.Embed = await self.CreateBanEmbed(TargetId)
                await message.reply(embed = ResponseEmbed)
            else:
                await message.reply("You must activate your server to use commands!")
        elif (Command.startswith("?commands")):
            CommandResponse:str = "The list of commands are: \n"
            for CommandData in self.CommandList:
                CommandLevel = CommandData[2]
                Usable:bool = CommandPermission.CanUse(CommandLevel, InControlServer, IsApprover, IsMaintainer, IsDeveloper)
                if (Usable):
                    CommandResponse += f"* `{CommandData[0]}`: Access[**{CommandData[2]}**] - {CommandData[3]}\n"
                
            await message.reply(f"{CommandResponse}")
    
    ### Ban Handling ###
    async def ReprocessBansForServer(self, Server:discord.Guild) -> BanResult:
        ServerInfoStr:str = f"{Server.name}[{Server.id}]"
        BanReturn:BanResult = BanResult.Processed
        Logger.Log(LogLevel.Log, f"Attempting to import ban data to {ServerInfoStr}")
        NumBans:int = 0
        BanQueryResult = self.Database.GetAllBans()
        TotalBans:int = len(BanQueryResult)
        for Ban in BanQueryResult:
            UserId:int = int(Ban[0])
            UserToBan = discord.Object(UserId)
            BanResponse = await self.PerformActionOnServer(Server, UserToBan, "User banned by ScamBot", True)
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
        try:
            BanStr:str = "ban"
            if (not IsBan):
                BanStr = "unban"
            
            Logger.Log(LogLevel.Verbose, f"Performing {BanStr} action in {Server.name} owned by {ServerOwnerId}")
            if (BanId == ServerOwnerId):
                Logger.Log(LogLevel.Warn, f"{BanStr.title()} of {BanId} dropped for {Server.name} as it is the owner!")
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
        except(discord.Forbidden):
            Logger.Log(LogLevel.Error, f"We do not have ban/unban permissions in this server {Server.name} owned by {ServerOwnerId}!")
            return (False, BanResult.LostPermissions)
        except discord.HTTPException as ex:
            Logger.Log(LogLevel.Warn, f"We encountered an error {(str(ex))} while trying to perform for server {Server.name} owned by {ServerOwnerId}!")
        return (False, BanResult.Error)
        
    async def PropagateActionToServers(self, TargetId:int, Sender:discord.Member, IsBan:bool):
        NumServersPerformed:int = 0
        UserToWorkOn = discord.Object(TargetId)
        ScamStr:str = "scammer"
        if (not IsBan):
            ScamStr = "non-scammer"
        
        BanReason=f"Reported {ScamStr} by {Sender.name}"
        AllServers = self.Database.GetAllActivatedServers()
        #AllServers = self.guilds
        NumServers:int = len(AllServers)
        # Instead of going through all servers it's added to, choose all servers that are activated.
        for ServerData in AllServers:
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

        Logger.Log(LogLevel.Notice, f"Action execution on {TargetId} as a {ScamStr} performed in {NumServersPerformed}/{NumServers}")

Bot = DiscordScamBot()
Bot.run(ConfigData.GetToken())