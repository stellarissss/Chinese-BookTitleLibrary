"""跨源聚类：把 N 条原始记录收敛成 M 个书名条目。

合并原则（按可信度递减）：

1. **规范化书名完全相同** —— 直接合并。这是唯一自动执行的大规模合并。
2. **ISBN 相同** —— 合并。同一 ISBN 不可能对应两本不同的书。
3. **近似但不相同** —— 只输出候选对，不自动合并。

第 3 条是刻意的克制。中文书名里「增订」「续编」「补注」这类差异是实质性的，
自动模糊合并会把《西游记》与《西游记续》并成一条，造成「漏」。宁可留一份
待复核清单，也不悄悄改动数据。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from . import quality, textnorm as tn
from .lexicon import TitleLexicon

# 数据源可信度：元数据越规范，越适合作为规范书名的来源。
SOURCE_PRIORITY = {
    "douban": 5,
    "weread": 4,
    "guji": 3,
    "dangdang": 2,
    "legacy": 1,
    "openlibrary": 1,
    "wikidata": 1,
}


@dataclass
class Candidate:
    raw_id: int
    source: str
    title: str
    key: str
    edition: str = ""
    volume: str = ""
    author: str = ""
    publisher: str = ""
    pub_year: str = ""
    isbn: str = ""
    category: str = ""
    confidence: float = 1.0
    title_raw: str = ""


def clean_record(row: tuple, lexicon: TitleLexicon | None = None) -> tuple[Candidate | None, str]:
    """把一条 raw 行清洗为候选条目。返回 (候选, 拒绝原因)。"""
    raw_id, source, source_id, title_raw, author_raw, publisher, pub_year, isbn, category = row

    title, edition, volume, conf = tn.clean_title(title_raw or "")

    # 词典优先：电商把「书名＋卖点」直接拼在一起时（无分隔符），规则清洗无能为力，
    # 用已知干净书名做最长前缀匹配。只在原始标题里确实残留了营销/出版信息时才覆盖，
    # 否则会把《西游记续》这类本来正确的书名截成《西游记》。
    if lexicon is not None:
        hit = lexicon.match(title_raw or "")
        if hit:
            hit_key = tn.title_key(hit)
            cur_key = tn.title_key(title)
            excess = cur_key[len(hit_key):] if cur_key.startswith(hit_key) else ""
            if hit_key != cur_key and len(excess) >= 2 and tn.has_tail_noise(title_raw or ""):
                title, conf = hit, 1.0

    ok, reason = quality.is_book(title)
    if not ok:
        return None, reason

    key = tn.title_key(title)
    if not tn.is_strong_key(key):
        return None, "single_char"

    return Candidate(
        raw_id=raw_id,
        source=source,
        title=title,
        key=key,
        edition=edition,
        volume=volume,
        author=tn.clean_author(author_raw or ""),
        publisher=tn.squash(publisher or ""),
        pub_year=tn.pub_year(pub_year or ""),
        isbn=tn.isbn13(isbn or ""),
        category=tn.squash(category or ""),
        confidence=conf,
        title_raw=tn.squash(title_raw or ""),
    ), ""


class _DSU:
    def __init__(self) -> None:
        self.parent: dict[int, int] = {}

    def find(self, x: int) -> int:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _canonical(members: list[Candidate]) -> Candidate:
    return max(
        members,
        key=lambda c: (
            SOURCE_PRIORITY.get(c.source, 0),
            c.confidence,
            1 if c.author else 0,
            1 if c.isbn else 0,
            -len(c.title),
        ),
    )


@dataclass
class Result:
    books: list[dict] = field(default_factory=list)
    members: list[tuple[int, int]] = field(default_factory=list)
    rejected: dict[str, int] = field(default_factory=dict)
    n_candidates: int = 0


def cluster(rows: Iterable[tuple], lexicon: TitleLexicon | None = None) -> Result:
    res = Result()
    rejected: dict[str, int] = defaultdict(int)
    by_key: dict[str, list[Candidate]] = defaultdict(list)
    by_isbn: dict[str, list[Candidate]] = defaultdict(list)
    index: list[Candidate] = []

    for row in rows:
        cand, reason = clean_record(row, lexicon)
        if cand is None:
            rejected[reason] += 1
            continue
        by_key[cand.key].append(cand)
        if cand.isbn:
            by_isbn[cand.isbn].append(cand)
        index.append(cand)

    res.n_candidates = len(index)
    res.rejected = dict(rejected)
    if not index:
        return res

    # ---- 并查集：先按书名键，再按 ISBN 串联 ISBN 相同但写法不同的条目
    pos = {id(c): i for i, c in enumerate(index)}
    dsu = _DSU()
    for group in by_key.values():
        first = pos[id(group[0])]
        for c in group[1:]:
            dsu.union(first, pos[id(c)])
    for group in by_isbn.values():
        if len(group) > 1:
            first = pos[id(group[0])]
            for c in group[1:]:
                dsu.union(first, pos[id(c)])

    clusters: dict[int, list[Candidate]] = defaultdict(list)
    for c in index:
        clusters[dsu.find(pos[id(c)])].append(c)

    # ---- 生成规范条目
    book_id = 0
    for members in clusters.values():
        best = _canonical(members)
        sources = sorted({m.source for m in members}, key=lambda s: -SOURCE_PRIORITY.get(s, 0))
        authors = [m.author for m in members if m.author]
        aliases = sorted({m.title_raw for m in members} - {best.title_raw})[:8]

        book_id += 1
        res.books.append(
            {
                "title": best.title,
                "title_key": best.key,
                "edition": best.edition,
                "volume": best.volume,
                "author": authors[0] if authors else "",
                "publisher": best.publisher,
                "pub_year": best.pub_year,
                "isbn": best.isbn,
                "category": best.category,
                "sources": ",".join(sources),
                "n_sources": len(sources),
                "aliases": " | ".join(aliases),
                "confidence": quality.score(
                    best.confidence, len(sources), bool(authors), bool(best.isbn)
                ),
            }
        )
        for m in members:
            res.members.append((book_id, m.raw_id))

    return res


def near_duplicates(books: list[dict], threshold: float = 0.9, max_block: int = 4000) -> list[tuple[str, str, float]]:
    """输出疑似重复的书名对，供人工复核。

    分块策略：首字 + 长度（允许 ±1）。块内两两比较 2-gram Jaccard。
    超大块直接跳过，避免 O(n²) 拖垮整个流程。
    """
    def grams(s: str) -> set[str]:
        return {s[i : i + 2] for i in range(len(s) - 1)} or {s}

    blocks: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for b in books:
        k = b["title_key"]
        blocks[(k[0], len(k))].append(b)

    seen: set[tuple[str, str]] = set()
    pairs: list[tuple[str, str, float]] = []
    for (ch, ln), items in blocks.items():
        pool = list(items)
        for dl in (1,):
            pool += blocks.get((ch, ln + dl), [])
        if len(pool) < 2 or len(pool) > max_block:
            continue
        for i in range(len(pool)):
            gi = grams(pool[i]["title_key"])
            for j in range(i + 1, len(pool)):
                gj = grams(pool[j]["title_key"])
                inter = len(gi & gj)
                if not inter:
                    continue
                sim = inter / (len(gi) + len(gj) - inter)
                if sim >= threshold:
                    a, b = pool[i]["title"], pool[j]["title"]
                    pair = (a, b) if a <= b else (b, a)
                    if pair in seen:
                        continue
                    seen.add(pair)
                    pairs.append((pair[0], pair[1], round(sim, 3)))
    pairs.sort(key=lambda x: -x[2])
    return pairs
