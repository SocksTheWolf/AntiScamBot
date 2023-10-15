import os
import time
from Config import Config
from Logger import LogLevel, Logger
from sqlalchemy import create_engine, select, Table, Column, Integer, text, DateTime, String, URL, asc, desc
from sqlalchemy.sql import func
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import declarative_base, Session
from sqlalchemy_easy_softdelete.mixin import generate_soft_delete_mixin_class
from sqlalchemy_easy_softdelete.hook import IgnoredTable
from datetime import datetime
from BotDatabaseSchema import *


def SetupDatabases():

    ConfigData=Config()

    if (ConfigData.GetDBEngine() != 'sqlite'):
        Logger.Log(LogLevel.Error, f"Only sqlite databases are currently supported")
        quit()

    database_url = URL.create(
        ConfigData.GetDBEngine(),
        username='',
        password='',
        host='',
        database=ConfigData.GetDBName(),
    )

    engine = create_engine(database_url)

    session = Session(engine)

    # if the old table 'banslist' exists, it is in need of a full version 1 to version 2 migration
    if (inspect(engine).has_table("banslist") == True):
        Logger.Log(LogLevel.Notice, f"Upgrading the bot database to {DATABASE_VERSION}")

        # store banslist and servers in memory
        query = text('select * from banslist')
        banlist = session.execute(query)

        newBanList = []
        for bans in banlist:
            newBan = Ban(
                target_discord_user_id = bans[0],
                assigner_discord_user_id = bans[2],
                assigner_discord_user_name = bans[1],
                # convert old (local python) datetime to utc (in database) datetime
                created_at = datetime.utcfromtimestamp(datetime.timestamp(datetime.strptime(bans[3], '%Y-%m-%d %H:%M:%S.%f')))
            )
            newBanList.append(newBan)
        banlist.close()

        query = text('select * from servers')
        serverlist = session.execute(query)

        newServerList = []
        for oldServer in serverlist:
            newServer = Server(
                discord_server_id = oldServer[0],
                discord_owner_user_id = oldServer[1],
                activation_state = oldServer[2],
            ) 
            newServerList.append(newServer)
        serverlist.close()

        # drop old tables
        query = text('drop table banslist')
        session.execute(query)
        session.commit()

        query = text('drop table servers')
        session.execute(query)
        session.commit()

        # create all the new tables
        Base.metadata.create_all(engine)

        # insert newly formatted data
        session.bulk_save_objects(newBanList)
        session.bulk_save_objects(newServerList)
        session.commit()

        # remove ban microseconds to match internal (sqlite) datetime(now) format
        query = text('UPDATE bans set created_at = datetime(created_at)')
        session.execute(query) 
        session.commit()

        # store completed migration version
        appVersion = Migration(
            database_version = DATABASE_VERSION
        )
        session.add(appVersion)
        session.commit()

    # if migrations table is non existant in database, it is a blank database, so create
    if (inspect(engine).has_table("migrations") == False):
        Logger.Log(LogLevel.Notice, "Creating the bot database!")
        Base.metadata.create_all(engine)

        appVersion = Migration(
            database_version = DATABASE_VERSION
        )
        session.add(appVersion)
        session.commit()

    # future migration logic
    # currentVersion = session.query(Migration).first().database_version
    # if (currentVersion != DATABASE_VERSION):
        # Logger.Log(LogLevel.Warn, f"Upgrading database from {currentVersion} to {DATABASE_VERSION}")

        # placeholder space for future migration loops

SetupDatabases()
