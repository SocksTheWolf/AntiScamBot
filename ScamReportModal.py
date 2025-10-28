from discord import ui, TextStyle, Interaction, Member, User
from Logger import Logger, LogLevel

class SubmitScamReport(ui.Modal):
    ReportedUser:Member|User|None = None
    TypeOfScam = ui.TextInput(label="Type of Scam", required=True, placeholder="Please state the type of scam", max_length=50, min_length=10)
    Reasoning = ui.TextInput(label="Details",
                                     placeholder="Provide extra context towards the ban itself here",
                                     style=TextStyle.paragraph,
                                     max_length=700, required=False)    
    ScamEvidence = ui.TextInput(label="Image Evidence", 
                                        placeholder="Please insert links to images (space separated up to 9). Images speed up the process immensely!",
                                        style=TextStyle.paragraph,
                                        min_length=1,
                                        max_length=4000,
                                        required=True)
    def __init__(self, InReportUser:Member|User):
        self.ReportedUser = InReportUser
        TruncatedName:str = InReportUser.name[:19]
        ModalTitle:str=f"Report {TruncatedName}[{InReportUser.id}]"[:45]
        super().__init__(title=ModalTitle)
    
    async def on_submit(self, interaction: Interaction):
        if (self.ReportedUser is None):
            Logger.Log(LogLevel.Error, "Failed to get reported user on scam submission, somehow none???")
            await interaction.response.send_message(f"Unable to submit report, please try again in a minute", ephemeral=True)
            return
        
        # Check to see if already banned.
        if (interaction.client.Database.DoesBanExist(self.ReportedUser.id)): # pyright: ignore[reportAttributeAccessIssue]
            await interaction.response.send_message(f"The reported user has been already banned.", ephemeral=True, delete_after=20.0)
            return
        
        # Split the evidence block into a string list
        EvidenceList:list[str] = self.ScamEvidence.value.split()
        # Log the original data so we don't lose it
        Logger.Log(LogLevel.Log, f"Given evidence for report for id {self.ReportedUser.id} is {self.ScamEvidence.value}")
                
        ScamReportPayload = {
            "ReportingUserName": interaction.user.name,
            "ReportingUserId": interaction.user.id,
            "ReportedServer": interaction.guild.name, # pyright: ignore[reportOptionalMemberAccess]
            "ReportedServerId": interaction.guild_id,
            "ReportedUserGlobalName": self.ReportedUser.display_name,
            "ReportedUserName": self.ReportedUser.name,
            "ReportedUserId": self.ReportedUser.id,
            "TypeOfScam": self.TypeOfScam.value,
            "Reasoning": self.Reasoning.value,
            "Evidence": EvidenceList,
            "Webhook": interaction.followup
        }
        
        await interaction.response.defer(thinking=True)
        interaction.client.AddAsyncTask(interaction.client.PostScamReport(ScamReportPayload)) # pyright: ignore[reportAttributeAccessIssue]
        
    async def on_error(self, interaction: Interaction, exceptionError: Exception):
        Logger.Log(LogLevel.Error, f"Encountered Exception with the scam report modal: {str(exceptionError)}")
        # I hate pylance so much
        ReportedUserId = 0
        if (self.ReportedUser is not None):
            ReportedUserId = self.ReportedUser.id
        await interaction.response.send_message(f"Unable to send report about user {ReportedUserId}", ephemeral=True, delete_after=20.0)