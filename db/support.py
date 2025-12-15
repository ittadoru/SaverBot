from sqlalchemy import (
    Column, 
    DateTime, 
    ForeignKey, 
    Integer, 
    BigInteger, 
    String, 
    func, 
    select
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship
from sqlalchemy.exc import SQLAlchemyError

from db.base import Base


class SupportTicket(Base):
    """
    Модель тикета поддержки.
    id: ID тикета
    user_id: ID пользователя
    username: username пользователя
    topic_id: ID темы
    is_closed: 0 = открыт, 1 = закрыт
    created_at: дата создания
    messages: связанные сообщения
    """
    __tablename__ = 'support_tickets'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete="CASCADE"), nullable=False, index=True)
    username = Column(String, nullable=True)
    topic_id = Column(Integer, nullable=False, index=True)
    is_closed = Column(Integer, default=0, nullable=False)  # 0 = Открыт, 1 = Закрыт
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    messages = relationship(
        'SupportMessage', back_populates='ticket', cascade='all, delete-orphan'
    )

    def __repr__(self) -> str:
        return f"<SupportTicket id={self.id} user_id={self.user_id} topic_id={self.topic_id} is_closed={self.is_closed}>"


class SupportMessage(Base):
    """
    Модель сообщения поддержки.
    id: ID сообщения
    ticket_id: ID тикета
    message: текст сообщения
    created_at: дата создания
    ticket: связь с тикетом
    """
    __tablename__ = 'support_messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey('support_tickets.id'))
    message = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    ticket = relationship('SupportTicket', back_populates='messages')

    def __repr__(self) -> str:
        return f"<SupportMessage id={self.id} ticket_id={self.ticket_id} created_at={self.created_at}>"


async def get_open_ticket(
    session: AsyncSession, user_id: int
) -> SupportTicket | None:
    """
    Получает открытый тикет поддержки по ID пользователя.
    """
    query = select(SupportTicket).where(
        SupportTicket.user_id == user_id,
        SupportTicket.is_closed == 0
    )
    result = await session.execute(query)
    return result.scalars().first()


async def create_ticket(
    session: AsyncSession, user_id: int, username: str, topic_id: int
) -> SupportTicket:
    """
    Создаёт новый тикет поддержки, если у пользователя ещё нет открытого.
    Возвращает существующий открытый тикет или вновь созданный.
    """
    existing_ticket = await get_open_ticket(session, user_id)
    if existing_ticket:
        return existing_ticket
    new_ticket = SupportTicket(
        user_id=user_id,
        username=username,
        topic_id=topic_id,
        is_closed=0
    )
    session.add(new_ticket)
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise
    return new_ticket


async def add_message_to_ticket(
    session: AsyncSession, user_id: int, message: str
) -> bool:
    """
    Добавляет сообщение в открытый тикет пользователя.
    """
    ticket = await get_open_ticket(session, user_id)
    if not ticket:
        return False
    new_message = SupportMessage(ticket_id=ticket.id, message=message)
    session.add(new_message)
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        return False
    return True


async def get_ticket_messages(session: AsyncSession, user_id: int) -> list[str]:
    """
    Получает все сообщения из открытого тикета пользователя.
    """
    ticket = await get_open_ticket(session, user_id)
    if not ticket:
        return []
    query = select(SupportMessage).where(
        SupportMessage.ticket_id == ticket.id
    ).order_by(SupportMessage.created_at)
    result = await session.execute(query)
    return [msg.message for msg in result.scalars().all()]


async def close_ticket(session: AsyncSession, user_id: int) -> None:
    """
    Закрывает открытый тикет пользователя.
    """
    ticket = await get_open_ticket(session, user_id)
    if ticket:
        ticket.is_closed = 1
        try:
            await session.commit()
        except SQLAlchemyError:
            await session.rollback()


async def get_ticket_by_topic_id(
    session: AsyncSession, topic_id: int
) -> SupportTicket | None:
    """
    Находит тикет (открытый или закрытый) по его topic_id.
    """
    query = select(SupportTicket).where(SupportTicket.topic_id == topic_id)
    result = await session.execute(query)
    return result.scalars().first()


async def get_open_ticket_by_topic_id(
    session: AsyncSession, topic_id: int
) -> SupportTicket | None:
    """
    Находит открытый тикет по его topic_id.
    """
    query = select(SupportTicket).where(
        SupportTicket.topic_id == topic_id,
        SupportTicket.is_closed == 0
    )
    result = await session.execute(query)
    return result.scalars().first()
