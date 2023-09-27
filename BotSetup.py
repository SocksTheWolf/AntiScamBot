import os
import sqlite3
from Logger import LogLevel, Logger

def SetupDatabases():
    if (os.path.exists("bans.db")):
        Logger.Log(LogLevel.Debug, "Database already exists!")
        return
    
    Logger.Log(LogLevel.Notice, "Creating database for scam bot setup")
    con = sqlite3.connect("bans.db")

    cursor = con.cursor()
    cursor.execute("CREATE TABLE if not exists banslist(Id, BannerName, BannerId, Date)")
    cursor.execute("CREATE TABLE if not exists servers(Id, OwnerId, Activated)")
    con.commit()
    con.close()
    Logger.Log(LogLevel.Notice, "Created the bot databases!")

SetupDatabases()