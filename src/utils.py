from __future__ import annotations

import hashlib
import json
import platform
import random
import re
import sys
from datetime import datetime
from functools import partial
from os import getenv
from pathlib import Path
from threading import Lock
from typing import Any

from constants import INVALID_ISO8601_FORMAT

print_err = partial(print, file=sys.stderr, flush=True)


def get_config_path() -> Path:
    match platform.system():
        case "Windows":
            return Path(getenv("APPDATA", Path.home() / "AppData" / "Roaming" / "headhunter_automation"))
        case "Darwin":  # macOS
            return Path.home() / "Library" / "Application Support" / "headhunter_automation"
        case _:  # Linux and etc
            return Path(getenv("XDG_CONFIG_HOME", Path.home() / ".config" / "headhunter_automation"))


class AttrDict(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


class Data(dict):
    def __init__(self, config_path: str | Path | None = None):
        self._data_path = Path(config_path or get_config_path()) / "data.json"
        self._lock = Lock()
        self.load()

    def load(self) -> None:
        if self._data_path.exists():
            with self._lock:
                with self._data_path.open("r", encoding="utf-8", errors="replace") as f:
                    self.update(json.load(f))

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.update(*args, **kwargs)
        self._data_path.parent.mkdir(exist_ok=True, parents=True)
        with self._lock:
            with self._data_path.open("w+", encoding="utf-8", errors="replace") as fp:
                json.dump(
                    self,
                    fp,
                    ensure_ascii=True,
                    indent=2,
                    sort_keys=True,
                )

    __getitem__ = dict.get

def truncate_string(s: str, limit: int = 75, ellipsis: str = "…") -> str:
    return s[:limit] + bool(s[limit:]) * ellipsis

def make_hash(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def parse_invalid_datetime(dt: str) -> datetime:
    return datetime.strptime(dt, INVALID_ISO8601_FORMAT)


def fix_datetime(dt: str | None) -> str | None:
    return parse_invalid_datetime(dt).isoformat() if dt is not None else None

def random_text(s: str) -> str:
    while (
        temp := re.sub(
            r"{([^{}]+)}",
            lambda m: random.choice(
                m.group(1).split("|"),
            ),
            s,
        )
    ) != s:
        s = temp
    return s


def parse_interval(interval: str) -> tuple[float, float]:
    """Парсит строку интервала и возвращает кортеж с минимальным и максимальным значениями."""
    if "-" in interval:
        min_interval, max_interval = map(float, interval.split("-"))
    else:
        min_interval = max_interval = float(interval)
    return min(min_interval, max_interval), max(min_interval, max_interval)

class BlockedVacanciesDB:
    """
    Blocked Vacancies database.
    File: <config_dir>/blocked_vacancies.json
    Format: {"blocked": [123, 456, 789]}
    """

    def __init__(self, config_path: str | Path | None = None):
        self._path = Path(config_path or get_config_path()) / "blocked_vacancies.json"
        self._lock = Lock()
        self.blocked: set[int] = set()
        self._load()

    def _load(self) -> None:
        """Load data from JSON."""
        if not self._path.exists():
            return

        with self._lock:
            try:
                with self._path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    items = data.get("blocked", [])
                    if isinstance(items, list):
                        self.blocked = {int(x) for x in items}
            except Exception as e:
                print_err(f"Failed to load blocked vacancies: {e}")

    def _save(self) -> None:
        """Save data to JSON."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            try:
                with self._path.open("w", encoding="utf-8") as f:
                    json.dump(
                        {"blocked": sorted(list(self.blocked))},
                        f,
                        ensure_ascii=False,
                        indent=2
                    )
            except Exception as e:
                print_err(f"Failed to save blocked vacancies: {e}")

    def add(self, vacancy_id: int | str) -> None:
        """Add vacancy to blocked list."""
        vacancy_id = int(vacancy_id)
        if vacancy_id not in self.blocked:
            self.blocked.add(vacancy_id)
            self._save()

    def remove(self, vacancy_id: int | str) -> None:
        """Delete vacancy from blocked list."""
        vacancy_id = int(vacancy_id)
        if vacancy_id in self.blocked:
            self.blocked.remove(vacancy_id)
            self._save()

    def is_blocked(self, vacancy_id: int | str) -> bool:
        """Check, if vacancy is blocked."""
        return int(vacancy_id) in self.blocked

    def list(self) -> list[int]:
        """Retrieve list of all blocked vacancies."""
        return sorted(self.blocked)

    def clear(self) -> None:
        """Clear blocked vacancies list."""
        self.blocked.clear()
        self._save()

    def is_in_list(self, vacancy_id):
        array = self.list()
        return vacancy_id in array
