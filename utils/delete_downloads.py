import os
import aiofiles.os
import asyncio


async def delete_all_files_in_downloads():
    """Асинхронно удаляет все файлы в папке downloads."""
    downloads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'downloads')
    deleted = 0
    if await asyncio.to_thread(os.path.exists, downloads_dir):
        files = await asyncio.to_thread(os.listdir, downloads_dir)
        tasks = []
        for filename in files:
            file_path = os.path.join(downloads_dir, filename)
            if await asyncio.to_thread(os.path.isfile, file_path):
                tasks.append(aiofiles.os.remove(file_path))
                deleted += 1
        if tasks:
            await asyncio.gather(*tasks)
    return deleted
