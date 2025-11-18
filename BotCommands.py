# ScamGuard application commands that are used on every server
from CommandHelpers import TargetIdTransformer
from discord import app_commands, Interaction, Member, User, Embed
from ScamReportModal import SubmitScamReport
from BotServerSettings import ServerSettingsView
from Config import Config

@app_commands.guild_only()
class GlobalScamCommands(app_commands.Group):   
    def GetInstance(self):
        return self.extras["instance"]
    
    def IsActivated(self, InteractionId:int) -> bool:
        return (self.GetInstance().Database.IsActivatedInServer(InteractionId))
    
    def CanReport(self, InteractionId:int) -> bool:
        return (self.GetInstance().Database.CanServerReport(InteractionId))
     
    @app_commands.command(name="check", description="Checks to see if a discord id is banned")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.cooldown(1, 2.0)
    async def ScamCheck_Global(self, interaction:Interaction, target:app_commands.Transform[int, TargetIdTransformer]):
        if (target <= -1):
            await interaction.response.send_message("Invalid id!", ephemeral=True, delete_after=5.0)
            return
        
        InteractionId:int|None = interaction.guild_id
        if (InteractionId is None):
            await interaction.response.send_message("This command cannot be ran outside a server")
            return
        
        if (self.IsActivated(InteractionId)):
            ResponseEmbed:Embed = await self.GetInstance().CreateBanEmbed(target)
            await interaction.response.send_message(embed = ResponseEmbed)
        else:
            await interaction.response.send_message("Your server must be activated in order to run scam check!")

    @app_commands.command(name="report", description="Report an User")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.cooldown(1, 5.0)
    async def ReportScam_Global(self, interaction:Interaction, target:app_commands.Transform[int, TargetIdTransformer]):        
        if (interaction.guild_id == Config()["ControlServer"]):
            await interaction.response.send_message("You cannot make remote reports from this server!", ephemeral=True, delete_after=5.0)
            return
        
        InteractionId:int|None = interaction.guild_id
        if (InteractionId is None):
            await interaction.response.send_message("This command cannot be ran outside a server")
            return
        
        # Block any usages of the commands if the server is not activated.
        if (not self.IsActivated(InteractionId)):
            await interaction.response.send_message("You must activate your server to report users", ephemeral=True, delete_after=10.0)
            return
        
        # Check if the server is barred from reporting
        if (not self.CanReport(InteractionId)):
            await interaction.response.send_message("Due to potential abuse, this command is limited in this server, please contact support.", ephemeral=True, delete_after=10.0)
            return
        
        # If it cannot be transformed, print an error
        if (target == -1):
            await interaction.response.send_message("Could not look up the given user, supported look up methods are via @ mentions and user ids", ephemeral=True)
            return

        UserToSend:Member|User|None = await self.GetInstance().LookupUser(target, ServerToInspect=interaction.guild)
        # If the user is no longer in said server, then do a global lookup
        if (UserToSend is None):
            UserToSend = await self.GetInstance().LookupUser(target)

        # If the user is still invalid, then ask for a manual report.
        if (UserToSend is None):
            await interaction.response.send_message("Unable to look up the given user for a report, you'll have to make a report manually.", ephemeral=True)
            return
        
        # Check if the user is already banned
        if (interaction.client.Database.DoesBanExist(UserToSend.id)): # type: ignore
            await interaction.response.send_message(f"The targeted user is already banned by ScamGuard.", ephemeral=True, delete_after=20.0)
        
        await interaction.response.send_modal(SubmitScamReport(UserToSend))

    @app_commands.command(name="setup", description="Set up ScamGuard")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.cooldown(1, 5.0)
    async def SetupScamGuard_Global(self, interaction:Interaction):
        if (interaction.guild_id == Config()["ControlServer"]):
            await interaction.response.send_message("This command cannot be used in the control server", ephemeral=True, delete_after=5.0)
            return
        
        InteractionId:int|None = interaction.guild_id
        if (InteractionId is None):
            await interaction.response.send_message("This command cannot be ran outside a server")
            return
        
        # Block any usages of the setup command if the server is activated.
        if (not self.IsActivated(InteractionId)):
            await self.GetInstance().ServerSetupHelper.OpenServerSetupModel(interaction)
        else:
            await interaction.response.send_message("This server is already activated with ScamGuard! Use `/scamguard config` to change settings", ephemeral=True, delete_after=15.0)
            
            
    @app_commands.command(name="config", description="Set ScamGuard Settings")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.cooldown(1, 5.0)
    async def ConfigScamGuard_Global(self, interaction:Interaction):
        if (interaction.guild_id == Config()["ControlServer"]):
            await interaction.response.send_message("This command cannot be used in the control server", ephemeral=True, delete_after=5.0)
            return
        
        InteractionId:int|None = interaction.guild_id
        if (InteractionId is None):
            await interaction.response.send_message("This command cannot be ran outside a server")
            return
        
        if (not self.IsActivated(InteractionId)):
            await interaction.response.send_message("You must run `/scamguard setup` and activate first before proceeding", ephemeral=True, delete_after=30.0)
        else:
            await interaction.response.defer(thinking=True)
            BotInstance = self.GetInstance()
            ResponseEmbed:Embed = BotInstance.CreateBaseEmbed("ScamGuard Settings")
            BotInstance.AddSettingsEmbedInfo(ResponseEmbed)
            
            SettingsView:ServerSettingsView = ServerSettingsView(interaction.client.ApplySettings, interaction) # type: ignore
            await SettingsView.Send(interaction, [ResponseEmbed])

    @app_commands.command(name="info", description="Info & Stats about ScamGuard")
    @app_commands.checks.cooldown(1, 5.0)
    async def HelpScamGuard_Global(self, interaction:Interaction):
        if (interaction.guild_id == Config()["ControlServer"]):
            await interaction.response.send_message("This command cannot be used in the control server", ephemeral=True, delete_after=5.0)
            return
        
        ResponseEmbed:Embed = self.GetInstance().CreateInfoEmbed()
        await interaction.response.send_message(embed=ResponseEmbed, silent=True)