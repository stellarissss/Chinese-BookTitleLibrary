"""中国国家版本馆 PDC 平台客户端。

PDC（`pdc.capub.cn`）是国家新闻出版署的出版物数据平台，也是目前唯一同时具备
「ISBN 库 400 万 / CIP 库 500 万 / 馆藏样本库 650 万」的中文书目来源。它决定了
这个项目能不能从「爬到 50 万条」跨到「覆盖 1949 年以来的正式出版物」。

**前置条件：需要你自己的账号。** 未登录时接口返回 ``{"status":"failed","msg":"没有用户"}``
（已实测）。请把登录后的 cookie 放进环境变量，代码不读取、不存储任何凭据：

    export CNBOOK_PDC_COOKIE='SESSION=...; other=...'

接口是从平台前端实测出来的（`static/js/chunk-common.*.js`）：

    POST /api/index/searchQuick      关键词检索（分页）
    POST /api/index/searchAdvanced   高级检索（按 ISBN / CIP / 出版年等字段）
    POST /api/index/bookDetail2      单条详情
    POST /api/index/exportSearchQuick 导出（异步任务，结果在「我的-下载中心」）

**使用边界**：仅导出你有权访问的数据；不做高频轮询；不共享账号。
"""

from __future__ import annotations

import json
import os
from typing import Iterator

from ..net import Session
from .base import Source

BASE = "https://pdc.capub.cn"


class Pdc(Source):
    name = "pdc"

    def __init__(self, store) -> None:
        super().__init__(store)
        cookie = os.environ.get("CNBOOK_PDC_COOKIE", "")
        if not cookie:
            raise RuntimeError(
                "缺少 CNBOOK_PDC_COOKIE。请先登录 pdc.capub.cn，把 cookie 放进环境变量。"
            )
        self.http = Session(
            referer=BASE + "/",
            cookie=cookie,
            encoding="utf-8",
            headers={"Origin": BASE, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
        )

    def search(self, keyword: str, page: int = 1, size: int = 20, search_type: str = "marc") -> dict:
        resp = self.http.post(
            f"{BASE}/api/index/searchQuick",
            data={
                "keyword": keyword,
                "pageNum": page,
                "pageSize": size,
                "searchType": search_type,
            },
        )
        if resp is None:
            return {}
        try:
            return json.loads(resp.text)
        except ValueError:
            return {}

    @staticmethod
    def _rows(payload: dict) -> list[dict]:
        """把平台返回的列表项映射成本项目的原始记录结构。

        字段名随平台版本变动，这里只用最稳定的几个；缺失即为空串，
        不猜测、不补全。
        """
        items = payload.get("data", {}).get("list") or payload.get("list") or []
        out = []
        for it in items:
            title = it.get("bookName") or it.get("firstbookname") or ""
            if not title:
                continue
            out.append(
                {
                    "source": "pdc",
                    "source_id": str(it.get("isbn") or it.get("id") or ""),
                    "title_raw": title,
                    "author_raw": it.get("author") or "",
                    "publisher": it.get("publisher") or "",
                    "pub_year": str(it.get("publishDate") or "")[:4],
                    "isbn": it.get("isbn") or "",
                    "category": it.get("cate1") or "",
                    "url": "",
                }
            )
        return out

    def run(self, keywords: list[str] | None = None, **kwargs) -> int:
        """按关键词检索。

        注意：PDC 的检索接口是「按词查」而非「按类目枚举」，用它做全量枚举需要
        海量查询词，不现实。它的正确用法是**按已有书名反查 ISBN**，再走批量套录。
        """
        keywords = keywords or []
        added = 0
        for kw in keywords:
            payload = self.search(kw)
            added += self.emit(self._rows(payload))
        return added

    def batch_export(self, isbns: list[str]) -> str:
        """提交批量套录，返回任务提示信息。

        平台限制单次 5,000 条；命中结果在「我的 → 下载中心 → 数据导出」取。
        这里只做提交，不轮询下载 —— 下载需要人工确认，也更合规。
        """
        resp = self.http.post(
            f"{BASE}/api/index/exportSearchQuick",
            data={
                "ids": ",".join(isbns[:5000]),
                "download": 1,
                "pageSize": len(isbns[:5000]),
                "pageNum": 1,
                "searchType": "marc",
                "exportType": "excel",
            },
        )
        return resp.text if resp is not None else ""
