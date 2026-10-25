"""命令行入口。

    python -m cnbook crawl dangdang --max-pages 100
    python -m cnbook crawl douban
    python -m cnbook build
    python -m cnbook stats
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from . import config, dedup, report
from .lexicon import TitleLexicon
from .sources import REGISTRY
from .store import Store


def cmd_crawl(args: argparse.Namespace) -> None:
    store = Store()
    cls = REGISTRY.get(args.source)
    if cls is None:
        sys.exit(f"未知数据源: {args.source}（可选: {', '.join(REGISTRY)}）")
    src = cls(store)
    kwargs = {}
    if args.source == "dangdang":
        kwargs = {"max_pages": args.max_pages, "max_workers": args.workers}
    elif args.source == "douban":
        kwargs = {"max_start": args.max_start, "workers": args.workers, "limit": args.limit}
    added = src.run(**kwargs)
    print(f"[{args.source}] 本轮新增 {added} 条，库内 raw 共 {store.count('raw')} 条")
    store.close()


def build_lexicon(store: Store) -> TitleLexicon:
    """用元数据规范的数据源构建书名切分词典。"""
    lex = TitleLexicon()
    rows = store.iter_raw(source="douban")
    for batch in rows:
        for r in batch:
            lex.add(r[3])
    return lex


def cmd_build(args: argparse.Namespace) -> None:
    from . import quality

    store = Store()
    lex = build_lexicon(store)
    print(f"[build] 词典规模 {len(lex)}（来源：douban）", flush=True)

    rows = (r for batch in store.iter_raw() for r in batch)
    res = dedup.cluster(rows, lex)

    print(f"[build] 候选 {res.n_candidates}，规范条目 {len(res.books)}", flush=True)
    if res.rejected:
        top = sorted(res.rejected.items(), key=lambda x: -x[1])[:6]
        print(f"[build] 拒收 {sum(res.rejected.values())}：{top}", flush=True)

    store.replace_books(res.books, res.members)

    if args.review:
        pairs = dedup.near_duplicates(res.books)
        out = config.DATA_DIR / "review_near_duplicates.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["title_a", "title_b", "similarity"])
            w.writerows(pairs)
        print(f"[build] 近似重复候选 {len(pairs)} 对 -> {out}", flush=True)

    print_stats(store)
    store.close()


def print_stats(store: Store) -> None:
    total = store.count("books")
    raw = store.count("raw")
    print(f"\n原始记录 {raw:,}  ->  规范条目 {total:,}")
    print(f"{'来源':<12}{'记录数':>10}{'去重书名':>10}")
    for source, n, distinct in store.source_breakdown():
        print(f"{source:<12}{n:>10,}{distinct:>10,}")

    conn = store._conn
    rows = conn.execute(
        "SELECT confidence >= 0.9, COUNT(*) FROM books GROUP BY 1 ORDER BY 1 DESC"
    ).fetchall()
    for flag, n in rows:
        print(f"{'高置信' if flag else '待复核':<8}{n:>10,}")
    n_author = conn.execute("SELECT COUNT(*) FROM books WHERE author<>''").fetchone()[0]
    n_isbn = conn.execute("SELECT COUNT(*) FROM books WHERE isbn<>''").fetchone()[0]
    print(f"有著者 {n_author:,}    有 ISBN {n_isbn:,}")


def cmd_stats(args: argparse.Namespace) -> None:
    store = Store()
    print_stats(store)
    store.close()


def cmd_export(args: argparse.Namespace) -> None:
    store = Store()
    out = Path(args.out or config.DATA_DIR / "books.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    conn = store._conn
    cur = conn.execute(
        "SELECT title, edition, volume, author, publisher, pub_year, isbn,"
        " category, sources, n_sources, confidence FROM books"
        f"{' WHERE confidence>=%s' % args.min_conf if args.min_conf else ''}"
        " ORDER BY n_sources DESC, confidence DESC, title"
    )
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            ["书名", "版本", "卷册", "著者", "出版社", "出版年", "ISBN", "分类", "来源", "来源数", "置信度"]
        )
        n = 0
        for row in cur:
            w.writerow(row)
            n += 1
    print(f"导出 {n:,} 条 -> {out}")
    store.close()


def cmd_report(args: argparse.Namespace) -> None:
    store = Store()
    path = report.write_report(store)
    print(f"报告已写入 {path}")
    store.close()


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="cnbook", description="中华书名库采集与整理")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("crawl", help="运行采集器")
    c.add_argument("source", choices=list(REGISTRY))
    c.add_argument("--max-pages", type=int, default=100)
    c.add_argument("--max-start", type=int, default=980)
    c.add_argument("--workers", type=int, default=config.CONCURRENCY)
    c.add_argument("--limit", type=int, default=0, help="豆瓣：只爬收录量最大的前 N 个标签")
    c.set_defaults(func=cmd_crawl)

    b = sub.add_parser("build", help="归一化 + 去重 + 写规范表")
    b.add_argument("--review", action="store_true", help="同时输出近似重复候选")
    b.set_defaults(func=cmd_build)

    s = sub.add_parser("stats", help="统计")
    s.set_defaults(func=cmd_stats)

    e = sub.add_parser("export", help="导出 CSV")
    e.add_argument("--out", default="")
    e.add_argument("--min-conf", type=float, default=0.0)
    e.set_defaults(func=cmd_export)

    r = sub.add_parser("report", help="生成实测报告 REPORT.md")
    r.set_defaults(func=cmd_report)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
