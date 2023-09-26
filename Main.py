from datetime import datetime
# Logging functionality
from Logger import Logger, LogLevel
from enum import IntEnum, auto
from Config import Config
# Discord library
import discord
import sqlite3

# Setup functions
ConfigData=Config()

class BanLookup(IntEnum):
  Banned=auto()
  Unbanned=auto()
  Duplicate=auto()
  NotExist=auto()
  DBError=auto()
  
  def __lt__(self, other):
    if self.__class__ is other.__class__:
      return self.value < other.value
    return NotImplemented
      
  def ToString(self):
    return self.name

# TODO:
# * Queue based action system
# * Async functionality for processing events
# * Something that cleans up the database in the future based off of if the scam accounts are deleted

class DiscordScamBot(discord.Client):
    ControlServer = None
    ApproverRole = None
    # Channel to send updates as to when someone is banned/unbanned
    # this is an announcement channel
    NotificationChannel = None
    Database = None
    CommandList = ["?scamban", "?scamunban", "?scamcheck", "?scamimport"]
    
    def __init__(self, *args, **kwargs):
        self.Database = sqlite3.connect("bans.db")
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        
    def __del__(self):
        Logger.Log(LogLevel.Notice, "Closing the discord scam bot")
        if (self.Database is not None):
            self.Database.close()

    def ReloadConfig(self):
        self.ControlServer = self.get_guild(ConfigData["ControlServer"])
        self.ApproverRole = self.ControlServer.get_role(ConfigData["ApproverRole"])
        self.NotificationChannel = self.get_channel(ConfigData["AnnouncementChannel"])
        Logger.Log(LogLevel.Notice, "Configs loaded")

    def CheckIfCommand(self, text:str):
        for Command in self.CommandList:
            if (text.startswith(Command)):
                return True
        return False

    async def on_ready(self):
        Logger.Log(LogLevel.Log, "Bot is ready to start!")
        self.ReloadConfig()
    
    async def on_guild_join(self, server):
        await self.ReprocessBans(server)
 
    async def on_message(self, message):
        MessageContents:str = message.content
        # If not a command, get out of here
        if (not MessageContents.startswith("?")):
            return

        SplitStr = MessageContents.split(" ")
        # If not formatted with arguments, get out of here as well
        if (len(SplitStr) <= 1):
            return
        
        Command = SplitStr[0]
        TargetIdStr = SplitStr[1]
        if (not self.CheckIfCommand(Command)):
            return
        
        if (not TargetIdStr.isnumeric()):
            await message.reply("The format of this command is incorrect, the userid should be the second value")
            return
        
        # Do not accept DMs, only channel messages
        if (message.guild is None):
            Logger.Log(LogLevel.Warn, f"There is no guild for this server instance!")
            return
        
        Sender = message.author        
        # Senders must also be discord server members, not random users
        if (type(Sender) is not discord.Member):
            Logger.Log(LogLevel.Warn, f"User is not a discord member, this must be a DM")
            return
        
        TargetId = int(TargetIdStr)
        # If this is the control server, then we can have things like commands
        if (message.guild == self.ControlServer):
            IsAdmin = False
            
            if (self.ApproverRole in Sender.roles):
                IsAdmin = True
               
            # If the first bit of the message is the command to ban
            if (Command.startswith("?scamban")):
                if (IsAdmin):
                    Logger.Log(LogLevel.Log, "Scam ban message detected from " + str(Sender))
                    Result = await self.PrepareBan(TargetId, Sender)
                    if (Result is not BanLookup.Banned):
                        if (Result == BanLookup.Duplicate):
                            await message.reply(f"{TargetId} already exists in the ban database")
                        else:
                            await message.reply(f"The given id had an error {str(Result.ToString())}")
                    else:
                        await message.reply(f"The ban for {TargetId} is in progress...")
                else:
                    Logger.Log(LogLevel.Warn, "A scam ban message was sent by a non-admin from " + str(Sender))

                return
            elif (Command.startswith("?scamunban")):
                if (IsAdmin):
                    Logger.Log(LogLevel.Log, "Scam unban message detected from " + str(Sender))
                    Result = await self.PrepareUnban(TargetId, Sender)
                    if (Result is not BanLookup.Unbanned):
                        await message.reply(f"The given id {TargetId} had an error {str(Result.ToString())}")
                    else:
                        await message.reply(f"The unban for {TargetId} is in progress...")
                else:
                    Logger.Log(LogLevel.Warn, "A scam unban message was sent by a non-admin from " + str(Sender))

                return
    
        if (Command.startswith("?scamcheck")):
            if (self.DoesBanExist(TargetId)):
                await message.reply(f"{TargetId} is currently banned")
            else:
                await message.reply(f"{TargetId} is not currently banned")

        elif (Command.startswith("?scamimport") and Sender.id == message.guild.owner_id):
            await self.ReprocessBans(message.guild)

    async def ReprocessBans(self, Server):
        Logger.Log(LogLevel.Log, f"Attempting to reimport ban data to {Server.name}")
        NumBans:int = 0
        for Ban in self.Database.execute(f"SELECT Id FROM banslist"):
            User = discord.Object(int(Ban[0]))
            NumBans += 1
            await self.PerformActionOnServer(Server, User, "User banned by ScamBot", True)
        Logger.Log(LogLevel.Notice, f"Processed {NumBans} bans on join!")
    
    async def PublishNotification(self, Message:str):
        try:
            NewMessage = await self.NotificationChannel.send(Message)
            await NewMessage.publish()
        except discord.HTTPException as ex:
            Logger.Log(LogLevel.Warn, f"Unable to publish message to notification channel {str(ex)}")
        
    def DoesBanExist(self, TargetId:int):
        res = self.Database.execute(f"SELECT * FROM banslist WHERE Id={TargetId}")
        if (res.fetchone() is None):
            return False
        else:
            return True
             
    async def PrepareBan(self, TargetId:int, Sender):
        try:
            if (self.DoesBanExist(TargetId)):
                return BanLookup.Duplicate
        except Exception as ex:
            Logger.Log(LogLevel.Error, f"Got error {str(ex)}")
            return BanLookup.DBError
        SenderId = Sender.id
        
        # Add to database
        data = [
            (TargetId, Sender.display_name, Sender.id, datetime.now()),
        ]
        self.Database.executemany("INSERT INTO banslist VALUES(?, ?, ?, ?)", data)
        self.Database.commit() 
        await self.PropegateActionToServers(TargetId, Sender, True)
        
        # Send a message to the notification channel
        await self.PublishNotification(f"A ban of user {TargetId} was committed by {Sender.display_name}")
        
        return BanLookup.Banned

    async def PrepareUnban(self, TargetId:int, Sender):
        try:
            if (not self.DoesBanExist(TargetId)):
                return BanLookup.NotExist
        except Exception as ex:
            Logger.Log(LogLevel.Error, f"Got error {str(ex)}")
            return BanLookup.DBError
        
        self.Database.execute(f"DELETE FROM banlist where Id={TargetId}")
        await self.PropegateActionToServers(TargetId, Sender, False)
        await self.PublishNotification(f"An Unban of user {TargetId} has started by {Sender.display_name}")
        return BanLookup.Unbanned
    
    async def PerformActionOnServer(self, Server, User, Reason, IsBan:bool) -> bool:
        try:
            BanStr:str = "ban"
            if (not IsBan):
                BanStr = "unban"
            
            Logger.Log(LogLevel.Log, f"Performing {BanStr} action in {Server.name} owned by {Server.owner_id}")
            if (IsBan):
                await Server.ban(User, reason=Reason)
            else:
                await Server.unban(User, reason=Reason)
            return True
        except(discord.NotFound):
            if (not IsBan):
                Logger.Log(LogLevel.Verbose, f"User {User.id} is not banned in server")
                return True
            else:
                Logger.Log(LogLevel.Warn, f"User {User.id} is not a valid user!")
        except(discord.Forbidden):
            Logger.Log(LogLevel.Error, f"We do not have ban/unban permissions in this server!!")
        except(discord.HTTPException):
            Logger.Log(LogLevel.Log, f"We encountered an error while trying to perform for server {Server.name}!")
        return False
        
    async def PropegateActionToServers(self, TargetId:int, Sender, IsBan:bool):
        NumServersPerformed:int = 0
        UserToWorkOn = discord.Object(TargetId)
        ScamStr:str = "scam"
        if (not IsBan):
            ScamStr = "not a scam"
        
        BanReason=f"Reported {ScamStr} by {Sender.display_name}"
        NumServers = len(self.guilds)
        for DiscordServer in self.guilds:
            if (await self.PerformActionOnServer(DiscordServer, UserToWorkOn, BanReason, IsBan)):
                NumServersPerformed += 1

        Logger.Log(LogLevel.Notice, f"Action execution performed in {NumServersPerformed}/{NumServers}")

Bot = DiscordScamBot()
Bot.run(ConfigData.GetToken())