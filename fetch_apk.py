#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《混二》(com.hao.hun) APK 抓取脚本 —— 供 GitHub Actions 在正常网络环境运行。
逆向自 iefans 下载站分发接口：
  openPackage(472,'混二','com.hao.hun',1)
    -> POST/GET https://tz2.xiaota.com/api/download.php  (固定签名 sg/t)
    -> 返回 {"url": "https://apkXX.<cdn>:8010/apk/47/4f/com.hao.hun.apk?md5=..&e=.."}
其中 e 为约 5 分钟的过期时间戳，故取链后必须立即下载。
"""
import json
import random
import string
import sys
import urllib.parse
import urllib.request

API = "https://tz2.xiaota.com/api/download.php"
REFERER = "https://www.iefans.net/soft/v974051.html"
TT = "1789783089"
SG = "deea8c88bd9c4bb5da5c760c31cf87aa"
PKG_ID, NAME, PACKAGE = "472", "混二", "com.hao.hun"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def api_url():
    return API + "?" + urllib.parse.urlencode({
        "package_id": PKG_ID, "name": NAME, "package": PACKAGE,
        "uuid": "".join(random.choices(string.ascii_letters + string.digits, k=28)),
        "refer": "0", "h": "", "x": "1", "referurl": "", "nowurl": REFERER,
        "t": TT, "sg": SG, "r": str(random.random()),
    })


def get(url, timeout=60, extra=None):
    h = {"User-Agent": UA, "Referer": REFERER}
    if extra:
        h.update(extra)
    return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout)


def main():
    # 重试取链（节点会轮换，取到能连的为止）
    apk_url = None
    for i in range(6):
        try:
            with get(api_url()) as r:
                node = json.loads(r.read().decode()).get("url")
            if node:
                print(f"[取链] 第{i+1}次: {node}")
                # 立即探活
                try:
                    print("[探活] HTTP", get(node, timeout=20).status)
                    apk_url = node
                    break
                except Exception as e:
                    print("[探活] 失败，重试:", e)
        except Exception as e:
            print(f"[取链] 第{i+1}次失败:", e)
    if not apk_url:
        print("取链失败"); sys.exit(1)

    # 下载
    with get(apk_url, timeout=600) as r, open("hun2.apk", "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b); got += len(b)
            print(f"\r下载 {got}/{total} ({100*got//total if total else 0}%)", end="", flush=True)
    print()
    print("完成, 大小:", got, "bytes")
    if got < 20_000_000:
        print("警告: 文件偏小(预期约 27.8MB), 可能被截断"); sys.exit(2)


if __name__ == "__main__":
    main()
