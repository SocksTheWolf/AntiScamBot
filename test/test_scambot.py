import asyncio
import os
from dotenv import load_dotenv
from BotDatabase import ScamBotDatabase
from BotEnums import BanLookup
from BotSetup import SetupDatabases # importing the module instantly runs the function SetupDatabases
import pytest
from DiscordBot import DiscordScamBot
from Main import ScamBot
from discord import Client, Guild, Object, errors
from unittest.mock import patch, AsyncMock
from requests import Response


@pytest.fixture(scope="function")
def setup_data() -> dict: 
    load_dotenv()
    #Shared test data
    banner_mock = AsyncMock()
    banner_mock.name = "test name"
    banner_mock.id = 1

    user_ban_id = 2
    
    fake_guild = AsyncMock()
    fake_guild.owner_id = 3
    fake_guild.name = "fake guild 1"
    fake_guild.id = 21

    fake_guild2 = AsyncMock()
    fake_guild2.owner_id = 4
    fake_guild2.name = "fake guild 2"
    fake_guild2.id = 22

    yield {
        "banner_mock" : banner_mock,
        "user_ban_id" : user_ban_id,
        "fake_guild": fake_guild,
        "fake_guild2": fake_guild2
    }

    #calling del to close the db connection to clean up
    ScamBot.__del__()
    db_filepath = os.getenv("DATABASE_FILE")
    os.remove(db_filepath)
    SetupDatabases()
    ScamBot.__init__()

@pytest.mark.asyncio
@patch.object(ScamBot, 'PublishAnnouncement')
@patch('discord.client.Client.fetch_user')
@patch('discord.client.Client.get_guild')
async def test_scam_ban(get_guild, fetch_user_mock , publish_mock, setup_data):
    """
    Tests the following:  
    - When calling PrepareBan() with an id that hasn't been banned, Guild.ban is called with the id and the result is BanLookup.Banned
    - When calling PrepareBan() with an id that already has been banned, Guild.ban is not called and the result is BanLookup.Duplicate
    - When Calling PrepareUnban() with an id that has been banned, Guild.unban is called and the result is BanLookup.Unbanned
    """

    #setup code
    fake_ban_func = AsyncMock()
    setup_data["fake_guild"].attach_mock(fake_ban_func, 'ban')
    fake_unban_func = AsyncMock()
    setup_data["fake_guild"].attach_mock(fake_unban_func, 'unban')

    fake_ban_func2 = AsyncMock()
    setup_data["fake_guild2"].attach_mock(fake_ban_func2, 'ban')
    fake_unban_func2 = AsyncMock()
    setup_data["fake_guild2"].attach_mock(fake_unban_func2, 'unban')

    get_guild.side_effect = [setup_data["fake_guild"], setup_data["fake_guild2"], setup_data["fake_guild"], setup_data["fake_guild2"]]

    ScamBot.Database.SetBotActivationForOwner(setup_data["fake_guild"].owner_id, [setup_data["fake_guild"].id], True)
    ScamBot.Database.SetBotActivationForOwner(setup_data["fake_guild2"].owner_id, [setup_data["fake_guild2"].id], True)

    # 1st PrepareBan() test
    first_ban_command = await asyncio.wait_for(ScamBot.PrepareBan(setup_data["user_ban_id"], setup_data["banner_mock"]), timeout=5) 
    assert first_ban_command == BanLookup.Banned
    fake_ban_func.assert_called_once_with(Object(setup_data["user_ban_id"]), reason=f'Reported scammer by {setup_data["banner_mock"].name}')
    fake_ban_func2.assert_called_once_with(Object(setup_data["user_ban_id"]), reason=f'Reported scammer by {setup_data["banner_mock"].name}')

    # 2nd PrepareBan() test
    fake_ban_func.reset_mock()
    fake_ban_func2.reset_mock()
    second_ban_command = await asyncio.wait_for(ScamBot.PrepareBan(setup_data["user_ban_id"], setup_data["banner_mock"]), timeout=5) 
    assert second_ban_command == BanLookup.Duplicate
    fake_ban_func.assert_not_called()
    fake_ban_func2.assert_not_called()

    # PrepareUnban() test
    first_unban_command = await asyncio.wait_for(ScamBot.PrepareUnban(setup_data["user_ban_id"], setup_data["banner_mock"]), timeout=5)
    assert first_unban_command == BanLookup.Unbanned 
    fake_unban_func.assert_called_once_with(Object(setup_data["user_ban_id"]), reason=f'Reported non-scammer by {setup_data["banner_mock"].name}')
    fake_unban_func2.assert_called_once_with(Object(setup_data["user_ban_id"]), reason=f'Reported non-scammer by {setup_data["banner_mock"].name}')

@pytest.mark.asyncio
@patch.object(ScamBot, 'PublishAnnouncement')
@patch('discord.client.Client.fetch_user')
@patch('discord.client.Client.get_guild')
async def test_scam_ban_no_permissions(get_guild, fetch_user_mock , publish_mock, setup_data):
    """ Tests the PrepareBan() call when the ban command returns Forbidden Exception """
    #setup code
    forbidden_response = Response()
    forbidden_response.status = 403
    fake_ban_func = AsyncMock()
    fake_ban_func.return_value = errors.Forbidden(forbidden_response, message="Forbidden")
    setup_data["fake_guild"].attach_mock(fake_ban_func, 'ban')

    fake_ban_func2 = AsyncMock()
    fake_ban_func2.return_value = errors.Forbidden(forbidden_response, message="Forbidden")
    setup_data["fake_guild2"].attach_mock(fake_ban_func2, 'ban')

    get_guild.side_effect = [setup_data["fake_guild"], setup_data["fake_guild2"]]

    ScamBot.Database.SetBotActivationForOwner(setup_data["fake_guild"].owner_id, [setup_data["fake_guild"].id], True)
    ScamBot.Database.SetBotActivationForOwner(setup_data["fake_guild2"].owner_id, [setup_data["fake_guild2"].id], True)

    first_ban_command = await asyncio.wait_for(ScamBot.PrepareBan(setup_data["user_ban_id"], setup_data["banner_mock"]), timeout=5) 
    assert first_ban_command == BanLookup.Banned
    fake_ban_func.assert_called_once_with(Object(setup_data["user_ban_id"]), reason=f'Reported scammer by {setup_data["banner_mock"].name}')
    fake_ban_func2.assert_called_once_with(Object(setup_data["user_ban_id"]), reason=f'Reported scammer by {setup_data["banner_mock"].name}')
    #TODO currently no other action is done if ban call returns forbidden due to missing permissions