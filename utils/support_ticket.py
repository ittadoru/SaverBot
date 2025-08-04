import json

SUPPORT_TICKET_PREFIX = "support_ticket:"

async def create_ticket(redis, bot, user_id: int, username: str, group_id: int) -> int:
    ticket_key = f"{SUPPORT_TICKET_PREFIX}{user_id}"
    ticket_data = await redis.get(ticket_key)
    if ticket_data:
        ticket = json.loads(ticket_data)
        # Если тикет закрыт, открываем его снова
        if ticket["status"] != "open":
            ticket["status"] = "open"
            await redis.set(ticket_key, json.dumps(ticket))
        return ticket["topic_id"]

    topic_name = f"@{username} | {user_id}" if username else f"{user_id}"
    topic = await bot.create_forum_topic(chat_id=group_id, name=topic_name)
    topic_id = topic.message_thread_id

    ticket = {
        "topic_id": topic_id,
        "username": username,
        "status": "open"
    }
    await redis.set(ticket_key, json.dumps(ticket))
    return topic_id

async def get_ticket(redis, user_id: int):
    ticket_key = f"{SUPPORT_TICKET_PREFIX}{user_id}"
    ticket_data = await redis.get(ticket_key)
    if ticket_data:
        return json.loads(ticket_data)
    return None

async def close_ticket(redis, user_id: int):
    ticket = await get_ticket(redis, user_id)
    if ticket:
        ticket["status"] = "closed"
        await redis.set(f"{SUPPORT_TICKET_PREFIX}{user_id}", json.dumps(ticket))

async def is_ticket_open(redis, user_id: int) -> bool:
    ticket = await get_ticket(redis, user_id)
    return ticket and ticket["status"] == "open"

async def get_user_id_by_topic(redis, topic_id: int):
    keys = await redis.keys(f"{SUPPORT_TICKET_PREFIX}*")
    for key in keys:
        ticket_data = await redis.get(key)
        if ticket_data:
            ticket = json.loads(ticket_data)
            if ticket["topic_id"] == topic_id:
                return int(key.split(":")[1])
    return None