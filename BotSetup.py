import os
import sqlite3
from Config import Config
from Logger import LogLevel, Logger

DATABASE_VERSION=1

def SetupDatabases():
    DatabaseExists:bool = os.path.exists(Config.GetDBFile())
    Logger.Log(LogLevel.Notice, "Creating database for scam bot setup")
    con = sqlite3.connect(Config.GetDBFile())
    cursor = con.cursor()
    CurrentVersion:int = cursor.execute("PRAGMA user_version").fetchone()[0]
    if (CurrentVersion != 0):
        # Version updating for the database
        if (CurrentVersion != DATABASE_VERSION):
            Logger.Log(LogLevel.Error, f"Please run the database update script from version {CurrentVersion} to {DATABASE_VERSION}")
        else:
            Logger.Log(LogLevel.Debug, f"Database version is currently {CurrentVersion}")

    cursor.execute(f"PRAGMA user_version = {DATABASE_VERSION}")
    cursor.execute("CREATE TABLE if not EXISTS banslist(Id, BannerName, BannerId, Date)")
    cursor.execute("CREATE TABLE if not EXISTS servers(Id, OwnerId, Activated)")
    con.commit()
    con.close()
    Logger.Log(LogLevel.Notice, "Created the bot databases!")

SetupDatabases()