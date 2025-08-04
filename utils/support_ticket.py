import json

SUPPORT_TICKET_PREFIX = "support_ticket:"


async def create_ticket(redis, bot, user_id: int, username: str, group_id: int) -> int:
    """
    Создает или открывает тикет поддержки для пользователя.
    Если тикет уже есть и закрыт — открывает его заново.
    Возвращает ID темы (topic_id) созданного/существующего тикета.
    """
    ticket_key = f"{SUPPORT_TICKET_PREFIX}{user_id}"
    ticket_data = await redis.get(ticket_key)

    if ticket_data:
        ticket = json.loads(ticket_data)
        # Если тикет закрыт, открываем его заново
        if ticket["status"] != "open":
            ticket["status"] = "open"
            await redis.set(ticket_key, json.dumps(ticket))
        return ticket["topic_id"]

    # Формируем название темы: "@username | user_id" или просто "user_id"
    topic_name = f"@{username} | {user_id}" if username else f"{user_id}"

    # Создаем новую тему форума в группе
    topic = await bot.create_forum_topic(chat_id=group_id, name=topic_name)
    topic_id = topic.message_thread_id

    ticket = {
        "topic_id": topic_id,
        "username": username,
        "status": "open",
    }

    await redis.set(ticket_key, json.dumps(ticket))

    return topic_id


async def get_ticket(redis, user_id: int):
    """
    Получить данные тикета поддержки по user_id.

    """
    ticket_key = f"{SUPPORT_TICKET_PREFIX}{user_id}"
    ticket_data = await redis.get(ticket_key)
    if ticket_data:
        return json.loads(ticket_data)
    return None


async def close_ticket(redis, user_id: int):
    """
    Закрыть тикет поддержки пользователя.

    :param redis: Экземпляр Redis клиента.
    :param user_id: ID пользователя.
    """
    ticket = await get_ticket(redis, user_id)
    if ticket:
        ticket["status"] = "closed"
        await redis.set(f"{SUPPORT_TICKET_PREFIX}{user_id}", json.dumps(ticket))


async def is_ticket_open(redis, user_id: int) -> bool:
    """
    Проверить, открыт ли тикет поддержки для пользователя.

    :param redis: Экземпляр Redis клиента.
    :param user_id: ID пользователя.
    :return: True, если тикет открыт, иначе False.
    """
    ticket = await get_ticket(redis, user_id)
    return ticket and ticket["status"] == "open"


async def get_user_id_by_topic(redis, topic_id: int):
    """
    Найти user_id по topic_id тикета.

    :param redis: Экземпляр Redis клиента.
    :param topic_id: ID темы форума.
    :return: user_id или None, если не найден.
    """
    keys = await redis.keys(f"{SUPPORT_TICKET_PREFIX}*")
    for key in keys:
        ticket_data = await redis.get(key)
        if ticket_data:
            ticket = json.loads(ticket_data)
            if ticket["topic_id"] == topic_id:
                return int(key.split(":")[1])
    return None
