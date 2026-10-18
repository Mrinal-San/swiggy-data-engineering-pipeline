from __future__ import annotations

import sys
import os
import threading
import time
from collections import OrderedDict
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# Reuse the existing SQL validator and Athena client. This module does not
# create another boto3 client or issue SQL outside the approved query layer.
from text_to_sql import execute_sql, generate_sql, validate_sql  # noqa: E402
from backend.services.response_formatter import json_value

_CACHE_TTL_SECONDS = int(os.getenv("DASHBOARD_CACHE_SECONDS", "300"))
_CACHE_MAX_ENTRIES = 256
_cache: OrderedDict[tuple[str, int], tuple[float, tuple[tuple[tuple[str, object], ...], ...]]] = OrderedDict()
_cache_lock = threading.RLock()


def query_rows(sql: str, max_rows: int = 100) -> list[dict]:
    key = (sql, max_rows)
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(key)
        if cached and cached[0] > now:
            _cache.move_to_end(key)
            return [dict(row) for row in cached[1]]
        if cached:
            _cache.pop(key, None)
    rows = execute_sql(sql, max_rows=max_rows)
    frozen = tuple(tuple((key, json_value(value)) for key, value in row.items()) for row in rows)
    with _cache_lock:
        _cache[key] = (time.monotonic() + _CACHE_TTL_SECONDS, frozen)
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_MAX_ENTRIES:
            _cache.popitem(last=False)
    return [dict(row) for row in frozen]


def clear_query_cache() -> None:
    with _cache_lock:
        _cache.clear()


__all__ = ["query_rows", "clear_query_cache", "generate_sql", "validate_sql", "execute_sql"]
