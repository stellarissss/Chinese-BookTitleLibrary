"""从调试浏览器（CDP）导出并刷新站点 cookie。

当当、孔夫子等站点的防护层会在响应里下发短时效 token（如阿里云的 ``acw_tc``），
裸 curl 拿不到，且过期很快。与其逆向其签发流程，不如让真实浏览器去访问一次，
把 cookie 读出来复用 —— 这是最稳定、也最不激进的做法。
"""

from __future__ import annotations

import json
import time
import urllib.request
from typing import Optional

try:
    from websocket import create_connection
except ImportError:  # pragma: no cover
    create_connection = None

CDP = "http://127.0.0.1:9222"


def _ws() -> Optional[str]:
    try:
        return json.load(urllib.request.urlopen(f"{CDP}/json/version", timeout=3))["webSocketDebuggerUrl"]
    except Exception:
        return None


def _call(ws, method: str, params: dict | None = None) -> dict:
    ws.send(json.dumps({"id": 1, "method": method, "params": params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            return msg


def warmup(url: str, wait: float = 3.0) -> None:
    """让浏览器实际访问一次目标站，触发防护层下发 token。"""
    try:
        tabs = json.load(urllib.request.urlopen(f"{CDP}/json/list", timeout=3))
    except Exception:
        return
    page = next((t for t in tabs if t.get("type") == "page"), None)
    if not page:
        return
    ws_url = page["webSocketDebuggerUrl"]
    if not ws_url:
        return
    ws = create_connection(ws_url, timeout=10)
    try:
        _call(ws, "Page.navigate", {"url": url})
        time.sleep(wait)
    finally:
        ws.close()


def export(domain_fragment: str, url: str = "") -> str:
    """返回 ``name=value; ...`` 形式的 cookie 串。"""
    if create_connection is None:
        return ""
    if url:
        warmup(url)
    ws_url = _ws()
    if not ws_url:
        return ""
    ws = create_connection(ws_url, timeout=10)
    try:
        res = _call(ws, "Storage.getCookies")
        cookies = res.get("result", {}).get("cookies", [])
    finally:
        ws.close()
    pairs = [f"{c['name']}={c['value']}" for c in cookies if domain_fragment in c.get("domain", "")]
    return "; ".join(dict.fromkeys(pairs))
