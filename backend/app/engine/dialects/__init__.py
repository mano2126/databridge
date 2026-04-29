"""DB 방언 구현 패키지 (v10 #9)"""
from .base import (
    DatabaseDialect,
    IndexInfo,
    PKInfo,
    ChunkRange,
    UnsupportedDialect,
    get_dialect,
)

__all__ = [
    "DatabaseDialect",
    "IndexInfo",
    "PKInfo",
    "ChunkRange",
    "UnsupportedDialect",
    "get_dialect",
]
