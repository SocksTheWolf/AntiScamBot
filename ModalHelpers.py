from discord import ui, Interaction, SelectOption, WebhookMessage, ButtonStyle, Message, TextChannel, ChannelType, Member, Permissions
from Logger import Logger, LogLevel
import traceback

class YesNoSelector(ui.Select):
    CurrentSelection:str = ""
    CachedValue:str = ""
    
    def __init__(self, RowPos=None):
        options = [
            SelectOption(label="Yes", description=self.GetYesDescription(), emoji="🟩"),
            SelectOption(label="No", description=self.GetNoDescription(),  emoji="🟥")
        ]
        
        super().__init__(placeholder=self.GetPlaceholder(), max_values=1, options=options, row=RowPos)
        self.SetRequired(True)
    
    def HasValue(self) -> bool:
        return self.CurrentSelection != ""
    
    def HasValueChanged(self) -> bool:
        if (self.CachedValue != "" and self.CachedValue != self.CurrentSelection):
            return True
        
        return False
        
    def GetValue(self) -> None | bool:
        if (self.CurrentSelection == ""):
            return None
        else:
            if (self.CurrentSelection == "Yes"):
                return True
            else:
                return False
        
    async def callback(self, interaction:Interaction):
        self.CurrentSelection = self.values[0]
        await interaction.response.send_message(f"Set Value to {self.GetValue()}", ephemeral=True, delete_after=0.001, silent=True)
        
    def SetRequired(self, NewState:bool):
        if (NewState):
            self.min_values = 1
        else:
            self.min_values = 0
            
    def IsRequired(self) -> bool:
        return True if self.min_values == 1 else False
    
    # Updates the current placeholder if a value is set already
    def SetCurrentValue(self, CurValue:bool) -> str:
        self.CurrentSelection = "Yes" if CurValue else "No"
        self.CachedValue = self.CurrentSelection
        self.placeholder = f"[Current Setting: {self.CurrentSelection}] {self.GetPlaceholder()}"
        
        if (self.SetNotRequiredIfValueSet()):
            self.SetRequired(False)
        
    def GetYesDescription(self) -> str:
        pass
    
    def GetNoDescription(self) -> str:
        pass
    
    def GetPlaceholder(self) -> str:
        pass
    
    def SetNotRequiredIfValueSet(self) -> bool:
        return False

# An override for channel selectors so that they do not show "This Interaction Failed" inappropriately
class ModChannelSelector(ui.ChannelSelect):
    def __init__(self, RowPos:int|None=None):
        super().__init__(row=RowPos, min_values=0, max_values=1, channel_types=[ChannelType.text], placeholder="ScamGuard Channel for Mod Messages")
        
    async def IsValid(self, interaction:Interaction, Silent:bool=False) -> bool:
        if (not self.values and self.min_values > 0):
            await interaction.response.send_message("A value must be selected for the channel selector!!", ephemeral=True, delete_after=60.0)    
            return False
        
        ChannelToHookInto:TextChannel = self.values[0].resolve()
        if (ChannelToHookInto == None):
            await interaction.response.send_message(f"ScamGuard does not have permissions to see the channel {ChannelToHookInto.mention}, please give it permissions", ephemeral=True, delete_after=60.0)
            return False
        
        # Check channel permissions to see if we can post in there.
        BotMember:Member = interaction.guild.get_member(interaction.client.user.id)
        PermissionsObj:Permissions = ChannelToHookInto.permissions_for(BotMember)
        if (not PermissionsObj.send_messages):
            await interaction.response.send_message(f"ScamGuard is unable to access the channel {ChannelToHookInto.mention}, please give its role `{interaction.guild.self_role.name}` access to `View Channel` & `Send Messages` in {ChannelToHookInto.mention}", ephemeral=True, delete_after=60.0)
            return False
        
        if (not Silent):
            await interaction.response.send_message(f"Message Channel Set to {ChannelToHookInto.mention}!", silent=True, ephemeral=True, delete_after=1.0)
        
        return True
        
    async def callback(self, interaction:Interaction):
        await self.IsValid(interaction, False)
        
    def SetRequired(self):
        self.min_values = 1

# This is an UI view that will allow for deletion after interaction.
class SelfDeletingView(ui.View):
    # Hook to the message we send, call Send to send the object.
    Hook:WebhookMessage|Message = None
    # Boolean to prevent multi-presses whenever discord ui lags.
    HasInteracted:bool = False
    
    def __init__(self, ViewTimeout:float|None=180):
         super().__init__(timeout=ViewTimeout)
         
    async def on_timeout(self):
        # prevent last second interactions...
        self.HasInteracted = True
        await self.StopInteractions()
        
    async def on_error(self, interaction:Interaction, error:Exception, object:ui.Item):
        Logger.Log(LogLevel.Error, f"View interaction encountered an error {str(error)} {traceback.format_exc()}")
        
    async def on_cancel(self, interaction:Interaction):
        pass
    
    @ui.button(label="Cancel", style=ButtonStyle.gray, row=4)
    async def cancel(self, interaction:Interaction, button:ui.Button):
        if (self.HasInteracted):
            return
        
        self.HasInteracted = True
        await self.on_cancel(interaction)
        await self.StopInteractions()
        
    async def StopInteractions(self):
        # Remove the original message, which is the embed
        if (self.Hook is not None):
            await self.Hook.delete()
        
        # Clear this view's buttons
        self.clear_items()
        # Stop processing this interaction further.
        self.stop()
        
    async def Send(self, interaction:Interaction, embedlist):
        if (self.Hook is not None):
            return
        
        self.Hook = await interaction.followup.send(embeds=embedlist, view=self, wait=True, ephemeral=True)
         
    async def SendToChannel(self, channel:TextChannel, embedlist):
        if (self.Hook is not None):
            return
        
        self.Hook = await channel.send(view=self, embeds=embedlist)