from datetime import datetime
from BotEnums import BanLookup
from Logger import Logger, LogLevel
from Config import Config
from BotDatabaseSchema import *
from sqlalchemy import create_engine, select, Column, URL, asc, desc
from sqlalchemy.sql import func
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import declarative_base, Session
from sqlalchemy_easy_softdelete.mixin import generate_soft_delete_mixin_class
from sqlalchemy_easy_softdelete.hook import IgnoredTable
from datetime import datetime
import shutil
import time
import os

class ScamBotDatabase():
    Database = None
    
    ### Initialization/Teardown ###
    def __init__(self, *args, **kwargs):
        self.Open()
        
    def __del__(self):
        self.Close()

    def Open(self):
        self.Close()
        ConfigData=Config()

        database_url = URL.create(
            ConfigData.GetDBEngine(),
            username='',
            password='',
            host='',
            database=ConfigData.GetDBName(),
        )
        self.Database = Session(create_engine(database_url).connect())
        
    def Close(self):
        if (self.IsConnected()):
            self.Database.close()
            self.Database = None
            
    def IsConnected(self) -> bool:
        if (self.Database is None):
            return False

        if (self.Database.get_bind().closed):
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
        
        if (Config.GetDBEngine() == "sqlite"):
            # Copy the database file over here
            DestinationLocation = os.path.abspath(Config.GetBackupLocation())
            shutil.copy(os.path.relpath(Config.GetDBName()), DestinationLocation)
            
            # Rename the file
            NewFileName:str = time.strftime("%Y%m%d-%H%M%S.db")
            NewFile = os.path.join(DestinationLocation, NewFileName)
            OriginalFile = os.path.join(DestinationLocation, Config.GetDBName())
            os.rename(OriginalFile, NewFile)
            Logger.Log(LogLevel.Notice, f"Current database has been backed up to new file {NewFileName}")
        else:
            Logger.Log(LogLevel.Notice, f"Non sqlite database backups are not implemented yet")

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
        
        Logger.Log(LogLevel.Notice, f"Cleaned up {BackupsCleaned} backups older than {OlderThan} days!")
                
    ### Adding/Updating/Removing Server Entries ###
    def AddBotGuilds(self, ListOwnerAndServerTuples):
        for Entry in ListOwnerAndServerTuples:
            stmt = select(Server).where(Server.discord_server_id==Entry.id)
            result = self.Database.scalars(stmt).first()

            if (result is not None):
                if (result.deleted_at):
                    Logger.Log(LogLevel.Warn, f"Bot re-added to previously deleted server")
                    result.undelete()
                    self.Database.commit()
            else:
                newServer = Server(
                    discord_server_id = Entry.id,
                    discord_owner_user_id = Entry.owner_id,
                ) 
                self.Database.add(newServer)
        self.Database.commit()
        Logger.Log(LogLevel.Notice, f"Bot had {len(ListOwnerAndServerTuples)} new server updates")
        
    def SetNewServerOwner(self, ServerId:int, NewOwnerId:int):
        stmt = select(Server).where(Server.discord_server_id==ServerId)
        result = self.Database.scalars(stmt).first()

        if (result is None):
            Logger.Log(LogLevel.Warn, f"Bot had attempted to set new owner on non-existant server ")
            return False
        
        result.discord_owner_user_id = NewOwnerId
        self.Database.add(result)
        self.Database.commit()
        return

        
    def RemoveServerEntry(self, ServerId:int):
        stmt = select(Server).where(Server.discord_server_id==ServerId).execution_options(include_deleted=True)
        result = self.Database.scalars(stmt).first()

        if (result is None):
            Logger.Log(LogLevel.Warn, f"Attempted to remove an invalid server id: {ServerId}")
            return False
        
        result.delete()
        self.Database.commit()
        return
    
    def SetBotActivationForOwner(self, OwnerId:int, Servers, IsActive:bool):
        ActivationChanges = []
        ActivationAdditions = []

        for ServerId in Servers:
            stmt = select(Server).where(Server.discord_server_id==ServerId)
            serverToChange = self.Database.scalars(stmt).first()

            if (not self.IsInServer(ServerId)):
                ActivationAdditions.append(ServerId)
                serverToChange = Server(
                    discord_server_id = ServerId,
                    discord_owner_user_id = OwnerId,
                    activation_state = IsActive
                )
            else:
                ActivationChanges.append(ServerId)
                serverToChange.discord_owner_user_id = OwnerId
                serverToChange.activation_state = IsActive
            
            self.Database.add(serverToChange)

        NumActivationAdditions:int = len(ActivationAdditions)
        NumActivationChanges:int = len(ActivationChanges)

        if (NumActivationAdditions > 0):
            Logger.Log(LogLevel.Notice, f"We have {NumActivationAdditions} additions")

        if (NumActivationChanges > 0):
            Logger.Log(LogLevel.Notice, f"Server activation changed in {NumActivationChanges} servers to {str(IsActive)} owned by {OwnerId}")

        self.Database.commit()
        
    ### Reconcile Servers ###
    def ReconcileServers(self, Servers):       
        NewAdditions = []
        ServersIn = []
        for DiscordServer in Servers:
            if (not self.IsInServer(DiscordServer.id)):
                NewAdditions.append(DiscordServer)
            ServersIn.append(DiscordServer.id)
            
        if (len(NewAdditions) > 0):
            self.AddBotGuilds(NewAdditions)

        # Check the current list of servers vs what the database has
        # to see if there are any servers we need to remove
        stmt = select(Server.discord_server_id)
        AllServerIDList = self.Database.execute(stmt).all()
        Logger.Log(LogLevel.Debug, f"Server count: {len(AllServerIDList)} with discord in {len(ServersIn)}")
        for InServerId in AllServerIDList:
            ServerId = InServerId[0]
            try:
                # Remove the servers that we see
                ServersIn.remove(ServerId)
            except ValueError:
                # and add those that we don't have
                ServersIn.append(ServerId)
                continue
        
        if (len(ServersIn) > 0):
            Logger.Log(LogLevel.Notice, f"Bot needs to reconcile {len(ServersIn)} servers from the list")
        else:
            Logger.Log(LogLevel.Debug, "Bot does not need to remove any servers from last run.")
            return

        for ServerToRemove in ServersIn:
            self.RemoveServerEntry(ServerToRemove)
            Logger.Log(LogLevel.Notice, f"Bot has been removed from server {ServerToRemove}")

    ### Query Status ###
    def IsInServer(self, ServerId:int) -> bool:
        stmt = select(Server).where(Server.discord_server_id==ServerId)
        result = self.Database.execute(stmt).scalars(stmt).first()
        if (result is None):
            return False
        return True
    
    def IsActivatedInServer(self, ServerId:int) -> bool:
        if (not self.IsInServer(ServerId)):
            return False

        stmt = select(Server).where(Server.discord_server_id==ServerId)
        result = self.Database.execute(stmt).scalars(stmt).first()
        if (result is None):
            return False

        if (result.activation_state):
            return True
        return False

    def DoesBanExist(self, TargetId:int) -> bool:
        stmt = select(Ban).where(Ban.discord_user_id==TargetId)
        result = self.Database.execute(stmt).scalars(stmt).first()
        if (result is None):
            return False

        return True
    
    # Returns the banner's name, the id and the date
    def GetBanInfo(self, TargetId:int):
        stmt = select(Ban).where(Ban.discord_user_id==TargetId)
        result = self.Database.execute(stmt).scalars(stmt).first()
        if (result is None):
            return False

        return result

    ### Adding/Removing Bans ###
    def AddBan(self, TargetId:int, BannerName:str, BannerId:int) -> BanLookup:
        try:
            if (self.DoesBanExist(TargetId)):
                return BanLookup.Duplicate
        except Exception as ex:
            Logger.Log(LogLevel.Error, f"Got error {str(ex)}")
            return BanLookup.DBError
        
        stmt = select(Ban).where(Ban.target_discord_user_id==TargetId)
        result = self.Database.execute(stmt).scalars(stmt).first()
        if (result is None):
            target = Ban(
                target_discord_user_id = TargetId,
                assigner_discord_user_id = BannerId,
                assigner_discord_user_name = BannerName
            )
            self.Database.add(target)
        else:
            Logger.Log(LogLevel.Warn, f"Ban for {TargetId} was previously reverted; re-applying ban")
            result.undelete()

        self.Database.commit()

        return BanLookup.Good
    
    def RemoveBan(self, TargetId:int):
        try:
            if (not self.DoesBanExist(TargetId)):
                return BanLookup.NotExist
        except Exception as ex:
            Logger.Log(LogLevel.Error, f"Got error {str(ex)}")
            return BanLookup.DBError

        stmt = select(Ban).where(Ban.target_discord_user_id==TargetId)
        result = self.Database.execute(stmt).scalars(stmt).first()
        if (result is None):
            Logger.Log(LogLevel.Warn, f"Tried to remove nonexistant ban for {TargetId}")
            return BanLookup.NotExist
        else:
            result.undelete()

        self.Database.commit()

        return BanLookup.Good
    
    ### Getting Server Information ###
    def GetAllServersOfOwner(self, OwnerId:int):
        stmt = select(Server).where(Server.discord_owner_user_id==OwnerId)
        result = list(self.Database.execute(stmt).scalars(stmt).all())
        if (not len(result)):
            Logger.Log(LogLevel.Warn, f"Failed to load servers for given discord user id of: {OwnerId}!")
        return result
    
    def GetOwnerOfServer(self, ServerId:int) -> int:
        stmt = select(Server).where(Server.discord_server_id==ServerId)
        result = self.Database.execute(stmt).scalars(stmt).first()
        if (result is None):
            Logger.Log(LogLevel.Warn, f"Tried to load owner for non existant server: {ServerId}!")
        return result
    
    def GetAllBans(self, NumLastActions:int=0):
        stmt = select(Ban).order_by(desc(Ban.created_at))
        if (NumLastActions):
            stmt = stmt.limit(NumLastActions)
        return self.Database.execute(stmt).scalars(stmt)
    
    def GetAllServers(self, ActivationState:bool=False):
        stmt = select(Server)
        if (ActivationState):
            stmt = stmt.where(Server.activation_state==ActivationState)
        return self.Database.execute(stmt).scalars(stmt)
    
    def GetAllActivatedServers(self):
        return self.GetAllServers(True)
