"""A tiny time-to-live file cache so scheduled jobs don't hammer free APIs."""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Optional


class FileCache:
    """Namespaced JSON file cache with a TTL, keyed by an arbitrary string."""

    def __init__(self, cache_dir: str, ttl_hours: float = 24.0) -> None:
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_hours * 3600.0
        os.makedirs(cache_dir, exist_ok=True)

    def _path(self, namespace: str, key: str) -> str:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
        safe_ns = "".join(c for c in namespace if c.isalnum() or c in "-_")
        return os.path.join(self.cache_dir, f"{safe_ns}_{digest}.json")

    def get(self, namespace: str, key: str) -> Optional[Any]:
        path = self._path(namespace, key)
        if not os.path.exists(path):
            return None
        try:
            age = time.time() - os.path.getmtime(path)
            if self.ttl_seconds and age > self.ttl_seconds:
                return None
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None

    def set(self, namespace: str, key: str, value: Any) -> None:
        path = self._path(namespace, key)
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(value, fh)
            os.replace(tmp, path)
        except OSError:
            # Cache is best-effort; never fail the run because of it.
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
