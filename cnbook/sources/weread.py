"""微信读书 · 分类树全量枚举。

微信读书是唯一给出**结构化 JSON 书目**的中文电子书目录（书名、著者、译者、出版社、
出版时间、分类俱全），而且分类树接口 `GET /web/categories` 直接暴露全部 187 个叶子类目
与各自书目数（合计约 97 万条）。

列表接口 `GET /web/bookListInCategory/{id}?maxIndex=N` 按 20 条/页返回，但**每个类目
最多翻到 maxIndex=480**（实测 500 起返回空），即单类目上限 500 条。大分类（男频/女频
小说动辄数万条）因此只能拿到前 500 条——这是官方限制，不是本项目的取舍。

即便如此，187 个类目 × 平均约 400 条，也能稳定贡献约 7—8 万条干净的、电商上可能
已经下架的书名，与当当（纸书在售）形成很好的互补。
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from .. import config
from ..net import Session
from .base import Source

CATEGORIES = "https://weread.qq.com/web/categories"
LIST = "https://weread.qq.com/web/bookListInCategory/{cat}?maxIndex={idx}"
STEP = 20
MAX_INDEX = 480


class Weread(Source):
    name = "weread"

    def __init__(self, store) -> None:
        super().__init__(store)
        self.http = Session(referer="https://weread.qq.com/", encoding="utf-8")

    # ------------------------------------------------------------ 类目树

    @staticmethod
    def _leaves(node: dict, path: str, out: list[tuple[str, str, str]]) -> None:
        cid = str(node.get("CategoryId") or "")
        name = node.get("title") or node.get("name") or ""
        sub = node.get("sublist") or node.get("categories") or []
        if not cid:
            return
        if sub:
            for s in sub:
                Weread._leaves(s, f"{path}{name}/", out)
        else:
            out.append((path + name, cid, name))

    def categories(self) -> list[tuple[str, str, str]]:
        resp = self.http.get(CATEGORIES)
        if resp is None:
            return []
        try:
            data = json.loads(resp.text)
        except ValueError:
            return []
        out: list[tuple[str, str, str]] = []
        for grp in data.get("data", []):
            for c in grp.get("categories") or grp.get("sublist") or []:
                self._leaves(c, "", out)
        return out

    # ------------------------------------------------------------ 列表

    def list_page(self, cat_id: str, idx: int) -> list[dict]:
        resp = self.http.get(LIST.format(cat=cat_id, idx=idx))
        if resp is None:
            return []
        try:
            data = json.loads(resp.text)
        except ValueError:
            return []
        out = []
        for item in data.get("books", []):
            info = item.get("bookInfo") or {}
            title = info.get("title") or ""
            if not title:
                continue
            out.append(
                {
                    "source": self.name,
                    "source_id": str(info.get("bookId") or ""),
                    "title_raw": title,
                    "author_raw": info.get("author") or "",
                    "publisher": info.get("publisher") or "",
                    "pub_year": (info.get("publishTime") or "")[:4],
                    "category": info.get("category") or "",
                    "url": info.get("deepLink") or "",
                }
            )
        return out

    def crawl_category(self, path: str, cat_id: str) -> int:
        added = 0
        for idx in range(0, MAX_INDEX + 1, STEP):
            rows = self.list_page(cat_id, idx)
            if not rows:
                break
            added += self.emit(rows)
            if len(rows) < STEP:
                break
        self.store.set_state(self.name, f"cat:{cat_id}", done=1, items=added)
        return added

    # ------------------------------------------------------------ 主流程

    def run(
        self, max_index: int = MAX_INDEX, workers: int | None = None, force: bool = False, **kwargs
    ) -> int:
        cats = self.categories()
        if not cats:
            raise RuntimeError("微信读书分类树不可用")
        print(f"[weread] 发现 {len(cats)} 个叶子类目", flush=True)

        global MAX_INDEX
        MAX_INDEX = max_index
        workers = workers or config.CONCURRENCY
        pending = [
            (p, c)
            for p, c, _ in cats
            if force or not self.store.get_state(self.name, f"cat:{c}")["done"]
        ]
        added = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self.crawl_category, p, c): c for p, c in pending}
            done = 0
            for fut in as_completed(futures):
                done += 1
                try:
                    added += fut.result()
                except Exception:
                    pass
                if done % 20 == 0:
                    print(
                        f"[weread] {done}/{len(pending)}  raw={self.store.count('raw')}",
                        flush=True,
                    )
        return added
