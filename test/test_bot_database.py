from datetime import datetime
import os
from dotenv import load_dotenv
from BotDatabase import ScamBotDatabase
from BotEnums import BanLookup
from BotSetup import SetupDatabases # importing the module instantly runs the function SetupDatabases
import pytest

@pytest.fixture(scope="session")
def bot_db() -> ScamBotDatabase: 
    load_dotenv()
    bot_db = ScamBotDatabase()
    yield bot_db

    bot_db.Close()
    db_filepath = os.getenv("DATABASE_FILE")
    os.remove(db_filepath)

def test_add_ban(bot_db: ScamBotDatabase):
    test_id = 1
    test_banner = "TestUser"
    test_date = datetime.now()
    db_result = bot_db.AddBan(test_id, test_banner, test_date)
    assert db_result == BanLookup.Good

    db_ban_entry = bot_db.Database.execute(f"SELECT * FROM banslist WHERE Id={test_id}")
    print(db_ban_entry)
    result_tuple = db_ban_entry.fetchone()

    assert result_tuple[0] == test_id
    assert result_tuple[1] == test_banner
