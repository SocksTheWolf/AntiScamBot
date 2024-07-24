from sqlalchemy import Column, Integer, DateTime, String
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Migration(Base):
    __tablename__ = "migrations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    database_version = Column(Integer, nullable=False)
    created_at = Column(DateTime(), server_default=func.now())
    updated_at = Column(DateTime(), server_default=func.now(), onupdate=func.now())

class Ban(Base):
    __tablename__ = "bans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    discord_user_id = Column(String(32), unique=True, nullable=False)
    assigner_discord_user_id = Column(String(32), nullable=False)
    assigner_discord_user_name = Column(String(32), nullable=False)
    created_at = Column(DateTime(), server_default=func.now())
    updated_at = Column(DateTime(), server_default=func.now(), onupdate=func.now())

class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_instance_id = Column(Integer, nullable=False, server_default="0")
    discord_server_id = Column(String(32), unique=True, nullable=False)
    owner_discord_user_id = Column(String(32), nullable=False)
    activation_state = Column(Integer, server_default="0")
    activator_discord_user_id = Column(String(32), nullable=False, server_default='-1')
    created_at = Column(DateTime(), server_default=func.now())
    updated_at = Column(DateTime(), server_default=func.now(), onupdate=func.now())
    message_channel = Column(Integer, server_default="0")
    has_webhooks = Column(Integer, server_default="0")
    kick_sus_users = Column(Integer, server_default="0")
