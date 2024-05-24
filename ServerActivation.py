from discord import ui, ButtonStyle, Interaction, Colour, Embed, Guild
from Config import Config
from Logger import Logger, LogLevel
from BotServerSettings import ServerSettingsView, BotSettingsPayload
from ModalHelpers import SelfDeletingView

class ScamGuardServerSetup():
    BotInstance = None
    
    def __init__(self, Bot) -> None:
        self.BotInstance = Bot
        
    async def CheckForBotConflicts(self, InServer:Guild) -> bool:
        BotConflicts = Config()["ConflictingBots"]
        for DiscordBotId in BotConflicts:
            if (await self.BotInstance.LookupUser(DiscordBotId, InServer) is not None):
                return True
            
        return False
    
    async def OpenServerSetupModel(self, interaction:Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        NumBans:int = self.BotInstance.Database.GetNumBans()
        
        InformationEmbed:Embed = self.BotInstance.CreateBaseEmbed("ScamGuard Setup Welcome")
        InformationEmbed.add_field(name="Setup Info", inline=False, value="When you click on the 'Confirm Settings' button, ScamGuard will send an activation request to handle your server setup.\nWhen complete, ScamGuard will start importing bans")
        InformationEmbed.add_field(name="Number of Bans", inline=False, value=f"ScamGuard will import ~{NumBans} bans into your ban list. This will usually be more than the amount of people in your server.\n\nThese aren't the number of people in your server, it is establishing a firewall to prevent scammers from entering.")
        InformationEmbed.add_field(name="Commands", inline=False, value="Use `/scamguard` to see the various different commands that the bot has, please use `/scamguard report` to report scammers that ScamGuard hasn't seen yet.")
        InformationEmbed.add_field(name="", value="", inline=False)
        InformationEmbed.add_field(name="Settings", value="", inline=False)
        InformationEmbed.add_field(name="Mod Message Channel", inline=False, value="Granting ScamGuard access to a channel that only moderators can see is highly recommended as the information passed there is usually important to mods. Messages are not sent very frequently.")
        InformationEmbed.add_field(name="Ban Notifications", inline=False, value="If you would like to subscribe to notifications when ScamGuard bans, select Yes when prompted about installing a webhook. It is highly recommended, but not necessary.")
        InformationEmbed.add_field(name="", value="", inline=False)
        InformationEmbed.add_field(name="IMPORTANT:", value="", inline=False)
        InformationEmbed.add_field(name="Roles", inline=False, value="Make sure that ScamGuard has a moderator role for your server to ease any issues.\n\nIf you do not want to give a moderator role to ScamGuard, you can watch this video for how to position the roles properly to avoid any problems: https://youtu.be/XYaQi3hM9ug")
        
        # Check to see if WizeBot/Carlbot is in the server, and warn about it.
        if (await self.CheckForBotConflicts(interaction.guild)):
            InformationEmbed.add_field(name="WizeBot & Carlbot", inline=False, value="It is detected that you have Wizebot/Carlbot in your server, you will need to whitelist ScamGuard in the WizeBot dashboard! Conflicts can arise between the two bots otherwise!!!")
        
        InformationEmbed.add_field(name="", value="", inline=False)
        InformationEmbed.add_field(name="Important Links", inline=False, value="[Support](https://scamguard.app/discord) | [Terms Of Service](https://scamguard.app/terms) | [Privacy Policy](https://scamguard.app/privacy)")
        InformationEmbed.set_footer(text="ScamGuard")
        
        NewSetupView:ServerSettingsView = ServerSettingsView(self.SendActivationRequest, interaction)
        await NewSetupView.Send(interaction, [InformationEmbed])

    async def PushActivation(self, Payload:BotSettingsPayload):
        ServerID:int = Payload.GetServerID()
        UserID:int = Payload.GetUserID()
        DB = self.BotInstance.Database
        ServerInstance:int = DB.GetBotIdForServer(Payload.GetServerID())
        
        DB.SetFromServerSettings(ServerID, Payload)        
        if (Payload.WantsWebhooks):
            await self.BotInstance.AnnouncementChannel.follow(destination=Payload.MessageChannel, reason="ScamGuard Setup")
        
        self.BotInstance.ClientHandler.SendActivationForServerInstance(UserID, ServerID, ServerInstance)
        await self.BotInstance.ActivateServerInstance(UserID, ServerID)
        
    async def SendActivationRequest(self, Payload:BotSettingsPayload):
        # If the server is already activated then do nothing more.
        if (self.BotInstance.Database.IsActivatedInServer(Payload.GetServerID())):
            Logger.Log(LogLevel.Warn, f"User {Payload.GetUserID()} attempted to activate {self.BotInstance.GetServerInfoStr(Payload.Server)} but it's already activated")
            return
        
        # If we don't require moderation for activation approval
        if (Config()["RequireActivationApproval"] == False):
            Logger.Log(LogLevel.Notice, f"Attempting to activate a server without approval necessary!")
            await self.PushActivation(Payload)
            return
        
        # View actions for the server activation approval
        ActivationActions:ServerActivationApproval = ServerActivationApproval(self, Payload)
        
        # Request Embed for the Activation Server
        RequestEmbed:Embed = Embed(title="Activation Request", color = Colour.orange())
        RequestEmbed.add_field(name="Server Name", value=Payload.Server.name, inline=False)
        RequestEmbed.add_field(name="Requestor", value=Payload.User.display_name)
        RequestEmbed.add_field(name="Requestor Handle", value=Payload.User.mention)
        RequestEmbed.add_field(name="Num Members", value=Payload.Server.member_count, inline=False)
        if (Payload.Server.icon is not None):
            RequestEmbed.set_thumbnail(url=Payload.Server.icon.url)
        RequestEmbed.set_footer(text=f"Server ID: {Payload.GetServerID()} | Requestor ID: {Payload.GetUserID()}")
        
        await ActivationActions.SendToChannel(self.BotInstance.ActivationChannel, [RequestEmbed])
    
class ServerActivationApproval(SelfDeletingView):
    Parent = None
    Payload:BotSettingsPayload = None
    
    def __init__(self, Parent, InPayload:BotSettingsPayload):
        self.Parent = Parent
        self.Payload = InPayload
        
        super().__init__(ViewTimeout=None)
        
    @ui.button(label="Approve", style=ButtonStyle.success, row=4)
    async def setup(self, interaction: Interaction, button: ui.Button):
        self.HasInteracted = True
        await interaction.response.send_message(f"Enqueing activation for server {self.Payload.GetServerID()}")
        await self.Parent.PushActivation(self.Payload)
        await self.StopInteractions()
        
    async def on_cancel(self, interaction:Interaction):
        ServerID:int = self.Payload.GetServerID()
        Bot = interaction.client
        DB = interaction.client.Database
        
        await interaction.response.send_message(f"Activation denied for server {ServerID}.")
        
        ChannelIDToPost:int = DB.GetChannelIdForServer()
        DiscordChannel = Bot.get_channel(ChannelIDToPost)
        ServerIDStr:str = Bot.GetServerInfoStr(self.Payload.Server)
        
        if (DiscordChannel is None):
            Logger.Log(LogLevel.Error, f"Could not resolve the channel {ChannelIDToPost} for server {ServerIDStr} to post activation deny message in")
            return
        
        # Do not send a message if the server admins sent the activation command a few times already.
        if (not DB.IsActivatedInServer(ServerID)):
            await DiscordChannel.send("An error has occured when trying to activate ScamGuard, please join the [Discord Support Server](https://scamguard.app/discord) to troubleshoot")