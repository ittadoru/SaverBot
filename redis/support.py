import json
import time
from redis import r
from utils import logger as log


async def create_ticket(user_id: int, username: str, message: str):
    """
    Создать новую тему поддержки с сообщением.
    """
    topic_key = f"support:topic:{user_id}"
    topic = await r.get(topic_key)
    if topic:
        # Тикет уже существует
        return False

    data = {
        "user_id": user_id,
        "username": username,
        "messages": [message],
        "created_at": int(time.time()),
    }
    await r.set(topic_key, json.dumps(data))
    return True

async def add_message_to_ticket(user_id: int, message: str):
    """
    Добавить сообщение в существующий тикет.
    """
    topic_key = f"support:topic:{user_id}"
    topic_json = await r.get(topic_key)
    if not topic_json:
        return False

    topic = json.loads(topic_json)
    topic["messages"].append(message)
    await r.set(topic_key, json.dumps(topic))
    return True

async def get_ticket_messages(user_id: int):
    """
    Получить все сообщения из тикета пользователя.
    """
    topic_key = f"support:topic:{user_id}"
    topic_json = await r.get(topic_key)
    if not topic_json:
        return []

    topic = json.loads(topic_json)
    return topic.get("messages", [])

async def close_ticket(user_id: int):
    """
    Закрыть и удалить тикет.
    """
    topic_key = f"support:topic:{user_id}"
    await r.delete(topic_key)