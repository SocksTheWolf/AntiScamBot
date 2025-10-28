from Logger import Logger, LogLevel
from BotEnums import BanLookup, ModerationAction
from Config import Config
from CommandHelpers import TargetIdTransformer, ServerIdTransformer, CommandErrorHandler
from discord import app_commands, Interaction, User, Member, Embed, Object, Webhook
from BotSetup import SetupDatabases
from ScamGuard import ScamGuard
from ConfirmBanView import ConfirmBan

ConfigData:Config=Config()

if __name__ == '__main__':
    async def has_activation_intents(ctx):
        return ctx.client.intents.members
        
    CommandControlServer=Object(id=ConfigData["ControlServer"])
    ScamGuardBot = ScamGuard(ConfigData["ControlBotID"])
    
    @ScamGuardBot.Commands.command(name="info", description="ScamGuard Info", guild=CommandControlServer)
    @app_commands.checks.cooldown(1, 3.0)
    async def PrintScamInfo(interaction:Interaction):
        ReturnEmbed = ScamGuardBot.CreateInfoEmbed()
        await interaction.response.send_message(embed=ReturnEmbed, silent=True)

    @ScamGuardBot.Commands.command(name="backup", description="Backs up the current database", guild=CommandControlServer)
    @app_commands.checks.has_role(ConfigData["MaintainerRole"])
    async def BackupCommand(interaction:Interaction):
        if (ScamGuardBot.Database.Backup()):
            await interaction.response.send_message("Backed up current database")
        else:
            await interaction.response.send_message("Failed to backup database!")
        
    @ScamGuardBot.Commands.command(name="forceleave", description="Makes the bot force leave a server", guild=CommandControlServer)
    @app_commands.checks.has_role(ConfigData["MaintainerRole"])
    @app_commands.describe(server='Discord ID of the server to leave')
    async def LeaveServer(interaction:Interaction, server:app_commands.Transform[int, ServerIdTransformer]):
        if (server <= -1):
            await interaction.response.send_message("Invalid id!", ephemeral=True, delete_after=5.0)
            return
        
        if (ScamGuardBot.LeaveServer(server)):
            await interaction.response.send_message(f"Bot is attempting to leave server {server}")
        else:
            await interaction.response.send_message("Invalid id!", ephemeral=True, delete_after=5.0)


    @ScamGuardBot.Commands.command(name="forceactivate", description="Force activates a server for the bot", guild=CommandControlServer)
    @app_commands.checks.has_role(ConfigData["MaintainerRole"])
    @app_commands.describe(server='Discord ID of the server to force activate')
    async def ForceActivate(interaction:Interaction, server:app_commands.Transform[int, ServerIdTransformer]):
        if (server <= -1):
            await interaction.response.send_message("Invalid id!", ephemeral=True, delete_after=5.0)
            return
        
        if (ScamGuardBot.Database.IsInServer(server)):
            BotInstance:int|None = ScamGuardBot.Database.GetBotIdForServer(server)
            if (BotInstance is None):
                await interaction.response.send_message(f"Unable to find the bot instance for server {server}")
                return
            Logger.Log(LogLevel.Notice, f"Reprocessing bans for server {server} from {interaction.user.id}")
            ScamGuardBot.AddAsyncTask(ScamGuardBot.ReprocessBansForServer(server))
            ServersActivated = [server]
            ScamGuardBot.Database.SetBotActivationForOwner(ServersActivated, True, BotInstance, ActivatorId=interaction.user.id)
            await interaction.response.send_message(f"Reprocessing bans for {server}")
        else:
            await interaction.response.send_message(f"I am unable to resolve that server id!")
            Logger.Log(LogLevel.Warn, f"Unable to resolve server {server} for reprocess")

    @ScamGuardBot.Commands.command(name="retryactions", description="Forces the bot to retry last actions", guild=CommandControlServer)
    @app_commands.checks.has_role(ConfigData["MaintainerRole"])
    @app_commands.describe(server='Discord ID of the server to force activate', numactions='The number of actions to perform')
    async def RetryActions(interaction:Interaction, server:app_commands.Transform[int, ServerIdTransformer], numactions:app_commands.Range[int, 0]):
        if (server <= -1):
            await interaction.response.send_message("Invalid id!", ephemeral=True, delete_after=5.0)
            return
            
        ScamGuardBot.AddAsyncTask(ScamGuardBot.ReprocessBansForServer(server, LastActions=numactions))
        ReturnStr:str = f"Reprocessing the last {numactions} actions in {server}..."
        Logger.Log(LogLevel.Notice, ReturnStr)
        await interaction.response.send_message(ReturnStr)
        
    @ScamGuardBot.Commands.command(name="retryinstance", description="Forces the bot to retry last actions for instance", guild=CommandControlServer)
    @app_commands.checks.has_role(ConfigData["MaintainerRole"])
    @app_commands.describe(instance='Bot Instance ID to reimport', numactions='The number of actions to perform')
    async def RedoInstance(interaction:Interaction, instance:app_commands.Range[int, 0], numactions:app_commands.Range[int, 0]):
        ScamGuardBot.AddAsyncTask(ScamGuardBot.ReprocessBansForInstance(instance, LastActions=numactions))
        ReturnStr:str = f"Reprocessing the last {numactions} actions for instance {instance}"
        Logger.Log(LogLevel.Notice, ReturnStr)
        await interaction.response.send_message(ReturnStr)
        
    @ScamGuardBot.Commands.command(name="ping", description="Ping an instance", guild=CommandControlServer)
    @app_commands.checks.has_role(ConfigData["MaintainerRole"])
    @app_commands.describe(instance='Bot Instance ID to ping')
    async def PingInstance(interaction:Interaction, instance:app_commands.Range[int, 0]):
        ScamGuardBot.ClientHandler.SendPing(instance)
        await interaction.response.send_message(f"Pinged instance #{instance}", ephemeral=True, delete_after=2.0)
        
    @ScamGuardBot.Commands.command(name="print", description="Print stats and information about all bots in the server", guild=CommandControlServer)
    @app_commands.checks.has_role(ConfigData["MaintainerRole"])
    async def PrintServers(interaction:Interaction):
        ReplyStr:str = "I am in the following servers:\n"
        RowNum:int = 1
        NumBans:int = ScamGuardBot.Database.GetNumBans()
        ActivatedServers:int = 0
        await interaction.response.defer(thinking=True)
        ResponseHook:Webhook = interaction.followup
        QueryResults = ScamGuardBot.Database.GetAllServers()
        for BotServers in QueryResults:
            IsActivated:bool = bool(BotServers.activation_state)
            ReplyStr += f"#{RowNum}: Inst {BotServers.bot_instance_id}, Server {BotServers.discord_server_id}, Owner {BotServers.owner_discord_user_id}, Activated {str(IsActivated)}\n"
            RowNum += 1
            if (IsActivated):
                ActivatedServers += 1
        # Final formatting
        ReplyStr = f"{ReplyStr}\nNumServers DB: {len(QueryResults)} | Num Activated: {ActivatedServers} | Num Bans: {NumBans}"
        # Split the string so that it fits properly into discord messaging
        MessageChunkLen:int = 2000
        MessageChunks = [ReplyStr[i:i+MessageChunkLen] for i in range(0, len(ReplyStr), MessageChunkLen)]
        for MessageChunk in MessageChunks:
            await interaction.channel.send(MessageChunk) # type: ignore
            
        await ResponseHook.send("Done printing", ephemeral=True)

    @ScamGuardBot.Commands.command(name="scamban", description="Bans a scammer", guild=CommandControlServer)
    @app_commands.checks.has_role(ConfigData["ApproverRole"])
    @app_commands.describe(targetid='The discord id for the user to ban')
    async def ScamBan(interaction:Interaction, targetid:app_commands.Transform[int, TargetIdTransformer]):
        if (targetid <= -1):
            await interaction.response.send_message("Invalid id!", ephemeral=True, delete_after=5.0)
            return 
        
        Sender:User|Member = interaction.user
        Logger.Log(LogLevel.Verbose, f"Scam ban message detected from {Sender} for {targetid}")
        # Check to see if the ban already exists
        if (not ScamGuardBot.Database.DoesBanExist(targetid)):
            BanEmbed:Embed = await ScamGuardBot.CreateBanEmbed(targetid)
            BanView:ConfirmBan = ConfirmBan(targetid, ScamGuardBot)
            await interaction.response.defer(ephemeral=True, thinking=True)
            await BanView.Send(interaction, [BanEmbed])
        else:
            Logger.Log(LogLevel.Log, f"The given id {targetid} is already banned.")
            await interaction.response.send_message(f"{targetid} already exists in the ban database")

    @ScamGuardBot.Commands.command(name="scamunban", description="Unbans a scammer", guild=CommandControlServer)
    @app_commands.checks.has_role(ConfigData["ApproverRole"])
    @app_commands.describe(targetid='The discord id for the user to unban')
    async def ScamUnban(interaction:Interaction, targetid:app_commands.Transform[int, TargetIdTransformer]):
        if (targetid <= -1):
            await interaction.response.send_message("Invalid id!", ephemeral=True, delete_after=5.0)
            return 

        Sender:Member|User = interaction.user
        Logger.Log(LogLevel.Verbose, f"Scam unban message detected from {Sender} for {targetid}")
        Result:BanLookup = await ScamGuardBot.HandleBanAction(targetid, Sender, ModerationAction.Unban)
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
            
    @ScamGuardBot.Commands.command(name="activate", description="Activates a server and brings in previous bans if caller has any known servers owned", guild=CommandControlServer)
    @app_commands.check(has_activation_intents)
    async def ActivateServer(interaction:Interaction):
        Sender:Member|User = interaction.user
        SendersId:int = Sender.id

        # Hold onto these objects, as activate is one of the most expensive commands if
        # we are running off a database that is mostly made of up unactivated servers.
        await interaction.response.defer(thinking=True)
        ResponseHook:Webhook = interaction.followup
        
        ScamGuardBot.ClientHandler.SendActivationForServers(SendersId)
        await ScamGuardBot.ActivateServersWithPermissions(SendersId)
        await ResponseHook.send("Enqueued processing for activation for servers you own/moderate in")
        
    @ScamGuardBot.Commands.command(name="deactivate", description="Deactivates a server and prevents any future ban information from being shared", guild=CommandControlServer)
    @app_commands.check(has_activation_intents)
    async def DeactivateServer(interaction:Interaction):
        Sender:Member|User = interaction.user
        SendersId:int = Sender.id
        
        # Hold onto these objects, as activate is one of the most expensive commands if
        # we are running off a database that is mostly made of up unactivated servers.
        await interaction.response.defer(thinking=True)
        ResponseHook:Webhook = interaction.followup
        
        ScamGuardBot.ClientHandler.SendDeactivationForServers(SendersId)
        await ScamGuardBot.DeactivateServersWithPermissions(SendersId)
        await ResponseHook.send("Enqueued processing for deactivation for servers you own/moderate in")

    # Control server version of scamcheck
    @ScamGuardBot.Commands.command(name="scamcheck", description="In the control server, check to see if a discord id is banned", guild=CommandControlServer)
    @app_commands.describe(target='The discord user id to check')
    @app_commands.checks.cooldown(1, 1.0)
    async def ScamCheck_Control(interaction:Interaction, target:app_commands.Transform[int, TargetIdTransformer]):
        if (target <= -1):
            await interaction.response.send_message("Invalid id!", ephemeral=True, delete_after=5.0)
            return
        
        ResponseEmbed:Embed = await ScamGuardBot.CreateBanEmbed(target)
        await interaction.response.send_message(embed = ResponseEmbed)
        
    # Control Server command to set evidence threads
    @ScamGuardBot.Commands.command(name="setthread", description="In the control server, set the evidence thread for the given user id", guild=CommandControlServer)
    @app_commands.checks.has_role(ConfigData["ApproverRole"])
    async def SetThread_Control(interaction:Interaction, target:app_commands.Transform[int, TargetIdTransformer]):
        if (target <= -1):
            await interaction.response.send_message("Invalid id!", ephemeral=True, delete_after=5.0)
            return
        
        InteractionLocation:int|None = interaction.channel_id
        if (InteractionLocation is None):
            await interaction.response.send_message("This action can only be performed in channels or threads.", ephemeral=True)
            return
        
        if (not ScamGuardBot.Database.DoesBanExist(target)):
            await interaction.response.send_message("Cannot set an evidence thread on a non-ban at this time!", ephemeral=True)
            return
        
        ScamGuardBot.Database.SetEvidenceThread(target, InteractionLocation)
        await interaction.response.send_message(f"Updated the thread for {target} to <#{interaction.channel_id}>")
        Logger.Log(LogLevel.Log, f"Thread set for {target} to {interaction.channel_id}")
    
    # Togglers for curbing any potential abuse
    @ScamGuardBot.Commands.command(name="toggleserverban", description="In the control server, sets if the given server should have bans processed on them", guild=CommandControlServer)
    @app_commands.checks.has_role(ConfigData["MaintainerRole"])
    async def SetBanActionForServer_Control(interaction:Interaction, server:app_commands.Transform[int, ServerIdTransformer], state:bool):
        if (server <= -1):
            await interaction.response.send_message("Invalid id!", ephemeral=True, delete_after=5.0)
            return
        
        if (not ScamGuardBot.Database.IsInServer(server)):
            await interaction.response.send_message(f"ScamGuard is not in server {server}!", ephemeral=True, delete_after=5.0)    
            return
        
        ScamGuardBot.Database.ToggleServerBan(server, state)
        await interaction.response.send_message(f"Server {server} ban ability set to {state}", ephemeral=True, delete_after=10.0)
        Logger.Log(LogLevel.Log, f"Ban ability set for {server} to {state}")
        
    @ScamGuardBot.Commands.command(name="toggleserverreport", description="In the control server, sets if the given server should have bans processed on them", guild=CommandControlServer)
    @app_commands.checks.has_role(ConfigData["MaintainerRole"])
    async def SetReportActionForServer_Control(interaction:Interaction, server:app_commands.Transform[int, ServerIdTransformer], state:bool):
        if (server <= -1):
            await interaction.response.send_message("Invalid id!", ephemeral=True, delete_after=5.0)
            return
        
        if (not ScamGuardBot.Database.IsInServer(server)):
            await interaction.response.send_message(f"ScamGuard is not in server {server}!", ephemeral=True, delete_after=5.0)    
            return
        
        ScamGuardBot.Database.ToggleServerReport(server, state)
        await interaction.response.send_message(f"Server {server} report ability set to {state}", ephemeral=True, delete_after=10.0)
        Logger.Log(LogLevel.Log, f"Report ability set for {server} to {state}")
        
    @ScamGuardBot.Commands.command(name="inactivecleanup", description="In the control server, cleans up any servers where we don't have correct permissions", guild=CommandControlServer)
    @app_commands.checks.has_role(ConfigData["MaintainerRole"])
    async def CleanupInactiveServers_Control(interaction:Interaction, dryrun:bool):
        await interaction.response.send_message(f"Attempting to clean up inactive servers now. Dry Run? {dryrun}")
        await ScamGuardBot.RunPeriodicLeave(dryrun) 
    
    SetupDatabases()
    ScamGuardBot.run(ConfigData.GetToken())