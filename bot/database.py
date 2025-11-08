import asyncio
from datetime import datetime, timedelta, date
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker, DeclarativeBase, relationship
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime, func,  Float, update, BigInteger



DATABASE_URL = 'sqlite+aiosqlite:///../shared/test.db'

'''
Статусы юзеров:
WAITING_USER_CHANNEL_REACTION      # Ожидаем от юзера добавления реакции на канал
WAITING_USER_CHAT_REACTION         # Ожидаем от юзера добавления реакции на сообщение в чате
 
'''

engine = create_async_engine(DATABASE_URL, echo=True, pool_size=20, max_overflow=10, pool_pre_ping=True, pool_recycle=3600)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Base(DeclarativeBase):
    pass


class User(Base):
    """Таблица пользователя"""
    __tablename__ = 'users'

    user_id = Column(Integer, primary_key=True, unique=True)
    username = Column(String)
    date_of_registration = Column(DateTime)
    language = Column(String)
    status = Column(String)
    balance = Column(String)
    user_first_name = Column(String)


class UserStatus(Base):
    """Статусы пользователя. Нужно, чтобы надёжно хранить промежуточные состояния пользователя и не терять в случае перезапуска"""
    __tablename__ = 'users_status'

    user_id = Column(Integer, primary_key=True, unique=True)
    status = Column(String)
    data = Column(String)
    datetime = Column(DateTime)


class Channel(Base):
    """Каналы и чаты"""
    __tablename__ = "channels"
    chat_id = Column(BigInteger, primary_key=True)
    admin_id = Column(BigInteger)                       # Админ
    admin_username = Column(String)
    channel_title = Column(String)
    channel_username = Column(String)
    status = Column(String)
    added_by_id = Column(BigInteger)                    # id того, кто добавил. (в теории, в чат может добавить не админ)
    created_at = Column(DateTime)
    chat_type = Column(String)
    bot_status = Column(String)


class ChannelReaction(Base):
    """Храним реакции, которые нужно ставить на посты"""
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
    user_id = Column(BigInteger)                                  # юзер на которого ставим реакции
    user_name = Column(String)                                    # юзернейм получателя, на всякой случай. Есть вероятность, что юзер на которого ставят, его не будет в базе
    user_id_who_installed = Column(BigInteger)                    # юзер, который установил реакции (предполагается, что можно поставить реакции на других)
    is_myself = Column(Boolean)                                   # поставлена ли реакция на себя самого. Если на себя, то = True если на другого то False
    emoji = Column(String)
    created_at = Column(DateTime)                                 # дата с которой действует
    valid_until = Column(DateTime)                                # дата по которую действует (если юзер поставил не на себя)
    duration_reaction_days = Column(BigInteger)                   # количество дней, которые реакция действует (если реакция не на себя. Если на себя, то вечно = 0)
    active_only_in_this_chat = Column(Boolean, default=False)     # активно только в этом чате
    active_all = Column(Boolean, default=False)                   # активно везде во всех чатах


class ReactionHistory(Base):
    """История реакций"""
    __tablename__ = "reaction_history"
    reaction_id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger)
    message_id = Column(BigInteger)
    emoji = Column(String)
    user_id = Column(BigInteger)                              # если в чате на юзера поставили, то пишет id. Если в канале, то False
    created_at = Column(DateTime)



async def check_and_add_user(user_id: int, username: str, language_code: str, user_first_name: str):
    """Проверка и добавление юзера в базу"""
    date = datetime.now()
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(select(User).filter_by(user_id=user_id))
            user = result.scalar_one_or_none()
            if user is None:
                new_user = User(user_id=user_id, username=username, date_of_registration=date, language=language_code ,status='REGISTERED_ONLY', balance=0, user_first_name=user_first_name)
                session.add(new_user)
                new_user_status = UserStatus(user_id=user_id, status=0)
                session.add(new_user_status)
                await session.commit()
                return True
            return False



async def get_user_status(user_id):
    """Получение статуса юзера"""
    async with async_session() as session:
        async with session.begin():
            user_status = await session.execute(select(UserStatus).filter_by(user_id=user_id))
            user_status = user_status.scalar_one_or_none()
            if not user_status:
                return False
            return user_status


async def set_user_status(user_id, status, data):
    """Установка статуса юзера"""
    date = datetime.now()
    async with async_session() as session:
        async with session.begin():
            user_status = await session.execute(select(UserStatus).filter_by(user_id=user_id))
            user_status = user_status.scalar_one_or_none()
            print(user_status)
            user_status.status = status
            user_status.data = data
            user_status.datetime = date
            await session.commit()
            return True


async def get_user_language(user_id: int):
    """Получает язык пользователя, если он есть в БД"""
    async with async_session() as session:
        async with session.begin():
            user = await session.execute(select(User).filter_by(user_id=user_id))
            user = user.scalar_one_or_none()
            return user.language if user else "en"  # Если не найден юзер, то вернём английский


async def set_user_language(user_id: int, language: str):
    """Меняет язык пользователя в БД"""
    async with async_session() as session:
        async with session.begin():
            user = await session.execute(select(User).filter_by(user_id=user_id))
            user = user.scalar_one_or_none()
            if user:
                user.language = language
            else:
                user = User(user_id=user_id, language=language)
                session.add(user)
            session.commit()


async def get_user_channels(user_id):
    """Получение всех каналов админа"""
    async with async_session() as session:
        async with session.begin():
            user_channels = await session.execute(select(Channel).filter_by(admin_id=user_id))
            user_channels = user_channels.scalars().all()
            if not user_channels:
                return False

            return user_channels


async def get_channel(channel_id):
    """получение данных канала по id"""
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(select(Channel).filter_by(chat_id=channel_id))
            channel = result.scalar_one_or_none()
            return channel


async def bot_add_chat(chat_id, chat_type, bot_status, channel_title, channel_username, admin_id, admin_first_name, admin_username):
    """бота добавили в чат, добавляем запись. Или меняем статус, и обновляем данные админа, если запись уже была"""
    date = datetime.now()
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(select(Channel).filter_by(chat_id=chat_id))
            channel = result.scalar_one_or_none()
            if channel is None:
                new_channel = Channel(chat_id=chat_id, admin_id=admin_id, admin_username=admin_username, channel_title=channel_title, channel_username=channel_username, status=True, added_by_id=admin_id, created_at=date,  chat_type=chat_type, bot_status=bot_status)
                session.add(new_channel)
                if chat_type == 'channel':
                    new_reaction_channel = ChannelReaction(channel_id=chat_id, emoji=0, active=False)
                    session.add(new_reaction_channel)
                elif chat_type == 'group' or 'supergroup':
                    new_chat_reaction = ChatReaction(chat_id=chat_id, user_id=admin_id,
                                                     emoji=False, active_only_in_this_chat=False, active_all=False)
                    session.add(new_chat_reaction)
                await session.commit()
                return True
            else:
                channel.status = True
                channel.channel_title = channel_title
                channel.channel_username = channel_username
                channel.admin_id = admin_id
                channel.admin_first_name = admin_first_name
                channel.admin_username = admin_username
                await session.commit()
                return True


async def bot_delete_chat(chat_id):
    """бота удалили из чата, меняем статус"""
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(select(Channel).filter_by(chat_id=chat_id))
            channel = result.scalar_one_or_none()
            if channel is None:
                channel.status = 'BOT_DELETED'
                await session.commit()
                return True
            return False


async def check_and_get_admin(chat_id):
    """Получение админа канала (на случай если админ сменился, или кто-то подменил запрос)"""
    async with async_session() as session:
        async with session.begin():
            admin = await session.execute(select(Channel.admin_id).filter_by(chat_id=chat_id))
            admin = admin.scalar_one_or_none()
            return admin


async def get_channel_reaction(chat_id):
    """Получаем реакции которые нужно ставить в канале"""
    async with async_session() as session:
        async with session.begin():
            channel_reaction = await session.execute(select(ChannelReaction).filter_by(channel_id=chat_id))
            channel_reaction = channel_reaction.scalar_one_or_none()
            if not channel_reaction:
                return False

            return channel_reaction


async def set_channel_reaction(chat_id, reaction):
    """Запись реакции, которую нужно ставить на посты"""
    date = datetime.now()
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(select(ChannelReaction).filter_by(channel_id=chat_id))
            channel = result.scalar_one_or_none()
            if channel:
                channel.emoji = reaction
                channel.created_at = date
                channel.active = True
                await session.commit()
                return True
            return False


async def add_reaction(chat_id, message_id, reaction, user_id):
    """Запись реакции, которую поставили на пост"""
    date = datetime.now()
    async with async_session() as session:
        async with session.begin():
            reaction = ReactionHistory(chat_id=chat_id, message_id=message_id, emoji=reaction, user_id=user_id, created_at=date)
            session.add(reaction)
            await session.commit()
            return True


async def get_chat_reaction(chat_id, user_id):
    """Получение реакции которую нужно ставить на юзера"""
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(select(ChatReaction).filter_by(chat_id=chat_id, user_id=user_id))
            channel = result.scalar_one_or_none()
            if channel:
                return channel
            return False


async def set_chat_reaction(chat_id, user_id, reaction):
    """Запись реакции, которую нужно ставить на сообщение юзера в чате"""
    date = datetime.now()
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(select(ChatReaction).filter_by(chat_id=chat_id, user_id=user_id))
            chat = result.scalar_one_or_none()
            if chat:
                chat.user_id_who_installed = user_id
                chat.is_myself = True
                chat.emoji = reaction
                chat.created_at = date
                chat.active_only_in_this_chat = True
                chat.active_all = False
                await session.commit()
                return True
            elif chat is None:
                new_chat_reaction = ChatReaction(chat_id=chat_id, user_id=user_id,
                                                 is_myself = True, emoji = reaction, created_at = date, active_only_in_this_chat = True, active_all = False)
                session.add(new_chat_reaction)
                await session.commit()
                return True
            return False


async def get_statistic_reactions_count(chat_id):
    """Получение общего количества реакций"""
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(
                            select(func.count(ReactionHistory.reaction_id))
                            .filter_by(chat_id=chat_id)
                        )
            count = result.scalar()
            print(count, chat_id)

            return count


async def get_statistic_reactions(chat_id):
    """Получаем список из всех типов проставленных реакций"""
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(
                    ReactionHistory.emoji,
                    func.count(ReactionHistory.reaction_id).label('count')
                )
                .filter_by(chat_id=chat_id)
                .group_by(ReactionHistory.emoji)
                .order_by(func.count(ReactionHistory.reaction_id).desc())
            )
            return result.all()


async def get_new_users_24hours():
    '''Получаем новых юзеров которые зашли за последние 24 часа'''
    time_threshold = datetime.utcnow() - timedelta(hours=24)
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(User.date_of_registration)
                .where(User.date_of_registration >= time_threshold))
            last_24h = result.scalars().all()
            last_24h_count = len(last_24h)
            return last_24h_count



# закрытие коннекта с базой
async def close_database():
    await engine.dispose()