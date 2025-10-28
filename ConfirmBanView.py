from Logger import Logger, LogLevel
from BotEnums import BanLookup, ModerationAction
from discord import ui, ButtonStyle, Interaction, Member, User, WebhookMessage
from ModalHelpers import SelfDeletingView

class ConfirmBan(SelfDeletingView):
    TargetId:int = 0
    ScamBot = None
    
    def __init__(self, target:int, bot):
        super().__init__(ViewTimeout=90.0)
        self.TargetId = target
        self.ScamBot = bot
        
    async def on_cancel(self, interaction:Interaction):
        await interaction.response.send_message("This action was cancelled.", ephemeral=True, delete_after=10.0)
        
    @ui.button(label="Confirm Ban", style=ButtonStyle.danger, row=4)
    async def confirm(self, interaction: Interaction, button: ui.Button):
        # Prevent pressing the button multiple times during asynchronous action.
        if (self.HasInteracted):
            return
        
        Sender:Member|User = interaction.user
        ResponseMsg:str = ""
        if (self.ScamBot is None):
            Logger.Log(LogLevel.Error, "ConfirmBan view has an invalid ScamBot reference!!")    
            return
        
        await interaction.response.defer(thinking=True)
        self.HasInteracted = True
        Result:BanLookup = await self.ScamBot.HandleBanAction(self.TargetId, Sender, ModerationAction.Ban, interaction.channel_id)
        if (Result is not BanLookup.Banned):
            if (Result == BanLookup.Duplicate):
                ResponseMsg = f"{self.TargetId} already exists in the ban database"
                Logger.Log(LogLevel.Log, f"The given id {self.TargetId} is already banned.")
            else:
                ResponseMsg = f"The given id {self.TargetId} had an error while banning!"
                Logger.Log(LogLevel.Warn, f"{Sender} attempted ban on {self.TargetId} with error {str(Result)}")
        else:
            ResponseMsg = f"{interaction.user.mention}, the ban for {self.TargetId} is now in progress..."

        # Make this message silent as we may include an @ mention in here and do not want to bother the user with notifications
        await interaction.followup.send(ResponseMsg, silent=True)
        await self.StopInteractions()
        