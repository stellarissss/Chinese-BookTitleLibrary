"""当当网图书分类全量遍历。

当当的分类页是少数仍然服务端渲染、且给出结构化著者/出版信息的电商页面，
单页 60 条、单类最多 100 页。

遍历策略是**逐层下钻**，而不是把所有三级类目翻到第 100 页：

* 一个三级类目通常只有 100—200 本书，翻到第 3—4 页就见底；
* 真正的大类（文学、童书）的书都挂在四级、五级子类目下面。

所以每层先把这个类目翻到见底，再从它的页面里取出下一层子类目继续。这样
请求量随「书的数量」增长，而不是随「页码上限」增长。

每个类目爬完即写入 ``crawl_state``，中断后重跑会跳过已完成的类目。
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from .. import browser_cookie, config
from ..net import Session, load_cookie_header
from .base import Source

HOME = "https://book.dangdang.com/"
CAT = "https://category.dangdang.com/cp{id}.html"
CAT_PAGE = "https://category.dangdang.com/pg{page}-cp{id}.html"

_RE_CAT = re.compile(r"category\.dangdang\.com/cp(\d+(?:\.\d+){5})\.html")
_RE_ITEM = re.compile(r'<li[^>]*id="p(\d+)"[^>]*>(.*?)</li>', re.S)
_RE_TITLE = re.compile(r'title="([^"]*)"')
_RE_AUTHOR = re.compile(r"itemlist-author'?\"?[^>]*?title=['\"]([^'\"]*)")
_RE_PRESS = re.compile(r"P_cbs'?\"?[^>]*?title=['\"]([^'\"]*)")
_RE_DATE = re.compile(r"/\s*(\d{4})-(\d{1,2})-(\d{1,2})")

MAX_DEPTH_LEVELS = 3


class Dangdang(Source):
    name = "dangdang"

    def __init__(self, store) -> None:
        super().__init__(store)
        self.http = Session(
            referer="https://book.dangdang.com/",
            cookie=load_cookie_header() or browser_cookie.export("dangdang", HOME),
            encoding="gbk",
            refresh=lambda: browser_cookie.export("dangdang", HOME),
        )

    # ------------------------------------------------------------ 类目

    def discover(self) -> list[str]:
        resp = self.http.get(HOME)
        if resp is None:
            raise RuntimeError("当当首页不可达，请先用浏览器导出 cookie 到 .cookies.txt")
        return sorted(set(_RE_CAT.findall(resp.text)))

    @staticmethod
    def _children(html: str, parent: str) -> list[str]:
        """从类目页里取出下一层子类目。

        当当的类目码是 6 段定长编码（``01.01.01.00.00.00``），尾部 ``00`` 是占位。
        子类目的判据是：与父级共享全部有效段，且下一个段位不为 ``00``。
        """
        core: list[str] = []
        for seg in parent.split("."):
            if seg == "00" and core:
                break
            core.append(seg)

        out = []
        for cid in set(_RE_CAT.findall(html)):
            segs = cid.split(".")
            if len(segs) != 6 or len(core) >= 6:
                continue
            if segs[: len(core)] == core and segs[len(core)] not in ("00", ""):
                out.append(cid)
        return sorted(out)

    # ------------------------------------------------------------ 列表页

    def fetch_page(self, cat_id: str, page: int) -> tuple[list[dict], str]:
        url = CAT.format(id=cat_id) if page == 1 else CAT_PAGE.format(page=page, id=cat_id)
        resp = self.http.get(url)
        if resp is None:
            return [], ""
        html = resp.text
        out = []
        for pid, body in _RE_ITEM.findall(html):
            m = _RE_TITLE.search(body)
            if not m:
                continue
            author = _RE_AUTHOR.search(body)
            press = _RE_PRESS.search(body)
            date = _RE_DATE.search(body)
            out.append(
                {
                    "source": self.name,
                    "source_id": pid,
                    "title_raw": m.group(1).strip(),
                    "author_raw": author.group(1) if author else "",
                    "publisher": press.group(1) if press else "",
                    "pub_year": date.group(1) if date else "",
                    "category": cat_id,
                    "url": f"https://product.dangdang.com/{pid}.html",
                }
            )
        return out, html

    def crawl_category(self, cat_id: str, max_pages: int) -> tuple[int, list[str], bool]:
        """翻完一个类目。返回 (新增条数, 子类目, 是否已见底)。"""
        added = 0
        children: list[str] = []
        exhausted = False
        for page in range(1, max_pages + 1):
            rows, html = self.fetch_page(cat_id, page)
            if page == 1 and html:
                children = self._children(html, cat_id)
            if not rows:
                exhausted = True
                break
            added += self.emit(rows)
            if len(rows) < 60:
                exhausted = True
                break
        self.store.set_state(self.name, f"cat:{cat_id}", done=int(exhausted), pages=max_pages)
        return added, children, exhausted

    # ------------------------------------------------------------ 主流程

    def run(self, max_pages: int = 100, max_workers: int | None = None, force: bool = False) -> int:
        cats = self.discover()
        if not cats:
            raise RuntimeError("未发现当当类目，页面结构可能已变化")
        print(f"[dangdang] 发现 {len(cats)} 个三级类目", flush=True)

        workers = max_workers or config.CONCURRENCY
        frontier = [c for c in cats if force or not self.store.get_state(self.name, f"cat:{c}")["done"]]
        added_total = 0

        for level in range(MAX_DEPTH_LEVELS):
            if not frontier:
                break
            print(f"[dangdang] 第 {level + 1} 层：{len(frontier)} 个类目", flush=True)
            next_frontier: list[str] = []
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(self.crawl_category, c, max_pages): c for c in frontier}
                done = 0
                for fut in as_completed(futures):
                    done += 1
                    try:
                        added, children, _ = fut.result()
                    except Exception:
                        added, children = 0, []
                    added_total += added
                    next_frontier.extend(children)
                    if done % 50 == 0:
                        print(
                            f"[dangdang] L{level + 1} {done}/{len(frontier)}  "
                            f"raw={self.store.count('raw')}",
                            flush=True,
                        )
            print(
                f"[dangdang] 第 {level + 1} 层完成：+{added_total} 条，"
                f"下钻 {len(set(next_frontier))} 个子类目",
                flush=True,
            )
            frontier = [c for c in dict.fromkeys(next_frontier)
                        if force or not self.store.get_state(self.name, f"cat:{c}")["done"]]

        return added_total
