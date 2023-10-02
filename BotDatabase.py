from datetime import datetime
from BotEnums import BanLookup
from Logger import Logger, LogLevel
from Config import Config
import sqlite3

class ScamBotDatabase():
    Database = None
    
    ### Initialization/Teardown ###
    def __init__(self, *args, **kwargs):
        self.Open()
        
    def __del__(self):
        self.Close()

    def Open(self):
        if (self.Database is not None):
            self.Database.close()
            
        self.Database = sqlite3.connect(Config.GetDBFile())
        
    def Close(self):
        if (self.Database is not None):
            self.Database.close()
            self.Database = None
    
    ### Adding/Removing Server Entries ###
    def AddBotGuilds(self, ListOwnerAndServerTuples):
        BotAdditionUpdates = []
        for Entry in ListOwnerAndServerTuples:
            BotAdditionUpdates.append(Entry + (0,))
        
        self.Database.executemany("INSERT INTO servers VALUES(?, ?, ?)", BotAdditionUpdates)
        self.Database.commit()
        Logger.Log(LogLevel.Notice, f"Bot had {len(BotAdditionUpdates)} new server updates")
        
    def RemoveServerEntry(self, ServerId:int):
        if (self.IsInServer(ServerId)):  
            self.Database.execute(f"DELETE FROM servers where Id={ServerId}")
            self.Database.commit()
        else:
            Logger.Log(LogLevel.Warn, f"Attempted to remove server {ServerId} but we are not in that list!")
    
    def SetBotActivationForOwner(self, OwnerId:id, Servers, IsActive:bool):
        ActivationChanges = []
        ActivationAdditions = []
        ActiveVal = int(IsActive)
        ActiveTuple = (ActiveVal,)
        
        for ServerId in Servers:
            if (not self.IsInServer(ServerId)):
                ActivationAdditions.append((ServerId, OwnerId) + ActiveTuple)
            else:
                ActivationChanges.append({"Id": ServerId, "Activated": ActiveVal})
        
        NumActivationAdditions:int = len(ActivationAdditions)
        NumActivationChanges:int = len(ActivationChanges)
        if (NumActivationAdditions > 0):
            Logger.Log(LogLevel.Debug, f"We have {NumActivationAdditions} additions")
            self.Database.executemany("INSERT INTO servers VALUES(?, ?, ?)", ActivationAdditions)
        if (NumActivationChanges > 0):
            self.Database.executemany("UPDATE servers SET Activated=:Activated WHERE Id=:Id", ActivationChanges)
            Logger.Log(LogLevel.Notice, f"Server activation changed in {NumActivationChanges} servers to {str(IsActive)} by {OwnerId}")
        self.Database.commit()
        
    ### Reconcile Servers ###
    def ReconcileServers(self, Servers):       
        NewAdditions = []
        ServersIn = []
        for DiscordServer in Servers:
            if (not self.IsInServer(DiscordServer.id)):
                NewAdditions.append((DiscordServer.id, DiscordServer.owner_id))
            ServersIn.append(DiscordServer.id)
            
        if (len(NewAdditions) > 0):
            self.AddBotGuilds(NewAdditions)
            
        # Check the current list of servers vs what the database has
        # to see if there are any servers we need to remove
        res = self.Database.execute(f"SELECT Id FROM servers")
        AllServerIDList = res.fetchall()
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
            self.Database.execute(f"DELETE FROM servers where Id={ServerId}")
            Logger.Log(LogLevel.Notice, f"Bot has been removed from server {ServerToRemove}")

        self.Database.commit()
        
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
    
    def GetAllBans(self):
        BansListQuery = self.Database.execute(f"SELECT Id FROM banslist")
        return BansListQuery.fetchall()
    
    def GetAllServers(self, ActivatedOnly:bool=False):
        ActivatedFilter:str = ""
        if (ActivatedOnly):
            ActivatedFilter = " WHERE Activated=1"
        AllServersQuery = self.Database.execute(f"SELECT Id, OwnerId, Activated FROM servers{ActivatedFilter}")
        return AllServersQuery.fetchall()
    
    def GetAllActivatedServers(self):
        return self.GetAllServers(True)