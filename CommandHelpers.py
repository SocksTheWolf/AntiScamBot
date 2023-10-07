from Logger import Logger, LogLevel
from discord import Interaction, app_commands

# This transformer allows us to take in a discord id (as the default int is too small)
# and properly convert it to a value that we can use to observe discord servers/users
class TargetIdTransformer(app_commands.Transformer):
    async def transform(self, interaction: Interaction, value: str) -> int:
        if (not value.isnumeric()):
            return -1
        ConvertedValue:int = int(value)
        # Prevent any targets on the bot
        if (ConvertedValue == interaction.client.user.id):
            return -1
        return ConvertedValue

# Simple error handling logger, so that we aren't completely bogging down the application run log with
# errors and such.
async def CommandErrorHandler(interaction: Interaction, error: app_commands.AppCommandError):
    ErrorType = type(error)
    ErrorMsg:str = ""
    InteractionName:str = interaction.command.name
    if (ErrorType == app_commands.CommandOnCooldown):
        ErrorMsg = f"This command {InteractionName} is currently on cooldown"
    elif (ErrorType == app_commands.MissingPermissions):
        ErrorMsg = f"You do not have permissions to use {InteractionName}"
    elif (ErrorType == app_commands.MissingRole):
        ErrorMsg = f"You are missing the roles necessary to run {InteractionName}"
    else:
        Logger.Log(LogLevel.Error, f"Encountered error running command {InteractionName}: {str(error)}")
        ErrorMsg = "An error has occurred while processing your request"
    
    await interaction.response.send_message(ErrorMsg, ephemeral=True, delete_after=5.0)