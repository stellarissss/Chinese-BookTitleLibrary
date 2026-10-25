"""数据源适配器的公共契约。

每个源只需实现 `run()`，并通过 `emit()` 交出原始记录。限速、重试、落库、
断点续跑由框架统一处理，源本身不关心存储细节。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

from ..store import Store


class Source(ABC):
    name: str = "base"

    def __init__(self, store: Store) -> None:
        self.store = store

    @abstractmethod
    def run(self, **kwargs) -> int:
        """执行采集，返回本轮新增记录数。"""

    def emit(self, rows: list[dict]) -> int:
        for r in rows:
            r.setdefault("source", self.name)
        return self.store.add_raw(rows)

    # 便捷方法：生成器分块写入，避免一次性占用内存
    @staticmethod
    def chunked(it: Iterator[dict], size: int = 200) -> Iterator[list[dict]]:
        buf: list[dict] = []
        for item in it:
            buf.append(item)
            if len(buf) >= size:
                yield buf
                buf = []
        if buf:
            yield buf
