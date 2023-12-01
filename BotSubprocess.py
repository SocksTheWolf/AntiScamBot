from Logger import Logger, LogLevel
from BotMain import DiscordBot
from Config import Config

def CreateBotProcess(ConnectionLocation, BotID):
    Logger.Log(LogLevel.Log, f"Bot process #{BotID} starting...")
    NewBot:DiscordBot = DiscordBot(ConnectionLocation, BotID)
    # This will block and run forever.
    NewBot.run(Config.GetToken(BotID))