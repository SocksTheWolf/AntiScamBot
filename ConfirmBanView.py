from Logger import Logger, LogLevel
from BotEnums import BanLookup
from discord import ui, ButtonStyle, Interaction, Member, WebhookMessage

class ConfirmBan(ui.View):
    TargetId:int = None
    ScamBot = None
    Hook:WebhookMessage = None
    ActionTaken:bool = False
    
    def __init__(self, target:int, bot):
        super().__init__(timeout=60.0)
        self.TargetId = target
        self.ScamBot = bot
        
    @ui.button(label="Confirm Ban", style=ButtonStyle.danger)
    async def confirm(self, interaction: Interaction, button: ui.Button):
        # Prevent pressing the button multiple times during asynchronous action.
        if (self.ActionTaken):
            return
        
        Sender:Member = interaction.user
        ResponseMsg:str = ""
        if (self.ScamBot is None):
            Logger.Log(LogLevel.Error, "ConfirmBan view has an invalid ScamBot reference!!")    
            return
        
        self.ActionTaken = True
        Result = await self.ScamBot.PrepareBan(self.TargetId, Sender)
        if (Result is not BanLookup.Banned):
            if (Result == BanLookup.Duplicate):
                ResponseMsg = f"{self.TargetId} already exists in the ban database"
                Logger.Log(LogLevel.Log, f"The given id {self.TargetId} is already banned.")
            else:
                ResponseMsg = f"The given id {self.TargetId} had an error while banning!"
                Logger.Log(LogLevel.Warn, f"{Sender} attempted ban on {self.TargetId} with error {str(Result)}")
        else:
            ResponseMsg = f"The ban for {self.TargetId} is in progress..."
            
        await interaction.response.send_message(ResponseMsg)
        await self.StopInteractions()
        
    @ui.button(label="Cancel", style=ButtonStyle.gray)
    async def cancel(self, interaction: Interaction, button: ui.Button):
        if (self.ActionTaken):
            return
        
        self.ActionTaken = True
        await interaction.response.send_message("This action was cancelled.", ephemeral=True, delete_after=10.0)
        await self.StopInteractions()
        
    async def on_timeout(self):
        # prevent last second interactions...
        self.ActionTaken = True
        
        Logger.Log(LogLevel.Log, f"Action confirmation timed out for {self.TargetId}")
        await self.StopInteractions()
        
    async def on_error(self, interaction:Interaction, error:Exception, object:ui.Item):
        Logger.Log(LogLevel.Error, f"ConfirmBan encountered an error {str(error)}")
        
    async def StopInteractions(self):
        # Remove the original message, which is the embed
        if (self.Hook is not None):
            Logger.Log(LogLevel.Debug, "Have message hook, going to cleanup objects quickly.")
            await self.Hook.delete()
        else:
            Logger.Log(LogLevel.Debug, "View hook was none, cannot cleanup messages early...")

        # Clear this view's buttons
        self.clear_items()
        # Stop processing this interaction further.
        self.stop()