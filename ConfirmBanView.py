from Logger import Logger, LogLevel
from BotEnums import BanAction, ModerationAction
from discord import ui, ButtonStyle, Interaction, Member, User, ForumTag, Thread
from ModalHelpers import SelfDeletingView
from Config import Config
from typing import cast

class ConfirmBan(SelfDeletingView):
    TargetId:int = 0
    ScamBot = None
    
    def __init__(self, target:int, bot):
        super().__init__(ViewTimeout=90.0)
        self.TargetId = target
        self.ScamBot = bot
        
    async def on_cancel(self, interaction:Interaction):
        await interaction.response.send_message("This action was cancelled.", ephemeral=True, delete_after=10.0)
        
    async def AddTag(self, thread: Thread, Action: BanAction):
        # Attempt to set the forum handled/duplicate tag because this is really annoying otherwise
        try:
            TagName:str = ""
            if (Action == BanAction.Banned):
                TagName = Config()["ReportHandledTag"]
            elif (Action == BanAction.Duplicate):
                TagName = Config()["ReportDuplicateTag"]
            else:
                return
            HandledForumTag:ForumTag = ForumTag(name=TagName)
            if (HandledForumTag not in thread.applied_tags):
                await thread.add_tags(HandledForumTag)
            else:
                return
        except Exception as ex:
            Logger.Log(LogLevel.Warn, f"Could not set the handled tag in {thread.id} {str(ex)}")
        
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
        Result:BanAction = await self.ScamBot.HandleBanAction(self.TargetId, Sender, ModerationAction.Ban, interaction.channel_id)
        if (Result is not BanAction.Banned):
            if (Result == BanAction.Duplicate):
                ResponseMsg = f"{self.TargetId} already exists in the ban database"
                Logger.Log(LogLevel.Log, f"The given id {self.TargetId} is already banned.")
            else:
                ResponseMsg = f"The given id {self.TargetId} had an error while banning!"
                Logger.Log(LogLevel.Warn, f"{Sender} attempted ban on {self.TargetId} with error {str(Result)}")
        else:
            ResponseMsg = f"{interaction.user.mention}, the ban for {self.TargetId} is now in progress..."

        await self.AddTag(cast(Thread, interaction.channel), Result)
        # Make this message silent as we may include an @ mention in here and do not want to bother the user with notifications
        await interaction.followup.send(ResponseMsg, silent=True)
        await self.StopInteractions()
        