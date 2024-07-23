from Logger import Logger, LogLevel
from discord import Interaction, app_commands

# This transformer allows us to take in a discord id (as the default int is too small)
# and properly convert it to a value that we can use to observe Discord data
class BaseIdTransformer(app_commands.Transformer):
    async def OnTransform(self, interaction: Interaction, TargetId:int) -> int:
        return TargetId
        
    async def transform(self, interaction: Interaction, value: str) -> int:
        if (not value.isnumeric()):
            return -1
        ConvertedValue:int = int(value)
        # Prevent any targets on the bot
        if (ConvertedValue == interaction.client.user.id):
            return -1
        return await self.OnTransform(interaction, ConvertedValue)

# This transformer checks to see if the given id is a real discord User.
class TargetIdTransformer(BaseIdTransformer):
    async def OnTransform(self, interaction: Interaction, TargetId:int) -> int:
        if (await interaction.client.UserAccountExists(TargetId)):
            return TargetId
        else:
            return -1

# This transformer is just a named copy of the BaseIdTransformer
class ServerIdTransformer(BaseIdTransformer):
    pass

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
    elif (ErrorType == app_commands.CheckFailure):
        if (InteractionName == "activate"):
            ErrorMsg = "To activate the bot, type `/scamguard setup`"
        else:
            ErrorMsg = "To change settings, run `/scamguard config`. To uninstall the bot, simply kick it from your server."
    else:
        Logger.Log(LogLevel.Error, f"Encountered error running command /{InteractionName}: {str(error)}")
        ErrorMsg = "An error has occurred while processing your request"
    
    await interaction.response.send_message(ErrorMsg, ephemeral=True, delete_after=5.0)