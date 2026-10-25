"""限速 HTTP 会话。

设计要点
--------
1. 全局限速：令牌桶 + 随机抖动，避免固定节奏被识别为爬虫。
2. 失败重试：仅对网络错误与 5xx/429 重试，4xx 直接放弃（重试无意义）。
3. 编码纠正：当当等站长年使用 GBK 且不在响应头声明，需按站点显式指定。
4. Cookie 注入：部分站点对裸请求返回 405，需携带浏览器导出的 cookie。
"""

from __future__ import annotations

import random
import threading
import time
from pathlib import Path
from typing import Optional

import requests

from . import config


class RateLimiter:
    """进程级全局限速器，保证所有线程合计不超过设定速率。"""

    def __init__(self, delay_min: float, delay_max: float) -> None:
        self._min = delay_min
        self._max = delay_max
        self._lock = threading.Lock()
        self._next_at = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            if now < self._next_at:
                time.sleep(self._next_at - now)
                now = time.monotonic()
            self._next_at = now + random.uniform(self._min, self._max)


_LIMITER = RateLimiter(config.DELAY_MIN, config.DELAY_MAX)


def load_cookie_header(path: Optional[Path] = None) -> str:
    """读取 `name=value; name2=value2` 形式的 cookie 串，缺失时返回空串。"""
    path = path or config.COOKIE_FILE
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


class Session:
    """线程安全的轻量 HTTP 客户端。"""

    def __init__(
        self,
        referer: str = "",
        cookie: str = "",
        encoding: Optional[str] = None,
        headers: Optional[dict] = None,
        refresh=None,
    ) -> None:
        self.referer = referer
        self.encoding = encoding
        self._cookie = cookie
        self._extra = headers or {}
        self._refresh = refresh          # callable -> 新的 cookie 串
        self._refreshed_at = 0.0
        self._local = threading.local()

    @property
    def _session(self) -> requests.Session:
        if not hasattr(self._local, "s"):
            s = requests.Session()
            s.headers.update(
                {
                    "User-Agent": random.choice(config.USER_AGENTS),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "Connection": "keep-alive",
                }
            )
            if self.referer:
                s.headers["Referer"] = self.referer
            if self._cookie:
                s.headers["Cookie"] = self._cookie
            s.headers.update(self._extra)
            self._local.s = s
        return self._local.s

    def get(self, url: str, **kwargs) -> Optional[requests.Response]:
        for attempt in range(config.MAX_RETRY):
            _LIMITER.wait()
            if self._cookie:
                self._session.headers["Cookie"] = self._cookie
            try:
                resp = self._session.get(url, timeout=config.TIMEOUT, **kwargs)
            except requests.RequestException:
                if attempt == config.MAX_RETRY - 1:
                    return None
                time.sleep(1.5 * (attempt + 1))
                continue

            # 防护层拦截：刷新一次 cookie 后重试
            if resp.status_code in (403, 405) and self._refresh:
                if time.monotonic() - self._refreshed_at > 5:
                    self._refreshed_at = time.monotonic()
                    new_cookie = self._refresh()
                    if new_cookie:
                        self._cookie = new_cookie
                        continue
                return None

            if resp.status_code in (429, 500, 502, 503, 504) and attempt < config.MAX_RETRY - 1:
                time.sleep(2.0 * (attempt + 1))
                continue
            if resp.status_code >= 400:
                return None

            if self.encoding:
                resp.encoding = self.encoding
            elif not resp.encoding or resp.encoding.lower() == "iso-8859-1":
                resp.encoding = resp.apparent_encoding
            return resp
        return None

    def post(self, url: str, **kwargs) -> Optional[requests.Response]:
        for attempt in range(config.MAX_RETRY):
            _LIMITER.wait()
            try:
                resp = self._session.post(url, timeout=config.TIMEOUT, **kwargs)
            except requests.RequestException:
                if attempt == config.MAX_RETRY - 1:
                    return None
                time.sleep(1.5 * (attempt + 1))
                continue
            if resp.status_code >= 500 and attempt < config.MAX_RETRY - 1:
                time.sleep(2.0 * (attempt + 1))
                continue
            if resp.status_code >= 400:
                return None
            return resp
        return None
