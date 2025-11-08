from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Float, BigInteger, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import MetaData
from sqlalchemy import Enum as SQLAlchemyEnum
import enum



# Определяем базовый класс для декларативного стиля
class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'

    user_id = Column(Integer, primary_key=True, unique=True)
    username = Column(String)
    date_of_registration = Column(DateTime)
    language = Column(String)
    status = Column(String)
    balance = Column(String)
    user_first_name = Column(String)


class UserStatus(Base):
    __tablename__ = 'users_status'

    user_id = Column(Integer, primary_key=True, unique=True)
    status = Column(String)
    data = Column(String)
    datetime = Column(DateTime)


class Channel(Base):
    __tablename__ = "channels"
    chat_id = Column(BigInteger, primary_key=True)
    admin_id = Column(BigInteger)                       
    admin_username = Column(String)
    channel_title = Column(String)
    channel_username = Column(String)
    status = Column(String)
    added_by_id = Column(BigInteger)        
    created_at = Column(DateTime)
    chat_type = Column(String)
    bot_status = Column(String)


class ChannelReaction(Base):
    __tablename__ = "channel_reactions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(BigInteger)
    emoji = Column(String)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime)


class ChatReaction(Base):
    """Таблица для хранения реакций на юзеров в чатах"""
    __tablename__ = "chat_reactions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger)
    user_id = Column(BigInteger)                                
    user_name = Column(String)                                    
    user_id_who_installed = Column(BigInteger)                    
    is_myself = Column(Boolean)                                   
    emoji = Column(String)
    created_at = Column(DateTime)                              
    valid_until = Column(DateTime)                              
    duration_reaction_days = Column(BigInteger)                   
    active_only_in_this_chat = Column(Boolean, default=False)     
    active_all = Column(Boolean, default=False)                   


class ReactionHistory(Base):
    """История реакций"""
    __tablename__ = "reaction_history"
    reaction_id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger)
    message_id = Column(BigInteger)
    emoji = Column(String)
    user_id = Column(BigInteger)                              
    created_at = Column(DateTime)


# Создаем движок базы данных (замените строку подключения на вашу)
engine = create_engine('sqlite:///test.db')

Session = sessionmaker(bind=engine)
session = Session()

metadata = MetaData()
metadata.reflect(bind=engine)

Base.metadata.create_all(engine)

print("База данных создана.")
