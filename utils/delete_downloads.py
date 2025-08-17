import os

def delete_all_files_in_downloads():
    """Удаляет все файлы в папке downloads."""
    downloads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'downloads')
    deleted = 0
    if os.path.exists(downloads_dir):
        for filename in os.listdir(downloads_dir):
            file_path = os.path.join(downloads_dir, filename)
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                    deleted += 1
                except Exception:
                    pass
    return deleted
