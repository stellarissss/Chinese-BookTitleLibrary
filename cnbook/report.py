"""从数据库生成实测报告。

报告里的每个数字都直接查库得出，不手写、不估算 —— 数字一旦能自动生成，
就不会出现「README 写着 80 万、实际只有 12 万」这种事。
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from . import config
from .store import Store


def _pct(a: int, b: int) -> str:
    return f"{a / b * 100:.1f}%" if b else "0%"


def _top_initial(store: Store, limit: int = 12) -> list[tuple[str, int]]:
    rows = store._conn.execute("SELECT title_key, 1 FROM books").fetchall()
    counter: Counter[str] = Counter()
    for key, _ in rows:
        if key:
            counter[key[0]] += 1
    return counter.most_common(limit)


def build_report(store: Store) -> str:
    conn = store._conn
    raw_total = store.count("raw")
    books = store.count("books")
    by_source = store.source_breakdown()

    high = conn.execute("SELECT COUNT(*) FROM books WHERE confidence >= 0.9").fetchone()[0]
    mid = conn.execute(
        "SELECT COUNT(*) FROM books WHERE confidence >= 0.6 AND confidence < 0.9"
    ).fetchone()[0]
    low = books - high - mid

    with_author = conn.execute("SELECT COUNT(*) FROM books WHERE author<>''").fetchone()[0]
    with_press = conn.execute("SELECT COUNT(*) FROM books WHERE publisher<>''").fetchone()[0]
    with_year = conn.execute("SELECT COUNT(*) FROM books WHERE pub_year<>''").fetchone()[0]
    multi = conn.execute("SELECT COUNT(*) FROM books WHERE n_sources > 1").fetchone()[0]

    year_dist = conn.execute(
        "SELECT substr(pub_year,1,3)||'0s' AS d, COUNT(*) FROM books "
        "WHERE pub_year BETWEEN 1949 AND 2029 GROUP BY d ORDER BY d"
    ).fetchall()

    lines: list[str] = []
    a = lines.append
    a("# 实测报告")
    a("")
    a("> 本文件由 `python -m cnbook report` 自动生成，数字取自当前数据库，请勿手工编辑。")
    a("")
    a("## 一、数量")
    a("")
    a("| 指标 | 数值 |")
    a("|---|---|")
    a(f"| 原始记录 | {raw_total:,} |")
    a(f"| 规范条目（去重后书名） | **{books:,}** |")
    a(f"| 多源互证条目 | {multi:,}（{_pct(multi, books)}） |")
    a("")
    a("## 二、来源")
    a("")
    a("| 来源 | 原始记录 | 去重书名 | 说明 |")
    a("|---|---|---|---|")
    notes = {
        "dangdang": "分类遍历，含著者/出版社/出版年",
        "douban": "标签遍历，书名最干净",
        "weread": "分类树枚举，元数据干净",
        "pdc": "国家版本馆（需账号）",
    }
    for source, n, distinct in by_source:
        a(f"| {source} | {n:,} | {distinct:,} | {notes.get(source, '')} |")
    a("")
    a("## 三、字段完整度")
    a("")
    a("| 字段 | 覆盖 | 占比 |")
    a("|---|---|---|")
    a(f"| 著者 | {with_author:,} | {_pct(with_author, books)} |")
    a(f"| 出版社 | {with_press:,} | {_pct(with_press, books)} |")
    a(f"| 出版年 | {with_year:,} | {_pct(with_year, books)} |")
    a("")
    a("## 四、书名可信度")
    a("")
    a("清洗置信度反映「这条书名里有没有残留营销文本」。判定规则见 `cnbook/textnorm.py`。")
    a("")
    a("| 档位 | 条目 | 占比 | 含义 |")
    a("|---|---|---|---|")
    a(f"| 高（≥0.9） | {high:,} | {_pct(high, books)} | 未检出营销噪声，可直接使用 |")
    a(f"| 中（0.6–0.9） | {mid:,} | {_pct(mid, books)} | 做过截断，建议抽查 |")
    a(f"| 低（<0.6） | {low:,} | {_pct(low, books)} | 仍有可疑片段，需人工复核 |")
    a("")
    a("导出时可用 `--min-conf 0.9` 只取高置信部分。")
    a("")
    if year_dist:
        a("## 五、出版年分布")
        a("")
        a("| 年代 | 条目 |")
        a("|---|---|")
        for d, n in year_dist:
            a(f"| {d} | {n:,} |")
        a("")
    a("## 六、书名首字分布（前 12）")
    a("")
    a("| 首字 | 条目 |")
    a("|---|---|")
    for ch, n in _top_initial(store):
        a(f"| {ch} | {n:,} |")
    a("")
    return "\n".join(lines)


def write_report(store: Store, path: Path | None = None) -> Path:
    path = path or (Path(__file__).resolve().parent.parent / "REPORT.md")
    path.write_text(build_report(store), encoding="utf-8")
    return path


def export_csv(store: Store, path: Path, min_conf: float = 0.0) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    sql = (
        "SELECT title, edition, volume, author, publisher, pub_year, isbn,"
        " category, sources, n_sources, confidence FROM books"
    )
    if min_conf:
        sql += f" WHERE confidence>={min_conf}"
    sql += " ORDER BY n_sources DESC, confidence DESC, title"
    cur = store._conn.execute(sql)
    n = 0
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["书名", "版本", "卷册", "著者", "出版社", "出版年", "ISBN", "分类", "来源", "来源数", "置信度"])
        for row in cur:
            w.writerow(row)
            n += 1
    return n
