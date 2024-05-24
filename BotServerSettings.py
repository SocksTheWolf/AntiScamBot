from discord import ui, Guild, ButtonStyle, Interaction, Member, TextChannel, Permissions
from ModalHelpers import YesNoSelector, SelfDeletingView, ModChannelSelector
from BotDatabaseSchema import Server
from Config import Config

class BotSettingsPayload:
    User:Member = None
    WebHookRequired:bool = False
    KickSusRequired:bool = False
    
    # These settings should get pulled from the db
    Server:Guild = None
    MessageChannel:TextChannel = None
    WantsWebhooks:bool = False
    KickSusUsers:bool = False
    
    def GetServerID(self) -> int:
        if (self.Server is None):
            return 0
        
        return self.Server.id
    
    def GetUserID(self) -> int:
        if (self.User is None):
            return 0
        
        return self.User.id
    
    def HasMessageChannel(self) -> bool:
        return self.MessageChannel is not None
    
    def GetMessageID(self) -> int:
        if (not self.HasMessageChannel()):
            return 0
        
        return self.MessageChannel.id
    
    def LoadFromDB(self, BotInstance):
        DB = BotInstance.Database
        ServerInfo:Server = DB.GetServerInfo(self.Server.id)
        if (ServerInfo.activation_state == 0):
            self.KickSusRequired = self.WebHookRequired = True
        else:
            self.WantsWebhooks = ServerInfo.has_webhooks
            self.KickSusUsers = ServerInfo.kick_sus_users
        
        # Check to see what the setting is for messaging channel, if it's 0, leave MessageChannel as None
        # else load up the text channel value
        if (ServerInfo.message_channel != 0):
            self.MessageChannel = BotInstance.get_channel(ServerInfo.message_channel)

class InstallWebhookSelector(YesNoSelector):
    def GetYesDescription(self) -> str:
        return "Yes, install the ban notification webhook"
    
    def GetNoDescription(self) -> str:
        return "No, do not install the ban notification webhook"
    
    def GetPlaceholder(self) -> str:
        return "ScamGuard Ban Notifications"
    
    def SetNotRequiredIfValueSet(self) -> bool:
        return True
    
class KickSuspiciousUsersSelector(YesNoSelector):
    def GetYesDescription(self) -> str:
        return "Yes, kick any suspicious users. These are usually users that have sent numerous friend requests upon joining servers, or mass DMs"
    
    def GetNoDescription(self) -> str:
        return "No, do not kick any suspicious users automatically. This may have false positives!"
    
    def GetPlaceholder(self) -> str:
        return "Kick Suspicious Accounts"
    
    def SetNotRequiredIfValueSet(self) -> bool:
        return True

class ServerSettingsView(SelfDeletingView):
    ChannelSelect:ModChannelSelector = None
    WebhookSelector:InstallWebhookSelector = None
    SuspiciousUserKicks:KickSuspiciousUsersSelector = None
    CallbackFunction = None
    Payload:BotSettingsPayload = None
    
    def __init__(self, InCB, interaction: Interaction):
        super().__init__()
        ConfigData:Config = Config()
        
        # Pull current data
        self.Payload = BotSettingsPayload()
        self.Payload.Server = interaction.guild
        self.Payload.User = interaction.user
        self.Payload.LoadFromDB(interaction.client)
        
        self.ChannelSelect = ModChannelSelector(RowPos=0)
        # If we don't have a message channel selected, force this setting here.
        if (not self.Payload.HasMessageChannel()):
            self.ChannelSelect.min_values = 1
        
        self.add_item(self.ChannelSelect)
        
        if (ConfigData["AllowWebhookInstall"]):
            self.WebhookSelector = InstallWebhookSelector(RowPos=1)
            if (not self.Payload.WebHookRequired):
                self.WebhookSelector.SetCurrentValue(self.Payload.WantsWebhooks)
            self.add_item(self.WebhookSelector)
            
        if (ConfigData["AllowSuspiciousUserKicks"]):
            self.SuspiciousUserKicks = KickSuspiciousUsersSelector(RowPos=2)
            if (not self.Payload.KickSusRequired):
                self.SuspiciousUserKicks.SetCurrentValue(self.Payload.KickSusUsers)
            self.add_item(self.SuspiciousUserKicks)
            
        self.CallbackFunction = InCB
        
    @ui.button(label="Confirm Settings", style=ButtonStyle.success, row=4)
    async def setup(self, interaction: Interaction, button: ui.Button):
        # Check to see if the webhook selector has a value set
        ConfigData:Config = Config()
        ChannelSelectRequired:bool = self.ChannelSelect.min_values == 1
        
        if (ConfigData["AllowWebhookInstall"]):
            if (self.WebhookSelector.GetValue() != None):
                self.Payload.WantsWebhooks = self.WebhookSelector.GetValue()
            elif self.WebhookSelector.IsRequired():
                await interaction.response.send_message("Please choose an option for ban notifications!", ephemeral=True, delete_after=10.0)
                return

        # Resolve the selected channel to send messages into
        if (ChannelSelectRequired):
            if (await self.ChannelSelect.IsValid(interaction, True) == False):
                return
            
            ChannelToHookInto:TextChannel = self.ChannelSelect.values[0].resolve()
            
            if (self.Payload.WantsWebhooks):
                BotMember:Member = interaction.guild.get_member(interaction.client.user.id)
                PermissionsObj:Permissions = ChannelToHookInto.permissions_for(BotMember)
                
                # Check to see if we can manage webhooks in that channel, if the user wants us to add ban notifications
                if (not PermissionsObj.manage_webhooks):
                    await interaction.response.send_message(f"ScamGuard needs permissions to add a webhook into the channel {ChannelToHookInto.mention}, please give it manage webhook permissions", ephemeral=True, delete_after=60.0)
                    return
                
            self.Payload.MessageChannel = ChannelToHookInto
        
        self.HasInteracted = True
        
        # Push a message to the activation request channel
        await self.CallbackFunction(self.Payload)
        
        # Respond to the user and kill the interactions
        MessageResponse:str = ""
        if (not interaction.client.Database.IsActivatedInServer(self.Payload.Server.id)):
            MessageResponse = "Enqueued your server for activation. This will take a few minutes to import all the bans."
        else:
            MessageResponse = "Settings changes enqueued for application!"
            
        await interaction.response.send_message(MessageResponse, ephemeral=True, delete_after=10.0)
        await self.StopInteractions()