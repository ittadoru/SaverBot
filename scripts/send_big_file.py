from telethon import TelegramClient
import asyncio
import os

# Замените на свои значения
api_id = 'YOUR_API_ID'
api_hash = 'YOUR_API_HASH'
session_name = 'userbot_session'  # Файл сессии будет создан в текущей папке

client = TelegramClient(session_name, api_id, api_hash)

async def send_big_file(chat_id, file_path, caption=None):
    if not os.path.exists(file_path):
        print(f"Файл не найден: {file_path}")
        return
    await client.start()
    await client.send_file(chat_id, file_path, caption=caption)
    print(f"Файл {file_path} отправлен в {chat_id}")
    await client.disconnect()

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Использование: python send_big_file.py <chat_id или @username> <путь_к_файлу> [caption]")
        exit(1)
    chat_id = sys.argv[1]
    file_path = sys.argv[2]
    caption = sys.argv[3] if len(sys.argv) > 3 else None
    asyncio.run(send_big_file(chat_id, file_path, caption))
