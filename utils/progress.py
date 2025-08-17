"""In-memory хранилище прогресса скачиваний (volatile)."""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Optional, Dict

@dataclass
class DownloadProgress:
    job_id: str
    user_id: int
    url: str
    created_at: float = field(default_factory=time.time)
    status: str = "pending"  # pending | downloading | done | error | denied
    bytes_done: int = 0
    total_bytes: int = 0
    message_id: Optional[int] = None
    chat_id: Optional[int] = None
    error: Optional[str] = None

    def percent(self) -> float:
        if self.total_bytes <= 0:
            return 0.0
        return min(100.0, (self.bytes_done / self.total_bytes) * 100)

_store: Dict[str, DownloadProgress] = {}


def create_progress(job: DownloadProgress):
    _store[job.job_id] = job
    return job

def get_progress(job_id: str) -> Optional[DownloadProgress]:
    return _store.get(job_id)

def update_progress(job_id: str, **fields):
    obj = _store.get(job_id)
    if not obj:
        return
    for k, v in fields.items():
        setattr(obj, k, v)
    return obj

def delete_progress(job_id: str):
    _store.pop(job_id, None)

def gc(expire_sec: int = 3600):
    now = time.time()
    to_del = [k for k, v in _store.items() if now - v.created_at > expire_sec]
    for k in to_del:
        _store.pop(k, None)
