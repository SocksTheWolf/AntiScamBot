from Logger import Logger, LogLevel
from BotEnums import BanLookup
from Config import Config
from CommandHelpers import TargetIdTransformer, ServerIdTransformer, CommandErrorHandler
from discord import app_commands, Interaction, Member, Embed, Object, Webhook, Thread
from BotSetup import SetupDatabases
from ScamGuard import ScamGuard
from ConfirmBanView import ConfirmBan

ConfigData:Config=Config()

if __name__ == '__main__':
    CommandControlServer=Object(id=ConfigData["ControlServer"])
    ScamGuardBot = ScamGuard(ConfigData["ControlBotID"])

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
            BotInstance:int = ScamGuardBot.Database.GetBotIdForServer(server)
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
        
    @ScamGuardBot.Commands.command(name="print", description="Print stats and information about all bots in the server", guild=CommandControlServer)
    @app_commands.checks.has_role(ConfigData["MaintainerRole"])
    async def PrintServers(interaction:Interaction):
        ReplyStr:str = "I am in the following servers:\n"
        RowNum:int = 1
        NumBans:int = len(ScamGuardBot.Database.GetAllBans())
        ActivatedServers:int = 0
        await interaction.response.defer(thinking=True)
        ResponseHook:Webhook = interaction.followup
        QueryResults = ScamGuardBot.Database.GetAllServers(False)
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
            await interaction.channel.send(MessageChunk)
            
        await ResponseHook.send("Done printing", ephemeral=True)

    @ScamGuardBot.Commands.command(name="scamban", description="Bans a scammer", guild=CommandControlServer)
    @app_commands.checks.has_role(ConfigData["ApproverRole"])
    @app_commands.describe(targetid='The discord id for the user to ban')
    async def ScamBan(interaction:Interaction, targetid:app_commands.Transform[int, TargetIdTransformer]):
        if (targetid <= -1):
            await interaction.response.send_message("Invalid id!", ephemeral=True, delete_after=5.0)
            return 
        
        Sender:Member = interaction.user
        Logger.Log(LogLevel.Verbose, f"Scam ban message detected from {Sender} for {targetid}")
        # Check to see if the ban already exists
        if (not ScamGuardBot.Database.DoesBanExist(targetid)):
            BanEmbed:Embed = await ScamGuardBot.CreateBanEmbed(targetid)
            BanView:ConfirmBan = ConfirmBan(targetid, ScamGuardBot)
            await interaction.response.defer(ephemeral=True, thinking=True)
            BanView.Hook = await interaction.followup.send(embed=BanEmbed, view=BanView, wait=True, ephemeral=True)
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

        Sender:Member = interaction.user
        Logger.Log(LogLevel.Verbose, f"Scam unban message detected from {Sender} for {targetid}")
        Result = await ScamGuardBot.PrepareUnban(targetid, Sender)
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
    async def ActivateServer(interaction:Interaction):
        Sender:Member = interaction.user
        SendersId:int = Sender.id

        # Hold onto these objects, as activate is one of the most expensive commands if
        # we are running off a database that is mostly made of up unactivated servers.
        await interaction.response.defer(thinking=True)
        ResponseHook:Webhook = interaction.followup
        
        ScamGuardBot.ClientHandler.SendActivationForServers(SendersId)
        await ScamGuardBot.ActivateServersWithPermissions(SendersId)
        await ResponseHook.send("Enqueued processing for activation for servers you own/moderate in")
        
    @ScamGuardBot.Commands.command(name="deactivate", description="Deactivates a server and prevents any future ban information from being shared", guild=CommandControlServer)
    async def DeactivateServer(interaction:Interaction):
        Sender:Member = interaction.user
        SendersId:int = Sender.id
        
        ScamGuardBot.ClientHandler.SendDeactivationForServers(SendersId)
        await ScamGuardBot.DeactivateServersWithPermissions(SendersId)
        await interaction.response.send_message("Enqueued processing for deactivation for servers you own/moderate in")

    # Control server version of scamcheck
    @ScamGuardBot.Commands.command(name="scamcheck", description="In the control server, check to see if a discord id is banned", guild=CommandControlServer)
    @app_commands.describe(target='The discord user id to check')
    @app_commands.checks.cooldown(1, 3.0)
    async def ScamCheck_Control(interaction:Interaction, target:app_commands.Transform[int, TargetIdTransformer]):
        if (target <= -1):
            await interaction.response.send_message("Invalid id!", ephemeral=True, delete_after=5.0)
            return
        
        ResponseEmbed:Embed = await ScamGuardBot.CreateBanEmbed(target)
        await interaction.response.send_message(embed = ResponseEmbed)
        
    @ScamGuardBot.Commands.command(name="scamtrack", description="Tracks a thread for a given user", guild=CommandControlServer)
    @app_commands.describe(target='The discord id for the user of the current thread')
    async def ScamThreadTrack(interaction:Interaction, target:app_commands.Transform[int, TargetIdTransformer]):
        if (target <= -1):
            await interaction.response.send_message("Invalid id!", ephemeral=True, delete_after=5.0)
            return
        
        # Make sure that the data is valid, and this is of a thread type.
        if (interaction.channel is None or interaction.channel_id is None or type(interaction.channel) != Thread):
            await interaction.response.send_message("This command can only be ran in threads!", ephemeral=True, delete_after=5.0)
            return
        
        # Pull the thread id and see if it's already been added
        ThreadID:int = interaction.channel_id
        if (ScamGuardBot.Database.IsThreadTracked(target, ThreadID)):
            await interaction.response.send_message("This thread is already tracked!", ephemeral=True, delete_after=5.0)
            return
        
        # Add the thread to track, and reply to the user
        ScamGuardBot.Database.AddThreadTracking(target, ThreadID)
        await interaction.response.send_message(f"Registered this thread for user {target}")
        
    @ScamGuardBot.Commands.command(name="scamuntrack", description="Untracks a thread for a given user", guild=CommandControlServer)
    @app_commands.checks.has_role(ConfigData["ApproverRole"])
    @app_commands.describe(target='The discord id for the user of the current thread')
    async def ScamThreadUntrack(interaction:Interaction, target:app_commands.Transform[int, TargetIdTransformer]):
        if (target <= -1):
            await interaction.response.send_message("Invalid id!", ephemeral=True, delete_after=5.0)
            return
        
        # Make sure that the data is valid, and this is of a thread type.
        if (interaction.channel is None or interaction.channel_id is None or type(interaction.channel) != Thread):
            await interaction.response.send_message("This command can only be ran in threads!", ephemeral=True, delete_after=5.0)
            return

        # Remove the thread to track and respond appropriately.
        if (ScamGuardBot.Database.RemoveThreadTracking(target, interaction.channel_id)):
            await interaction.response.send_message(f"Unregistered this thread for user {target}")
        else:
            await interaction.response.send_message(f"This thread was not being tracked for {target}", ephemeral=True, delete_after=5.0)
        
    SetupDatabases()
    ScamGuardBot.run(ConfigData.GetToken())