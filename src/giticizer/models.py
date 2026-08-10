from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class FileChange:
    path: str
    added: int
    deleted: int


@dataclass(frozen=True)
class Commit:
    rev: str
    author: str
    date: date
    message: str
    files: tuple[FileChange, ...]
