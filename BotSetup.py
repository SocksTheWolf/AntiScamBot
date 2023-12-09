from Config import Config
from Logger import LogLevel, Logger
from sqlalchemy import create_engine, select, text, URL, desc
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session
from datetime import datetime
from BotDatabaseSchema import Base, Migration, Ban, Server

class DatabaseMigrator:
    DATABASE_VERSION=3
    VersionMap={}
    DatabaseCon=None
    
    def __init__(self):
        database_url = URL.create(
            'sqlite',
            username='',
            password='',
            host='',
            database=Config.GetDBFile(),
        )

        self.DatabaseCon = create_engine(database_url)

        MatchingObjects = [a for a in dir(self) if a.startswith('upgrade_version') and callable(getattr(self, a))]
        for UpgradeFunc in MatchingObjects:
            VersionKeyStr:str = UpgradeFunc.removeprefix("upgrade_version")
            head, _, _ = VersionKeyStr.partition('to')
            VersionNumber:int = int(head)
            self.VersionMap[VersionNumber] = getattr(self, UpgradeFunc)
        
    def PerformUpgradesFromVersion(self, StartingVersion:int) -> bool:
        for i in range(StartingVersion, self.DATABASE_VERSION):
            # Perform upgrade to version
            Logger.Log(LogLevel.Debug, f"Performing upgrade to version {i+1}...")
            if (not self.VersionMap[i]()):
                Logger.Log(LogLevel.Error, f"Unable to perform upgrade to version {i+1}!")
                return False
            Logger.Log(LogLevel.Debug, f"Successfully upgraded to version {i+1}")
            
        return True
    
    def upgrade_version1to2(self) -> bool:
        session = Session(self.DatabaseCon)
        session.execute(text("ALTER TABLE servers ADD ActivatorId INTEGER default 0"))
        session.execute(text("ALTER TABLE servers ADD Instance INTEGER default 0"))
        session.execute(text(f"PRAGMA user_version = 2"))
        session.commit()
        return True

    def upgrade_version2to3(self) -> bool:
        session = Session(self.DatabaseCon)

        # store banslist and servers in memory
        query = text('select * from banslist')
        banlist = session.execute(query)

        newBanList = []
        for bans in banlist:
            newBan = Ban(
                discord_user_id = bans[0],
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
                bot_instance_id = oldServer[4],
                discord_server_id = oldServer[0],
                owner_discord_user_id = oldServer[1],
                activation_state = oldServer[2],
                activator_discord_user_id = oldServer[3],
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
        Base.metadata.create_all(self.DatabaseCon)

        # insert newly formatted data
        session.bulk_save_objects(newBanList)
        session.bulk_save_objects(newServerList)
        session.commit()

        # remove ban microseconds to match internal (sqlite) datetime(now) format
        query = text('UPDATE bans set created_at = datetime(created_at)')
        session.execute(query) 
        session.commit()

        # store completed migration version
        dbVersion = Migration(
            database_version = self.DATABASE_VERSION
        )
        session.add(dbVersion)
        session.execute(text(f"PRAGMA user_version = 3"))

        session.commit()

        return True

def SetupDatabases():
    Logger.Log(LogLevel.Notice, "Loading database for scam bot setup")
    
    database_url = URL.create(
        'sqlite',
        username='',
        password='',
        host='',
        database='dbtest.db',
    )

    engine = create_engine(database_url)

    session = Session(engine)

    CurrentVersion=0

    # if the old table 'banslist' exists, then it is not using the new ORM versioning scheme and we need to migrate
    # otherwise we are on the new schtema, and can query the the current database version from migration history
    if (inspect(engine).has_table("banslist") == True):
        query = text('PRAGMA user_version')
        CurrentVersion = session.execute(query).first()[0]

    if (inspect(engine).has_table("migrations") == True):
        stmt = select(Migration).order_by(desc(Migration.id))
        CurrentVersion = session.scalars(stmt).first().database_version

    if (CurrentVersion != 0):
        # Version updating for the database
        if (CurrentVersion != DatabaseMigrator.DATABASE_VERSION):
            MigrationManager = DatabaseMigrator()
            if (not MigrationManager.PerformUpgradesFromVersion(CurrentVersion)):
                exit()
        else:
            Logger.Log(LogLevel.Debug, f"Database version is currently {CurrentVersion}")
            return
    else:
        Base.metadata.create_all(engine)

        appVersion = Migration(
            database_version = DatabaseMigrator.DATABASE_VERSION
        )

        session.add(appVersion)
        session.execute(text(f"PRAGMA user_version = {DatabaseMigrator.DATABASE_VERSION}"))
        session.commit()

        Logger.Log(LogLevel.Notice, "Created the bot databases!")
