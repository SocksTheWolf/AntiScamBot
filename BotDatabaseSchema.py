from sqlalchemy import Table, Column, Integer, Text, DateTime, String
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base, Session
from sqlalchemy_easy_softdelete.mixin import generate_soft_delete_mixin_class
from sqlalchemy_easy_softdelete.hook import IgnoredTable
from datetime import datetime

DATABASE_VERSION = 2

Base = declarative_base()


class SoftDeleteMixin(generate_soft_delete_mixin_class(

    #ignored_tables=[IgnoredTable(table_schema="public", name="cars"),]

)):
    # type hint for autocomplete IDE support
    deleted_at: datetime

class Migration(Base):
    __tablename__ = "migrations"

    id = Column(Integer,primary_key=True, autoincrement=True)
    database_version = Column(Integer, nullable=False)
    created_at = Column(DateTime(),  server_default=func.now())
    updated_at = Column(DateTime(),  server_default=func.now(), onupdate=func.now())

class Ban(Base, SoftDeleteMixin):
    __tablename__ = "bans"

    id = Column(Integer,primary_key=True, autoincrement=True)
    target_discord_user_id = Column(String(32), unique=True, nullable=False)
    assigner_discord_user_id = Column(String(32), nullable=False)
    assigner_discord_user_name = Column(String(32), nullable=False)
    created_at = Column(DateTime(),  server_default=func.now())
    updated_at = Column(DateTime(),  server_default=func.now(), onupdate=func.now())

class Server(Base, SoftDeleteMixin):
    __tablename__ = "servers"

    id = Column(Integer,primary_key=True, autoincrement=True)
    discord_server_id = Column(String(32), unique=True, nullable=False)
    discord_owner_user_id = Column(String(32), nullable=False)
    activation_state = Column(Integer, server_default="0")
    created_at = Column(DateTime(),  server_default=func.now())
    updated_at = Column(DateTime(),  server_default=func.now(), onupdate=func.now())
