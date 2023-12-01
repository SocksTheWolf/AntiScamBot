import sqlite3
from Config import Config
from Logger import LogLevel, Logger

class DatabaseMigrator:
    DATABASE_VERSION=2
    VersionMap={}
    DatabaseCon=None
    
    def __init__(self):
        self.DatabaseCon = sqlite3.connect(Config.GetDBFile())
        MatchingObjects = [a for a in dir(self) if a.startswith('upgrade_version') and callable(getattr(self, a))]
        for UpgradeFunc in MatchingObjects:
            VersionKeyStr:str = UpgradeFunc.removeprefix("upgrade_version")
            head, _, _ = VersionKeyStr.partition('to')
            VersionNumber:int = int(head)
            self.VersionMap[VersionNumber] = getattr(self, UpgradeFunc)
        
    def __del__(self):
        self.DatabaseCon.close()
    
    def PerformUpgradesFromVersion(self, StartingVersion:int) -> bool:
        for i in range(StartingVersion, self.DATABASE_VERSION):
            # Perform upgrade to version
            Logger.Log(LogLevel.Debug, f"Performing upgrade to version {i}...")
            if (not self.VersionMap[i]()):
                Logger.Log(LogLevel.Error, f"Unable to perform upgrade to version {i}!")
                return False
            Logger.Log(LogLevel.Debug, f"Successfully upgraded to version {i}")
            
        return True
    
    def upgrade_version1to2(self) -> bool:
        cursor = self.DatabaseCon.cursor()
        cursor.execute("ALTER TABLE servers ADD ActivatorId INTEGER default 0")
        cursor.execute("ALTER TABLE servers ADD Instance INTEGER default 0")
        cursor.execute(f"PRAGMA user_version = 2")
        self.DatabaseCon.commit()
        return True

def SetupDatabases():
    Logger.Log(LogLevel.Notice, "Loading database for scam bot setup")
    con = sqlite3.connect(Config.GetDBFile())
    cursor = con.cursor()
    CurrentVersion:int = cursor.execute("PRAGMA user_version").fetchone()[0]
    if (CurrentVersion != 0):
        # Version updating for the database
        if (CurrentVersion != DatabaseMigrator.DATABASE_VERSION):
            NewMigrator = DatabaseMigrator()
            if (not NewMigrator.PerformUpgradesFromVersion(CurrentVersion)):
                exit()
        else:
            Logger.Log(LogLevel.Debug, f"Database version is currently {CurrentVersion}")
            con.close()
            return

    cursor.execute(f"PRAGMA user_version = {DatabaseMigrator.DATABASE_VERSION}")
    cursor.execute("CREATE TABLE if not EXISTS banslist(Id, BannerName, BannerId, Date)")
    cursor.execute("CREATE TABLE if not EXISTS servers(Id, OwnerId, Activated, ActivatorId, Instance)")
    con.commit()
    con.close()
    Logger.Log(LogLevel.Notice, "Created the bot databases!")