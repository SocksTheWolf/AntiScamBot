import asyncio
import os
from dotenv import load_dotenv
from BotEnums import BanLookup
from BotSetup import SetupDatabases # importing the module instantly runs the function SetupDatabases
import pytest
from DiscordBot import DiscordScamBot
from Main import ScamBot, ScamBan, ScamUnban
from discord import Client, Guild, Object
from unittest.mock import patch, AsyncMock, PropertyMock
from requests import Response


@pytest.fixture(scope="function")
def TData() -> dict: 
    load_dotenv()
    #Shared test data
    TUser1 = AsyncMock()
    TUser1.name = "test name"
    TUser1.id = 1

    TUser1Perm = AsyncMock()
    TUser1Perm.administrator = False
    TUser1Perm.manage_guild = False
    TUser1Perm.ban_members = False
    TUser1.guild_permissions = TUser1Perm

    BanUserId = 2
    
    TGuild1 = AsyncMock()
    TGuild1.owner_id = 3
    TGuild1.name = "fake guild 1"
    TGuild1.id = 21

    TGuild2 = AsyncMock()
    TGuild2.owner_id = 4
    TGuild2.name = "fake guild 2"
    TGuild2.id = 22

    yield {
        "TUser1" : TUser1,
        "BanUserId" : BanUserId,
        "TGuild1": TGuild1,
        "TGuild2": TGuild2
    }

    #calling del to close the db connection to clean up
    ScamBot.__del__()
    db_filepath = os.getenv("DATABASE_FILE")
    os.remove(db_filepath)
    SetupDatabases()
    ScamBot.__init__()

@pytest.mark.asyncio
@patch.object(ScamBot, 'PublishAnnouncement')
@patch.object(ScamBot, 'CreateBanEmbed')
@patch('discord.client.Client.fetch_user')
@patch('discord.client.Client.get_guild')
async def TestScamBanUnban(GetGuildMock, FetchUserMock, EmbededMock, PublishMock, TData):
    """
    Tests the following:  
    - When calling PrepareBan() with an id that hasn't been banned, Guild.ban is called with the id and the result is BanLookup.Banned
    - When calling PrepareBan() with an id that already has been banned, Guild.ban is not called and the result is BanLookup.Duplicate
    - When Calling PrepareUnban() with an id that has been banned, Guild.unban is called and the result is BanLookup.Unbanned
    - When Calling PrepareUnban() with an id that has been unbanned, Guild.unban is not called and the result is BanLookup.NotExist
    """

    #setup code
    TBanMock1 = AsyncMock()
    TData["TGuild1"].attach_mock(TBanMock1, 'ban')
    TUnbanMock1 = AsyncMock()
    TData["TGuild1"].attach_mock(TUnbanMock1, 'unban')

    TBanMock2 = AsyncMock()
    TData["TGuild2"].attach_mock(TBanMock2, 'ban')
    TUnbanMock2 = AsyncMock()
    TData["TGuild2"].attach_mock(TUnbanMock2, 'unban')

    GetGuildMock.side_effect = [TData["TGuild1"], TData["TGuild2"], TData["TGuild1"], TData["TGuild2"]]

    ScamBot.Database.SetBotActivationForOwner(TData["TGuild1"].owner_id, [TData["TGuild1"].id], True)
    ScamBot.Database.SetBotActivationForOwner(TData["TGuild2"].owner_id, [TData["TGuild2"].id], True)

    # 1st PrepareBan() test
    FirstBanEnum = await asyncio.wait_for(ScamBot.PrepareBan(TData["BanUserId"], TData["TUser1"]), timeout=5) 
    assert FirstBanEnum == BanLookup.Banned
    TBanMock1.assert_called_once_with(Object(TData["BanUserId"]), reason=f'Confirmed scammer by {TData["TUser1"].name}')
    TBanMock2.assert_called_once_with(Object(TData["BanUserId"]), reason=f'Confirmed scammer by {TData["TUser1"].name}')

    # 2nd PrepareBan() test
    TBanMock1.reset_mock()
    TBanMock2.reset_mock()
    SecondBanEnum = await asyncio.wait_for(ScamBot.PrepareBan(TData["BanUserId"], TData["TUser1"]), timeout=5) 
    assert SecondBanEnum == BanLookup.Duplicate
    TBanMock1.assert_not_called()
    TBanMock2.assert_not_called()

    # PrepareUnban() test
    FirstUnbanEnum = await asyncio.wait_for(ScamBot.PrepareUnban(TData["BanUserId"], TData["TUser1"]), timeout=5)
    assert FirstUnbanEnum == BanLookup.Unbanned 
    TUnbanMock1.assert_called_once_with(Object(TData["BanUserId"]), reason=f'Confirmed non-scammer by {TData["TUser1"].name}')
    TUnbanMock2.assert_called_once_with(Object(TData["BanUserId"]), reason=f'Confirmed non-scammer by {TData["TUser1"].name}')

    # 2nd PrepareUnban() test
    TUnbanMock1.reset_mock()
    TUnbanMock2.reset_mock()
    SecondUnbanEnum = await asyncio.wait_for(ScamBot.PrepareUnban(TData["BanUserId"], TData["TUser1"]), timeout=5)
    assert SecondUnbanEnum == BanLookup.NotExist 
    TUnbanMock1.assert_not_called()
    TUnbanMock2.assert_not_called()

@pytest.mark.asyncio
@patch.object(ScamBot, 'PublishAnnouncement')
@patch.object(ScamBot, 'CreateBanEmbed')
@patch('discord.client.Client.fetch_user')
@patch('discord.client.Client.get_guild')
async def TestActivateServer(GetGuildMock, FetchUserMock,  EmbededMock, PublishMock, TData):
    """
    Tests the following:  
    - When calling PrepareBan() with no servers activated, no ban calls are made
    - When calling ActivateUserServers() for the owner of TGuild1, TGuild1.ban is called while TGuild2.ban is not called due to not having permissions
    """ 
        
    TBanMock1 = AsyncMock()
    TData["TGuild1"].attach_mock(TBanMock1, 'ban')

    TBanMock2 = AsyncMock()
    TData["TGuild2"].attach_mock(TBanMock2, 'ban')
    TData["TGuild2"].fetch_member.return_value = TData["TUser1"]

    GetGuildMock.side_effect = [TData["TGuild1"], TData["TGuild2"]]

    #this is called in the on_guild_join hook with the False option
    ScamBot.Database.SetBotActivationForOwner(TData["TGuild1"].owner_id, [TData["TGuild1"].id], False)
    ScamBot.Database.SetBotActivationForOwner(TData["TGuild2"].owner_id, [TData["TGuild2"].id], False)

    # With no guilds activated, ban functions are not called
    FirstBanEnum = await asyncio.wait_for(ScamBot.PrepareBan(TData["BanUserId"], TData["TUser1"]), timeout=5)
    assert FirstBanEnum == BanLookup.Banned
    TBanMock1.assert_not_called()
    TBanMock2.assert_not_called() 

    type(ScamBot).guilds = [TData["TGuild1"], TData["TGuild2"]]

    # By activating TGuild1 with it's owner, TGuild1 should make a Ban request while TGuild2 should not get a ban request
    await asyncio.wait_for(ScamBot.ActivateUserServers(TData["TGuild1"].owner_id), timeout=5)
    await asyncio.sleep(2)
    TBanMock1.assert_called_once_with(Object(TData["BanUserId"]), reason=f'User banned by {TData["TUser1"].name}')
    TBanMock2.assert_not_called()
