import sqlite3
from Logger import LogLevel, Logger

Logger.Log(LogLevel.Notice, "Creating database for scam bot setup")
con = sqlite3.connect("bans.db")

cursor = con.cursor()
cursor.execute("CREATE TABLE banslist(Id, BannerName, BannerId, Date)")
con.commit()
con.close()
Logger.Log(LogLevel.Notice, "Created the ban database!")
