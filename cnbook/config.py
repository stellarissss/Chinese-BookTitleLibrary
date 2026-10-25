"""全局运行参数。

所有可调项集中在此，避免散落各处的魔法数字。
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("CNBOOK_DATA", ROOT / "data"))
DB_PATH = Path(os.environ.get("CNBOOK_DB", DATA_DIR / "cnbook.sqlite3"))

# 采集速率：对单一站点保持克制的并发与间隔，宁可慢也不触发封禁。
CONCURRENCY = int(os.environ.get("CNBOOK_CONCURRENCY", "3"))
DELAY_MIN = float(os.environ.get("CNBOOK_DELAY_MIN", "0.25"))
DELAY_MAX = float(os.environ.get("CNBOOK_DELAY_MAX", "0.6"))
TIMEOUT = 20
MAX_RETRY = 3

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
]

# 部分站点（当当）对无 cookie 的直连返回 405，需从真实浏览器导出 cookie 后注入。
COOKIE_FILE = Path(os.environ.get("CNBOOK_COOKIE", ROOT / ".cookies.txt"))
