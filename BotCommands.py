from CommandHelpers import TargetIdTransformer
from discord import app_commands, Interaction, Member, User, Embed
from ScamReportModal import SubmitScamReport
from Config import Config

@app_commands.guild_only()
class GlobalScamCommands(app_commands.Group):   
    def GetInstance(self):
        return self.extras["instance"]
    
    def IsActivated(self, InteractionId:int) -> bool:
        return (self.GetInstance().Database.IsActivatedInServer(InteractionId))
     
    @app_commands.command(name="check", description="Checks to see if a discord id is banned")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.cooldown(1, 3.0)
    async def ScamCheck_Global(self, interaction:Interaction, target:app_commands.Transform[int, TargetIdTransformer]):
        if (target <= -1):
            await interaction.response.send_message("Invalid id!", ephemeral=True, delete_after=5.0)
            return
        
        if (self.IsActivated(interaction.guild_id)):
            ResponseEmbed:Embed = await self.GetInstance().CreateBanEmbed(target)
            await interaction.response.send_message(embed = ResponseEmbed)
        else:
            await interaction.response.send_message("Your server must be activated in order to run scam check!")

    @app_commands.command(name="report", description="Report an User ID")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.cooldown(1, 5.0)
    async def ReportScam_Global(self, interaction:Interaction, target:app_commands.Transform[int, TargetIdTransformer]):        
        if (interaction.guild_id == Config()["ControlServer"]):
            await interaction.response.send_message("You cannot make remote reports from this server!", ephemeral=True, delete_after=5.0)
            return
        
        # Block any usages of the commands if the server is not activated.
        if (not self.IsActivated(interaction.guild_id)):
            await interaction.response.send_message("You must activate your server to report users", ephemeral=True, delete_after=10.0)
            return
        
        UserToSend:Member|User|None = await self.GetInstance().LookupUser(target, ServerToInspect=interaction.guild)
        # If the user is no longer in said server, then do a global lookup
        if (UserToSend is None):
            UserToSend = await self.GetInstance().LookupUser(target)
        
        # If the user is still invalid, then ask for a manual report.
        if (UserToSend is None):
            await interaction.response.send_message("Unable to look up the given user for a report, you'll have to make a report manually.", ephemeral=True)
            return
        
        await interaction.response.send_modal(SubmitScamReport(UserToSend))
        
    @app_commands.command(name="reportuser", description="Report a mentionable member")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.cooldown(1, 5.0)
    async def ReportScamUser_Global(self, interaction:Interaction, user:Member):
        if (interaction.guild_id == Config()["ControlServer"]):
            await interaction.response.send_message("This command cannot be used in the control server", ephemeral=True, delete_after=5.0)
            return
        
        # Block any usages of the commands if the server is not activated.
        if (not self.IsActivated(interaction.guild_id)):
            await interaction.response.send_message("You must activate your server to report users", ephemeral=True, delete_after=10.0)
            return
        
        await interaction.response.send_modal(SubmitScamReport(user))

    @app_commands.command(name="setup", description="Set up ScamGuard")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.cooldown(1, 5.0)
    async def SetupScamGuard_Global(self, interaction:Interaction):
        if (interaction.guild_id == Config()["ControlServer"]):
            await interaction.response.send_message("This command cannot be used in the control server", ephemeral=True, delete_after=5.0)
            return
        
        # Block any usages of the setup command if the server is activated.
        if (not self.IsActivated(interaction.guild_id)):
            await self.GetInstance().ServerSetupHelper.OpenServerSetupModel(interaction)
        else:
            await interaction.response.send_message("This server is already activated with ScamGuard!", ephemeral=True, delete_after=15.0)

    @app_commands.command(name="info", description="Info & Stats about ScamGuard")
    @app_commands.checks.cooldown(1, 5.0)
    async def HelpScamGuard_Global(self, interaction:Interaction):
        if (interaction.guild_id == Config()["ControlServer"]):
            await interaction.response.send_message("This command cannot be used in the control server", ephemeral=True, delete_after=5.0)
            return
        
        ResponseEmbed:Embed = self.GetInstance().CreateInfoEmbed()
        await interaction.response.send_message(embed=ResponseEmbed, silent=True)