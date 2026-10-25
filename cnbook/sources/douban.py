"""豆瓣图书标签遍历。

豆瓣的元数据是中文书里最规范的一批：书名、著者、出版社、出版年分列，
几乎没有电商式营销拼接。代价是数据量被标签页深度锁死 —— 每个标签最多翻
到 1000 条。因此它的定位是「提供干净的规范书名」，而非覆盖量。
"""

from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup

from ..net import Session
from .base import Source

TAG_INDEX = "https://book.douban.com/tag/"
TAG_PAGE = "https://book.douban.com/tag/{tag}?start={start}&type=T"
PER_PAGE = 20
MAX_START = 980

_RE_TAG = re.compile(r'href="/tag/([^"?/]+)"')


class Douban(Source):
    name = "douban"

    def __init__(self, store) -> None:
        super().__init__(store)
        self.http = Session(referer="https://book.douban.com/", encoding="utf-8")

    def tags(self) -> list[str]:
        """按收录量从大到小返回标签名。"""
        resp = self.http.get(TAG_INDEX)
        if resp is None:
            return []
        # 标签页里每个标签后面跟着 (收录数)，用它排序可以让有限的采集预算先覆盖大类
        pairs = re.findall(r'/tag/([^"?/]+)"[^>]*>[^<]*</a>\s*\((\d+)\)', resp.text)
        if pairs:
            ranked = sorted({t: int(n) for t, n in pairs}.items(), key=lambda x: -x[1])
            return [t for t, _ in ranked]
        return list(dict.fromkeys(_RE_TAG.findall(resp.text)))

    def page(self, tag: str, start: int) -> list[dict] | None:
        """返回该页书目；请求失败返回 None，与「真的没有更多」区分开。"""
        url = TAG_PAGE.format(tag=tag, start=start)
        resp = self.http.get(url)
        if resp is None:
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        items = soup.select("li.subject-item")
        if not items:
            return []
        out = []
        for li in items:
            a = li.select_one("h2 a")
            if not a:
                continue
            href = a.get("href", "")
            sid = href.rstrip("/").rsplit("/", 1)[-1] if href else ""
            pub = li.select_one("div.pub")
            author, press, year = self._split_pub(pub.get_text(" ", strip=True) if pub else "")
            out.append(
                {
                    "source": self.name,
                    "source_id": sid or f"{tag}-{start}-{a.get('title','')}",
                    "title_raw": a.get("title") or a.get_text(strip=True),
                    "author_raw": author,
                    "publisher": press,
                    "pub_year": year,
                    "category": tag,
                    "url": href,
                }
            )
        return out

    @staticmethod
    def _split_pub(text: str) -> tuple[str, str, str]:
        """``著者 / 译者 / 出版社 / 出版年 / 定价`` 形式的出版信息拆解。

        豆瓣的把译者与出版社并列，位置不固定，因此出版社用后缀识别而非取固定位。
        """
        parts = [p.strip() for p in text.split("/") if p.strip()]
        author = parts[0] if parts else ""
        press = ""
        for p in parts[1:]:
            if re.search(r"(出版社|出版公司|出版集团|书局|书店|印书馆|公司|集团|大学)$", p):
                press = p
                break
        if not press and len(parts) > 1:
            press = parts[1]
        year = ""
        for p in reversed(parts[1:]):
            m = re.search(r"((?:19|20)\d{2})", p)
            if m:
                year = m.group(1)
                break
        return author, press, year

    def run(
        self,
        max_start: int = MAX_START,
        workers: int = 1,
        cooldown: float = 45.0,
        force: bool = False,
        limit: int = 0,
    ) -> int:
        tags: list[str] = []
        for attempt in range(5):
            tags = self.tags()
            if tags:
                break
            print(f"[douban] 标签页不可用，第 {attempt + 1} 次重试", flush=True)
            time.sleep(cooldown)
        if not tags:
            raise RuntimeError("豆瓣标签页解析失败（连续 5 次）")
        if limit:
            tags = tags[:limit]
        print(f"[douban] 发现 {len(tags)} 个标签", flush=True)

        added = 0
        skipped = 0
        for i, tag in enumerate(tags, 1):
            if not force and self.store.get_state(self.name, tag)["done"]:
                skipped += 1
                continue
            tag_added = 0
            start = 0
            pages_done = 0
            fails = 0
            while start <= max_start:
                rows = self.page(tag, start)
                if rows is None:
                    # 被限流：冷却后重试同一页；连续失败 4 次才放弃该标签
                    fails += 1
                    if fails > 4:
                        print(f"[douban] {tag} 连续失败，跳过", flush=True)
                        break
                    print(f"[douban] 限流，冷却 {cooldown:.0f}s（{tag}@{start}）", flush=True)
                    time.sleep(cooldown)
                    continue
                fails = 0
                if not rows:
                    break
                tag_added += self.emit(rows)
                pages_done += 1
                if len(rows) < PER_PAGE:
                    break
                start += PER_PAGE
            added += tag_added
            # 只有真的取到内容才算完成；被限流而空手而归的标签留待下次
            if pages_done:
                self.store.set_state(self.name, tag, done=1, items=tag_added)
            print(
                f"[douban] {i}/{len(tags)} {tag} +{tag_added} total={self.store.count('raw')}",
                flush=True,
            )
        if skipped:
            print(f"[douban] 跳过已完成标签 {skipped} 个", flush=True)
        return added
