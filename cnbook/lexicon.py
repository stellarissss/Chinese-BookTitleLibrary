"""书名词典与最长前缀切分。

电商标题的典型形态是「书名＋卖点」直接拼接、中间无分隔符：

    盛世锋芒大国重器正版书籍 衔接课内外读懂国之重器培养孩子科学思维书籍

规则式截断在这里无能为力（「正版书籍」出现前已经混进了副标题）。可行的做法是
用一批**已知干净书名**做词典，对原始标题做最长前缀匹配。词典由豆瓣、微信读书
等元数据规范的站点提供，一次构建、反复使用。
"""

from __future__ import annotations

import pickle
from pathlib import Path

from . import textnorm as tn

MAX_PREFIX = 30


class TitleLexicon:
    def __init__(self, titles: set[str] | None = None) -> None:
        # 以去重键索引，避免「红楼梦」与「红楼梦 」因空白不同而漏匹配
        self._keys: set[str] = set()
        self._display: dict[str, str] = {}
        for t in titles or ():
            self.add(t)

    def __len__(self) -> int:
        return len(self._keys)

    def add(self, title: str) -> None:
        t = tn.strip_title_wrap(title)
        key = tn.title_key(t)
        if 2 <= len(key) <= MAX_PREFIX:
            self._keys.add(key)
            self._display.setdefault(key, t)

    def match(self, raw: str) -> str | None:
        """在 raw 的前缀中寻找最长命中，返回词典中的规范写法。"""
        key = tn.title_key(raw)
        if not key:
            return None
        for size in range(min(len(key), MAX_PREFIX), 1, -1):
            head = key[:size]
            if head in self._keys:
                # 命中位置必须落在原文的字符边界上，防止把词切成半个字
                return self._display[head]
        return None

    def contains(self, title: str) -> bool:
        return tn.title_key(title) in self._keys

    # ------------------------------------------------------------ 持久化

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as fh:
            pickle.dump({"keys": self._keys, "display": self._display}, fh, protocol=4)

    @classmethod
    def load(cls, path: Path) -> "TitleLexicon":
        lex = cls()
        if not path.exists():
            return lex
        with path.open("rb") as fh:
            obj = pickle.load(fh)
        lex._keys = obj["keys"]
        lex._display = obj["display"]
        return lex
