from datetime import datetime
from BotEnums import BanLookup
from Logger import Logger, LogLevel
from Config import Config
import shutil, time, os
import sqlite3

class ScamBotDatabase():
    Database = None
    
    ### Initialization/Teardown ###
    def __init__(self, *args, **kwargs):
        self.Open()
        
    def __del__(self):
        self.Close()

    def Open(self):
        self.Close()
        self.Database = sqlite3.connect(Config.GetDBFile())
        
    def Close(self):
        if (self.IsConnected()):
            self.Database.close()
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
        Logger.Log(LogLevel.Notice, f"Current database has been backed up to new file {NewFileName}")
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
    def AddBotGuilds(self, ListOwnerAndServerTuples, BotID:int):
        BotAdditionUpdates = []
        for Entry in ListOwnerAndServerTuples:
            BotAdditionUpdates.append(Entry + (-1, 0, BotID))
        
        self.Database.executemany("INSERT INTO servers VALUES(?, ?, ?, ?, ?)", BotAdditionUpdates)
        self.Database.commit()
        Logger.Log(LogLevel.Notice, f"Bot #{BotID} had {len(BotAdditionUpdates)} new server updates")
        
    def SetNewServerOwner(self, ServerId:int, NewOwnerId:int, BotId:int):
        ActivationChanges = []
        ActivationChanges.append({"Id": ServerId, "OwnerId": NewOwnerId, "BotId": BotId})
        self.Database.executemany("UPDATE servers SET OwnerId=:OwnerId WHERE Id=:Id AND Instance=:BotId", ActivationChanges)
        self.Database.commit()
        
    def RemoveServerEntry(self, ServerId:int, BotId:int):
        if (self.IsInServer(ServerId)):  
            self.Database.execute(f"DELETE FROM servers WHERE Id={ServerId} AND Instance={BotId}")
            self.Database.commit()
        else:
            Logger.Log(LogLevel.Warn, f"Attempted to remove server {ServerId} but we are not in that list!")
    
    def SetBotActivationForOwner(self, Servers, IsActive:bool, BotId:int, OwnerId:int=-1, ActivatorId:int=-1):
        ActivationChanges = []
        ActivationAdditions = []
        ActiveVal = int(IsActive)
        
        for ServerId in Servers:
            # This is if in the case of that this is the first time the bot has been added
            # to the server
            if (not self.IsInServer(ServerId)):
                # prevent garbage data from happening
                if (OwnerId > 0):
                    ActivationAdditions.append((ServerId, OwnerId, ActiveVal, ActivatorId, BotId))
            else:
                ActivationChanges.append({"Id": ServerId, "ActivatorId": ActivatorId, "Activated": ActiveVal, "BotId": BotId})
        
        NumActivationAdditions:int = len(ActivationAdditions)
        NumActivationChanges:int = len(ActivationChanges)
        if (NumActivationAdditions > 0):
            Logger.Log(LogLevel.Debug, f"We have {NumActivationAdditions} additions")
            self.Database.executemany("INSERT INTO servers VALUES(?, ?, ?, ?, ?)", ActivationAdditions)
        if (NumActivationChanges > 0):
            self.Database.executemany("UPDATE servers SET Activated=:Activated, ActivatorId=:ActivatorId WHERE Id=:Id AND Instance=:BotId", ActivationChanges)
            Logger.Log(LogLevel.Notice, f"Server activation changed in {NumActivationChanges} servers to {str(IsActive)} by {ActivatorId}")
        self.Database.commit()
        
    ### Reconcile Servers ###
    def ReconcileServers(self, Servers, BotId:int):       
        NewAdditions = []
        # Discord Guild IDs that we will later use to remove
        ServersIn = []
        # Control server id
        ControlServerID:int = Config().ControlServer
        # Loop through all the servers we are in and grab their guild ids
        for DiscordServer in Servers:
            # Check to see if we know about this server already.
            if (not self.IsInServer(DiscordServer.id)):
                NewAdditions.append((DiscordServer.id, DiscordServer.owner_id))
            
            # Ignore the control server but add any other servers to this list.
            if (DiscordServer.id != ControlServerID):
                ServersIn.append(DiscordServer.id)
        
        # Add any new servers we have found
        if (len(NewAdditions) > 0):
            self.AddBotGuilds(NewAdditions, BotId)

        # Check the current list of servers vs what the database has
        # to see if there are any servers we need to remove
        res = self.Database.execute(f"SELECT Id FROM servers WHERE Instance={BotId} AND NOT Id={ControlServerID}")
        AllServersWithThisBot = res.fetchall()
        Logger.Log(LogLevel.Debug, f"Bot #{BotId} server count: {len(AllServersWithThisBot)} with discord in {len(ServersIn)}")
        # Go through all the servers in the database for this bot
        for InServerId in AllServersWithThisBot:
            ServerId = InServerId[0]
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
            self.Database.execute(f"DELETE FROM servers where Id={ServerToRemove} AND Instance={BotId}")
            self.Database.commit()
            Logger.Log(LogLevel.Warn, f"Bot #{BotId} has been removed from server {ServerToRemove}")

    ### Query Status ###
    def IsInServer(self, ServerId:int) -> bool:
        res = self.Database.execute(f"SELECT * FROM servers WHERE Id={ServerId}")
        if (res.fetchone() is None):
            return False
        else:
            return True
    
    def IsActivatedInServer(self, ServerId:int) -> bool:
        if (not self.IsInServer(ServerId)):
            return False
        
        res = self.Database.execute(f"SELECT Activated FROM servers WHERE Id={ServerId}")
        FetchResult = res.fetchone()
        if (FetchResult[0] == 0):
            return False
        else:
            return True

    def DoesBanExist(self, TargetId:int) -> bool:
        result = self.Database.execute(f"SELECT * FROM banslist WHERE Id={TargetId}")
        if (result.fetchone() is None):
            return False
        else:
            return True
    
    # Returns the banner's name, the id and the date
    def GetBanInfo(self, TargetId:int):
        return self.Database.execute(f"SELECT BannerName, BannerId, Date FROM banslist WHERE Id={TargetId}").fetchone()

    ### Adding/Removing Bans ###
    def AddBan(self, TargetId:int, BannerName:str, BannerId:int) -> BanLookup:
        try:
            if (self.DoesBanExist(TargetId)):
                return BanLookup.Duplicate
        except Exception as ex:
            Logger.Log(LogLevel.Error, f"Got error {str(ex)}")
            return BanLookup.DBError
        
        data = [(TargetId, BannerName, BannerId, datetime.now())]
        self.Database.executemany("INSERT INTO banslist VALUES(?, ?, ?, ?)", data)
        self.Database.commit()
        
        return BanLookup.Good
    
    def RemoveBan(self, TargetId:int):
        try:
            if (not self.DoesBanExist(TargetId)):
                return BanLookup.NotExist
        except Exception as ex:
            Logger.Log(LogLevel.Error, f"Got error {str(ex)}")
            return BanLookup.DBError
        
        self.Database.execute(f"DELETE FROM banslist where Id={TargetId}")
        self.Database.commit()
        
        return BanLookup.Good
    
    ### Getting Server Information ###
    def GetAllServersOfOwner(self, OwnerId:int):
        ServersOwnedQuery = self.Database.execute(f"SELECT Activated, Id FROM servers WHERE OwnerId={OwnerId}")
        return ServersOwnedQuery.fetchall()
    
    def GetOwnerOfServer(self, ServerId:int) -> int:
        ServersOwnedQuery = self.Database.execute(f"SELECT OwnerId FROM servers WHERE Id={ServerId}")
        return ServersOwnedQuery.fetchone()[0]
    
    def GetBotIdForServer(self, ServerId:int) -> int:
        ServerIdQuery = self.Database.execute(f"SELECT Instance FROM servers WHERE Id={ServerId}")
        return ServerIdQuery.fetchone()[0]
    
    def GetAllBans(self, NumLastActions:int=0):
        LimitStr:str = ""
        if (NumLastActions > 0):
            LimitStr = f" LIMIT {NumLastActions}"
        BansListQuery = self.Database.execute(f"SELECT Id, BannerName FROM banslist ORDER BY ROWID DESC{LimitStr}")
        return BansListQuery.fetchall()
    
    def GetAllServers(self, ActivatedOnly:bool=False, OfBotInstance:int=-1):
        SearchFilter:str = ""
        if (ActivatedOnly):
            SearchFilter = " WHERE Activated=1"
            if (OfBotInstance > -1):
                SearchFilter = f"{SearchFilter} AND Instance={OfBotInstance}"
        elif (OfBotInstance > -1):
            SearchFilter = f" WHERE Instance={OfBotInstance}"
        
        AllServersQuery = self.Database.execute(f"SELECT Id, OwnerId, Activated, Instance FROM servers{SearchFilter}")
        return AllServersQuery.fetchall()
    
    def GetAllActivatedServers(self, OfInstance:int=-1):
        return self.GetAllServers(True, OfInstance)
    
    def GetAllDeactivatedServers(self):
        AllServersQuery = self.Database.execute(f"SELECT Id, OwnerId, Activated, Instance FROM servers WHERE Activated=0")
        return AllServersQuery.fetchall()