#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《混二》(com.hao.hun) APK 抓取脚本 —— 供 GitHub Actions 在正常网络环境运行。
逆向自 iefans 下载站分发接口：
  openPackage(472,'混二','com.hao.hun',1)
    -> GET https://tz2.xiaota.com/api/download.php  (固定签名 sg/t)
    -> 返回 {"url": "https://apkXX.<cdn>:8010/apk/47/4f/com.hao.hun.apk?md5=..&e=.."}
其中 e 为约 5 分钟的过期时间戳，故取链后必须立即下载。

实现要点：
  * 用 curl（系统证书库）而非 urllib —— 目标站点证书链不完整，Python 验证会失败；
  * 节点轮换 + HEAD 探活，取到可用节点为止；
  * 下载支持 Range 断点续传，遇截断自动重试。
"""
import json
import os
import random
import string
import subprocess
import sys
import urllib.parse

API = "https://tz2.xiaota.com/api/download.php"
REFERER = "https://www.iefans.net/soft/v974051.html"
TT = "1789783089"
SG = "deea8c88bd9c4bb5da5c760c31cf87aa"
PKG_ID, NAME, PACKAGE = "472", "混二", "com.hao.hun"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
OUT = "hun2.apk"


def api_url():
    return API + "?" + urllib.parse.urlencode({
        "package_id": PKG_ID, "name": NAME, "package": PACKAGE,
        "uuid": "".join(random.choices(string.ascii_letters + string.digits, k=28)),
        "refer": "0", "h": "", "x": "1", "referurl": "", "nowurl": REFERER,
        "t": TT, "sg": SG, "r": str(random.random()),
    })


def curl(args, timeout=60):
    """执行 curl，返回 (returncode, stdout_bytes, stderr_text)。"""
    p = subprocess.run(["curl", "-s", "-S", "--max-time", str(timeout)] + args,
                       capture_output=True)
    return p.returncode, p.stdout, p.stderr.decode("utf-8", "replace")


def http_headers(url, extra=None, timeout=30):
    args = ["-k", "-I", "-A", UA, "-H", f"Referer: {REFERER}"]
    for k, v in (extra or {}).items():
        args += ["-H", f"{k}: {v}"]
    args.append(url)
    rc, out, err = curl(args, timeout=timeout)
    return rc, out.decode("utf-8", "replace"), err


def fetch_node_url():
    """轮换取链 + 探活，返回可用 APK 直链。"""
    for i in range(10):
        rc, out, err = curl(["-k", "-A", UA, "-H", f"Referer: {REFERER}", api_url()], timeout=40)
        if rc != 0:
            print(f"[取链] 第{i+1}次 curl 失败: {err.strip()}")
            continue
        try:
            node = json.loads(out.decode("utf-8", "replace")).get("url")
        except Exception as e:
            print(f"[取链] 第{i+1}次解析失败: {e}; 原始: {out[:200]}")
            continue
        if not node:
            print(f"[取链] 第{i+1}次无 url 字段")
            continue
        print(f"[取链] 第{i+1}次: {node}")
        rc2, head, err2 = http_headers(node, timeout=25)
        clen = ""
        for line in head.splitlines():
            if line.lower().startswith("content-length:"):
                clen = line.split(":", 1)[1].strip()
        print(f"[探活] rc={rc2} Content-Length={clen} {err2.strip()[:80]}")
        if rc2 == 0 and clen:
            return node, int(clen)
    return None, 0


def download(url, total):
    """带 Range 断点续传的下载。"""
    got = os.path.getsize(OUT) if os.path.exists(OUT) else 0
    for attempt in range(1, 61):
        extra = {"Range": f"bytes={got}-"} if got else {}
        args = ["-k", "-A", UA, "-H", f"Referer: {REFERER}", "--max-time", "600"]
        for k, v in extra.items():
            args += ["-H", f"{k}: {v}"]
        args += ["-o", "-", url]
        # 用 curl 流式输出到文件
        with open(OUT, "ab" if got else "wb") as f:
            proc = subprocess.Popen(["curl", "-s", "-S"] + args, stdout=f,
                                    stderr=subprocess.PIPE)
            _, err = proc.communicate()
        size = os.path.getsize(OUT)
        print(f"[下载] 第{attempt}次尝试后: {size}/{total} ({100*size//total if total else 0}%)")
        if total and size >= total:
            return size
        if size == got:
            # 没有进展
            print("[下载] 无进展，稍后重试:", err.decode("utf-8", "replace")[:120])
            import time
            time.sleep(2)
        got = size
    return got


def main():
    node, total = fetch_node_url()
    if not node:
        print("取链失败")
        sys.exit(1)
    size = download(node, total)
    print("完成, 大小:", size, "bytes")
    if not total or size < total or size < 20_000_000:
        print(f"警告: 文件不完整 (预期 {total} bytes, 实得 {size})")
        sys.exit(2)


if __name__ == "__main__":
    main()
