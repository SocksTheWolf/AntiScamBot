from discord import ui, TextStyle, Interaction, Member
from Logger import Logger, LogLevel

class SubmitScamReport(ui.Modal):
    ReportedUser:Member = None
    TypeOfScam = ui.TextInput(label="Type of Scam", placeholder="Please Select the Type of Scam", max_length=50, min_length=10)
    Reasoning = ui.TextInput(label="Scam Ban Reasoning",
                                     placeholder="The reason that this user should be reported",
                                     max_length=300, required=False)    
    ScamEvidence = ui.TextInput(label="Evidence of Scam", 
                                        placeholder="Please insert links to images (space separated)",
                                        style=TextStyle.paragraph,
                                        max_length=4000,
                                        required=True)
    def __init__(self, InReportUser:Member):
        self.ReportedUser = InReportUser
        TruncatedName:str = InReportUser.name[:20]
        super().__init__(title=f"Report {TruncatedName}[{InReportUser.id}]")
    
    async def on_submit(self, interaction: Interaction):                
        # Check to see if already banned.
        if (interaction.client.Database.DoesBanExist(self.ReportedUser.id)):
            await interaction.response.send_message(f"The reported user is already banned!", ephemeral=True, delete_after=10.0)
            return
        
        # Split the evidence block into a string list
        EvidenceList:list[str] = self.ScamEvidence.value.split()
                
        ScamReportPayload = {
            "ReportingUserName": interaction.user.name,
            "ReportingUserId": interaction.user.id,
            "ReportedServer": interaction.guild.name,
            "ReportedServerId": interaction.guild_id,
            "ReportedUserGlobalName": self.ReportedUser.display_name,
            "ReportedUserName": self.ReportedUser.name,
            "ReportedUserId": self.ReportedUser.id,
            "TypeOfScam": self.TypeOfScam.value,
            "Reasoning": self.Reasoning.value,
            "Evidence": EvidenceList
        }
        
        interaction.client.AddAsyncTask(interaction.client.PostScamReport(ScamReportPayload))
        await interaction.response.send_message(f"Sent report about user {self.ReportedUser.id} successfully")
        
    async def on_error(self, interaction: Interaction, exceptionError: Exception):
        Logger.Log(LogLevel.Error, f"Encountered Exception with the scam report modal: {str(exceptionError)}")
        await interaction.response.send_message(f"Unable to send report about user {self.ReportedUser.id}", ephemeral=True, delete_after=10.0)