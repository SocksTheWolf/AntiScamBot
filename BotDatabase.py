from BotEnums import BanLookup
from Logger import Logger, LogLevel
from Config import Config
import shutil, time, os
from BotDatabaseSchema import Ban, Server
from sqlalchemy import create_engine, select, URL, desc, func
from sqlalchemy.orm import Session

class ScamBotDatabase():
    Database = None
    
    ### Initialization/Teardown ###
    def __init__(self, *args, **kwargs):
        self.Open()
        
    def __del__(self):
        self.Close()

    def Open(self):
        self.Close()

        database_url = URL.create(
            'sqlite',
            username='',
            password='',
            host='',
            database=Config.GetDBFile(),
        )
        self.Database = Session(create_engine(database_url))

    def Close(self):
        if (self.IsConnected()):
            self.Database.get_bind().dispose()
            self.Database = None
            
    def IsConnected(self) -> bool:
        if (self.Database is not None):
            return True
        return False
    
    def HasBackupDirectory(self) -> bool:
        DestinationLocation = os.path.abspath(Config.GetBackupLocation())
        if (not os.path.exists(DestinationLocation)):
            return False
        
        return True
    
    def Backup(self) -> bool:
        if (not self.HasBackupDirectory()):
            Logger.Log(LogLevel.Warn, "Backup directory does not exist!!")
            return False
        
        if (self.IsConnected()):
            self.Database.commit()
            self.Close()
        
        # Copy the database file over here
        DestinationLocation = os.path.abspath(Config.GetBackupLocation())
        shutil.copy(os.path.relpath(Config.GetDBFile()), DestinationLocation)
        
        # Rename the file
        NewFileName:str = time.strftime("%Y%m%d-%H%M%S.db")
        NewFile = os.path.join(DestinationLocation, NewFileName)
        OriginalFile = os.path.join(DestinationLocation, Config.GetDBFile())
        os.rename(OriginalFile, NewFile)
        Logger.Log(LogLevel.Log, f"Current database has been backed up to new file {NewFileName}")
        self.Open()
        return True
    
    def CleanupBackups(self):
        if (not self.HasBackupDirectory()):
            return
        
        BackupsCleaned:int = 0
        OlderThan:float = Config()["RemoveDaysOldBackups"]
        BackupLocation = os.path.abspath(Config.GetBackupLocation())
        FileList = os.listdir(BackupLocation)
        FilesOlderThan:float = time.time() - OlderThan * 86400
        for File in FileList:
            FileLocation:str = os.path.join(BackupLocation, File)
            FileModTime:float = os.stat(FileLocation).st_mtime
            if (FileModTime < FilesOlderThan):
                if (os.path.isfile(FileLocation)):
                    Logger.Log(LogLevel.Log, f"Removing file {File}")
                    os.remove(FileLocation)
                    BackupsCleaned += 1
        
        Logger.Log(LogLevel.Log, f"Cleaned up {BackupsCleaned} backups older than {OlderThan} days!")
                
    ### Adding/Updating/Removing Server Entries ###
    def AddBotGuilds(self, ListOwnerAndServerTuples, BotID:int):
        BotAdditionUpdates:list[Server] = []
        for Entry in ListOwnerAndServerTuples:
            server = Server(
                bot_instance_id = BotID,
                discord_server_id = Entry.id,
                owner_discord_user_id = Entry.owner_id,
                activator_discord_user_id = -1
            )
            BotAdditionUpdates.append(server)
        
        self.Database.bulk_save_objects(BotAdditionUpdates)
        self.Database.commit()

        Logger.Log(LogLevel.Notice, f"Bot #{BotID} had {len(BotAdditionUpdates)} new server updates")
        
    def SetNewServerOwner(self, ServerId:int, NewOwnerId:int, BotId:int):
        stmt = select(Server).where((Server.discord_server_id==ServerId) & (Server.bot_instance_id==BotId))
        server = self.Database.scalars(stmt).first()

        if (server is None):
            Logger.Log(LogLevel.Warn, f"Bot #{BotId} attempted to set new owner on non-assigned server: {ServerId}")
            return
        
        server.owner_discord_user_id = NewOwnerId

        self.Database.add(server)
        self.Database.commit()
        
    def AddChannelInformation(self, ServerId:int, ChannelId:int):
        stmt = select(Server).where(Server.discord_server_id==ServerId)
        serverToChange = self.Database.scalars(stmt).first()
        
        if (serverToChange is None):
            Logger.Log(LogLevel.Warn, f"Bot attempted to set channel updates to {ServerId}, but server doesn't exist in db!")
            return
        
        serverToChange.message_channel = ChannelId
        self.Database.add(serverToChange)
        self.Database.commit()
        
    def SetWebhookFlag(self, ServerId:int, WantsWebhooks:bool):
        stmt = select(Server).where(Server.discord_server_id==ServerId)
        serverToChange = self.Database.scalars(stmt).first()
        
        if (serverToChange is None):
            Logger.Log(LogLevel.Warn, f"Bot attempted to set channel updates to {ServerId}, but server doesn't exist in db!")
            return
        
        serverToChange.has_webhooks = 1 if WantsWebhooks else 0
        self.Database.add(serverToChange)
        self.Database.commit()
           
    def RemoveServerEntry(self, ServerId:int, BotId:int):
        stmt = select(Server).where((Server.discord_server_id==ServerId) & (Server.bot_instance_id==BotId))
        server = self.Database.scalars(stmt).first()

        if (server is None):
            Logger.Log(LogLevel.Warn, f"Bot #{BotId} attempted to remove an non-assigned server: {ServerId}")
            return
        
        self.Database.delete(server)
        self.Database.commit()

    def SetBotActivationForOwner(self, Servers:list[int], IsActive:bool, BotId:int, OwnerId:int=-1, ActivatorId:int=-1):
        NumActivationChanges = 0
        NumActivationAdditions = 0
        ActiveVal = int(IsActive)
        
        for ServerId in Servers:
            # If we're not in the server, and we've been given an OwnerId, then create the server
            # IsActive SHOULD be False when passed in this manner
            if (not self.IsInServer(ServerId)):
                if (OwnerId > 0):
                    NumActivationAdditions += 1

                    serverToChange = Server(
                        bot_instance_id = BotId,
                        discord_server_id = ServerId,
                        owner_discord_user_id = OwnerId,
                        activation_state = ActiveVal,
                        activator_discord_user_id = -1, 
                    )

                    self.Database.add(serverToChange)
            # Otherwise, fetch the existing server and update it
            else:
                NumActivationChanges += 1

                stmt = select(Server).where(Server.discord_server_id==ServerId)
                serverToChange = self.Database.scalars(stmt).first()
                
                serverToChange.activation_state = ActiveVal
                serverToChange.activator_discord_user_id = ActivatorId

                self.Database.add(serverToChange)


        if (NumActivationAdditions > 0):
            Logger.Log(LogLevel.Debug, f"We have {NumActivationAdditions} additions")

        if (NumActivationChanges > 0):
            Logger.Log(LogLevel.Notice, f"Server activation changed in {NumActivationChanges} servers to {str(IsActive)} by {ActivatorId}")

        self.Database.commit()
        
    ### Reconcile Servers ###
    def ReconcileServers(self, Servers, BotId:int):       
        NewAdditions = []
        # Discord Guild IDs that we will later use to remove
        ServersIn:list[int] = []
        # Control server id
        ControlServerID:int = Config().ControlServer
        # Loop through all the servers we are in and grab their guild ids
        for DiscordServer in Servers:
            # Check to see if we know about this server already.
            if (not self.IsInServer(DiscordServer.id)):
                NewAdditions.append(DiscordServer)
            
            # Ignore the control server but add any other servers to this list.
            if (DiscordServer.id != ControlServerID):
                ServersIn.append(DiscordServer.id)
        
        # Add any new servers we have found
        if (len(NewAdditions) > 0):
            self.AddBotGuilds(NewAdditions, BotId)

        # Check the current list of servers vs what the database has
        # to see if there are any servers we need to remove
        stmt = select(Server).where((Server.discord_server_id!=ControlServerID) & (Server.bot_instance_id==BotId))
        AllServersWithThisBot = list(self.Database.scalars(stmt).all())
        Logger.Log(LogLevel.Debug, f"Bot #{BotId} server count: {len(AllServersWithThisBot)} with discord in {len(ServersIn)}")
        # Go through all the servers in the database for this bot
        for InServerId in AllServersWithThisBot:
            ServerId = int(InServerId.discord_server_id)
            try:
                # If we are in the server, then we remove the entry from the list of servers
                # we are in. This is because this list will be used later to remove entries that
                # mismatch
                ServersIn.remove(ServerId)
            except ValueError:
                # If the entry fails to be removed from the discord guild list, then
                # it's a floating entry in the database and should be removed.
                ServersIn.append(ServerId)
                continue
                
        if (len(ServersIn) > 0):
            Logger.Log(LogLevel.Notice, f"Bot needs to reconcile {len(ServersIn)} servers from the list")
        else:
            Logger.Log(LogLevel.Debug, "Bot does not need to remove any servers from last run.")
            return

        for ServerToRemove in ServersIn:
            self.RemoveServerEntry(ServerToRemove, BotId)
            Logger.Log(LogLevel.Warn, f"Bot #{BotId} has been removed from server {ServerToRemove}")

    ### Query Status ###
    def IsInServer(self, ServerId:int) -> bool:
        stmt = select(Server).where(Server.discord_server_id==ServerId)
        server = self.Database.scalars(stmt).first()
        if (server is None):
            return False
        return True
    
    def IsActivatedInServer(self, ServerId:int) -> bool:
        if (not self.IsInServer(ServerId)):
            return False

        stmt = select(Server).where(Server.discord_server_id==ServerId)
        server = self.Database.scalars(stmt).first()

        if (server.activation_state):
            return True

        return False

    def DoesBanExist(self, TargetId:int) -> bool:
        stmt = select(Ban).where(Ban.discord_user_id==TargetId)
        result = self.Database.scalars(stmt).first()

        if (result is None):
            return False

        return True
    
    # Returns ban information
    def GetBanInfo(self, TargetId:int) -> Ban:
        stmt = select(Ban).where(Ban.discord_user_id==TargetId)
        return self.Database.scalars(stmt).first()
    
    # Returns server information
    def GetServerInfo(self, ServerId:int) -> Server:
        stmt = select(Server).where(Server.discord_server_id==ServerId)
        return self.Database.scalars(stmt).first()

    ### Adding/Removing Bans ###
    def AddBan(self, TargetId:int, BannerName:str, BannerId:int) -> BanLookup:
        if (self.DoesBanExist(TargetId)):
            return BanLookup.Duplicate

        ban = Ban(
            discord_user_id = TargetId,
            assigner_discord_user_id = BannerId,
            assigner_discord_user_name = BannerName
        )

        self.Database.add(ban)
        self.Database.commit()

        return BanLookup.Good
    
    def RemoveBan(self, TargetId:int) -> BanLookup:
        if (not self.DoesBanExist(TargetId)):
            return BanLookup.NotExist
        
        stmt = select(Ban).where(Ban.discord_user_id==TargetId)
        ban = self.Database.scalars(stmt).first()

        self.Database.delete(ban)
        self.Database.commit()

        return BanLookup.Good
    
    ### Getting Server Information ###
    def GetAllServersOfOwner(self, OwnerId:int) -> list[Server]:
        stmt = select(Server).where(Server.owner_discord_user_id==OwnerId)
        servers = self.Database.scalars(stmt).all()
        
        if (not len(servers)):
            Logger.Log(LogLevel.Warn, f"Failed to load servers for given discord user id of: {OwnerId}!")
        
        return list(servers)
        
    def GetOwnerOfServer(self, ServerId:int) -> int:
        stmt = select(Server).where(Server.discord_server_id==ServerId)
        server = self.Database.scalars(stmt).first()

        if (server is None):
            Logger.Log(LogLevel.Warn, f"Tried to load owner for non existant server: {ServerId}!")
            return None

        return int(server.owner_discord_user_id)
    
    def GetBotIdForServer(self, ServerId:int) -> int:
        stmt = select(Server).where(Server.discord_server_id==ServerId)
        server = self.Database.scalars(stmt).first()

        if (server is None):
            Logger.Log(LogLevel.Warn, f"Tried to load bot instance for non existant server: {ServerId}!")
            return None

        return int(server.bot_instance_id)
    
    def GetChannelIdForServer(self, ServerId:int) -> int:
        stmt = select(Server).where(Server.discord_server_id==ServerId)
        server = self.Database.scalars(stmt).first()

        if (server is None):
            Logger.Log(LogLevel.Warn, f"Tried to load bot instance for non existant server: {ServerId}!")
            return None

        ReturnValue:int = int(server.message_channel)
        if (ReturnValue == 0):
            return None
        
        return ReturnValue

    def GetAllBans(self, NumLastActions:int=0) -> list[Ban]:
        stmt = select(Ban).order_by(desc(Ban.created_at))
        
        if (NumLastActions):
            stmt = stmt.limit(NumLastActions)
        
        return list(self.Database.scalars(stmt).all())
    
    def GetAllServers(self, ActivationState:bool=False, OfInstance:int=-1) -> list[Server]:
        stmt = select(Server)

        if (ActivationState):
            stmt = stmt.where(Server.activation_state==ActivationState)

        if (OfInstance > -1):
            stmt = stmt.where(Server.bot_instance_id==OfInstance)

        return list(self.Database.scalars(stmt).all())
    
    def GetAllActivatedServers(self, OfInstance:int=-1) -> list[Server]:
        return self.GetAllServers(True, OfInstance)
    
    def GetAllDeactivatedServers(self) -> list[Server]:
        stmt = select(Server).where(Server.activation_state==False)

        return list(self.Database.scalars(stmt).all())
    
    ### Stats ###
    def GetNumBans(self) -> int:
        stmt = select(func.count()).select_from(Ban)
        return self.Database.scalars(stmt).first()
    
    def GetNumActivatedServers(self) -> int:
        stmt = select(func.count()).select_from(Server).where(Server.activation_state==True)
        return self.Database.scalars(stmt).first()
    
    def GetNumServers(self) -> int:
        stmt = select(func.count()).select_from(Server)
        return self.Database.scalars(stmt).first()