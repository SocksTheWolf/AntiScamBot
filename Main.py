from Logger import Logger, LogLevel
from BotEnums import BanLookup
from Config import Config
from CommandHelpers import TargetIdTransformer, CommandErrorHandler
from discord import app_commands, Interaction, Guild, Member, Embed, Object, Webhook
import BotSetup
from DiscordBot import DiscordScamBot
from ConfirmBanView import ConfirmBan

ConfigData=Config()
CommandControlServer=Object(id=ConfigData["ControlServer"])

ScamBot = DiscordScamBot()

@ScamBot.Commands.command(name="backup", description="Backs up the current database", guild=CommandControlServer)
@app_commands.checks.has_role(ConfigData["MaintainerRole"])
async def BackupCommand(interaction:Interaction):
    if (ScamBot.Database.Backup()):
        await interaction.response.send_message("Backed up current database")
    else:
        await interaction.response.send_message("Failed to backup database!")
    
@ScamBot.Commands.command(name="forceleave", description="Makes the bot force leave a server", guild=CommandControlServer)
@app_commands.checks.has_role(ConfigData["MaintainerRole"])
@app_commands.describe(server='Discord ID of the server to leave')
async def LeaveServer(interaction:Interaction, server:app_commands.Transform[int, TargetIdTransformer]):
    if (server <= -1):
        await interaction.response.send_message("Invalid id!", ephemeral=True)
        return
    
    ServerToLeave:Guild = ScamBot.get_guild(server)
    if (ServerToLeave is not None):
        Logger.Log(LogLevel.Notice, f"We have left the server {ServerToLeave.name}[{server}]")
        await ServerToLeave.leave()
        await interaction.response.send_message(f"I am leaving server {server}")
    else:
        await interaction.response.send_message(f"Could not find server {server}, id is invalid")

@ScamBot.Commands.command(name="forceactivate", description="Force activates a server for the bot", guild=CommandControlServer)
@app_commands.checks.has_role(ConfigData["MaintainerRole"])
@app_commands.describe(server='Discord ID of the server to force activate')
async def ForceActivate(interaction:Interaction, server:app_commands.Transform[int, TargetIdTransformer]):
    if (server <= -1):
        await interaction.response.send_message("Invalid id!", ephemeral=True)
        return
    
    ServerToProcess:Guild = ScamBot.get_guild(server)
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
async def RetryActions(interaction:Interaction, server:app_commands.Transform[int, TargetIdTransformer], numactions:app_commands.Range[int, 1]):
    if (server <= -1):
        await interaction.response.send_message("Invalid id!", ephemeral=True)
        return
    
    ServerToProcess:Guild = ScamBot.get_guild(server)
    if (ServerToProcess is None):
        await interaction.response.send_message(f"Could not look up {server} for retrying actions")
        return
    
    ScamBot.AddAsyncTask(ScamBot.ReprocessBansForServer(ServerToProcess, LastActions=numactions))
    ReturnStr:str = f"Reprocessing the last {numactions} actions in {ServerToProcess.name}..."
    Logger.Log(LogLevel.Notice, ReturnStr)
    await interaction.response.send_message(ReturnStr)
    
@ScamBot.Commands.command(name="print", description="Print stats and information about all bots in the server", guild=CommandControlServer)
@app_commands.checks.has_role(ConfigData["MaintainerRole"])
async def PrintServers(interaction:Interaction):
    ReplyStr:str = "I am in the following servers:\n"
    RowNum:int = 1
    NumBans:int = len(list(ScamBot.Database.GetAllBans()))
    ActivatedServers:int = 0
    QueryResults = list(ScamBot.Database.GetAllServers(False))
    for BotServers in QueryResults:
        ReplyStr += f"#{RowNum}: Server {BotServers.discord_server_id}, Owner {BotServers.discord_owner_user_id}, Activated {str(bool(BotServers.activation_state))}\n"
        RowNum += 1
        if (BotServers.activation_state):
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
async def ScamBan(interaction:Interaction, targetid:app_commands.Transform[int, TargetIdTransformer]):
    if (targetid <= -1):
        await interaction.response.send_message("Invalid id!", ephemeral=True)
        return 
    
    Sender:Member = interaction.user
    Logger.Log(LogLevel.Verbose, f"Scam ban message detected from {Sender} for {targetid}")
    # Check to see if the ban already exists
    if (not ScamBot.Database.DoesBanExist(targetid)):
        BanEmbed:Embed = await ScamBot.CreateBanEmbed(targetid)
        BanView:ConfirmBan = ConfirmBan(targetid, ScamBot)
        await interaction.response.defer(ephemeral=True, thinking=True)
        BanView.Hook = await interaction.followup.send(embed=BanEmbed, view=BanView, wait=True, ephemeral=True)
    else:
        Logger.Log(LogLevel.Log, f"The given id {targetid} is already banned.")
        await interaction.response.send_message(f"{targetid} already exists in the ban database")

@ScamBot.Commands.command(name="scamunban", description="Unbans a scammer", guild=CommandControlServer)
@app_commands.checks.has_role(ConfigData["ApproverRole"])
@app_commands.describe(targetid='The discord id for the user to unban')
async def ScamUnban(interaction:Interaction, targetid:app_commands.Transform[int, TargetIdTransformer]):
    if (targetid <= -1):
        await interaction.response.send_message("Invalid id!", ephemeral=True)
        return 

    Sender:Member = interaction.user
    Logger.Log(LogLevel.Verbose, f"Scam unban message detected from {Sender} for {targetid}")
    Result = await ScamBot.PrepareUnban(targetid, Sender)
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
async def ActivateServer(interaction:Interaction):
    Sender:Member = interaction.user
    SendersId:int = Sender.id
    ServersActivated = []
    ServersToActivate = []
    # Hold onto these objects, as activate is one of the most expensive commands if
    # we are running off a database that is mostly made of up unactivated servers.
    await interaction.response.defer(thinking=True)
    ResponseHook:Webhook = interaction.followup
    # Go through all servers that the bot is currently in.
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
                GuildMember:Member = await ScamBot.LookupUserInServer(ServerIn, SendersId)
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
    Logger.Log(LogLevel.Verbose, f"Finished crawling through all servers, found {len(ServersToActivate)} servers to activate.")
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
    await ResponseHook.send(MessageToRespond)
    
@ScamBot.Commands.command(name="deactivate", description="Deactivates a server and prevents any future ban information from being shared", guild=CommandControlServer)
async def DeactivateServer(interaction:Interaction):
    Sender:Member = interaction.user
    SendersId:int = Sender.id
    ServersToDeactivate = []
    ServersOwnedResult = ScamBot.Database.GetAllServersOfOwner(SendersId)
    for OwnerServers in ServersOwnedResult:
        if (OwnerServers.activation_state):
            ServersToDeactivate.append(OwnerServers.discord_server_id)

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

# Control server version of scamcheck
@ScamBot.Commands.command(name="scamcheck", description="In the control server, check to see if a discord id is banned", guild=CommandControlServer)
@app_commands.describe(target='The discord user id to check')
@app_commands.checks.cooldown(1, 3.0)
async def ScamCheck_Control(interaction:Interaction, target:app_commands.Transform[int, TargetIdTransformer]):
    if (target <= -1):
        await interaction.response.send_message("Invalid id!", ephemeral=True, delete_after=5.0)
        return
    
    ResponseEmbed:Embed = await ScamBot.CreateBanEmbed(target)
    await interaction.response.send_message(embed = ResponseEmbed)

# Global version of scamcheck
@ScamBot.Commands.command(name="scamcheck", description="Checks to see if a discord id is banned")
@app_commands.describe(target='The discord user id to check')
@app_commands.checks.has_permissions(ban_members=True)
@app_commands.checks.cooldown(1, 5.0)
@app_commands.guild_only()
async def ScamCheck_Global(interaction:Interaction, target:app_commands.Transform[int, TargetIdTransformer]):
    if (target <= -1):
        await interaction.response.send_message("Invalid id!", ephemeral=True, delete_after=5.0)
        return
    
    if (ScamBot.Database.IsActivatedInServer(interaction.guild_id)):
        ResponseEmbed:Embed = await ScamBot.CreateBanEmbed(target)
        await interaction.response.send_message(embed = ResponseEmbed)
    else:
        await interaction.response.send_message("You must be activated in order to run scam check!")
        
ScamBot.Commands.on_error = CommandErrorHandler
ScamBot.run(ConfigData.GetToken())