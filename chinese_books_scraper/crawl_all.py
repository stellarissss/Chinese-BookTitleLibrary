#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3
import argparse
from spiders.douban_spider import DoubanSpider
from spiders.dangdang_spider import DangdangSpider
from spiders.wikidata_spider import WikidataSpider
from spiders.openlibrary_spider import OpenLibrarySpider
from utils.data_cleaner import DataCleaner
from utils.data_storage import DataStorage
from config.logging import get_logger

logger = get_logger(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
DB_PATH = os.path.join(OUTPUT_DIR, 'chinese_books.db')

def ensure_database():
    """确保数据库和表结构存在"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            source TEXT,
            UNIQUE(title, author)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_title ON books(title)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_author ON books(author)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_source ON books(source)')
    conn.commit()
    conn.close()

def batch_insert_to_db(books, source_label=''):
    """增量写入一批数据到数据库"""
    if not books:
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    inserted = 0
    
    for book in books:
        title = DataCleaner.clean_title(book.get('title', ''))
        author = DataCleaner.clean_author(book.get('author', ''))
        source = book.get('source', '')
        
        if title and author:
            try:
                cursor.execute(
                    'INSERT OR IGNORE INTO books (title, author, source) VALUES (?, ?, ?)',
                    (title, author, source)
                )
                if cursor.lastrowid > 0:
                    inserted += 1
            except Exception:
                pass
    
    conn.commit()
    conn.close()
    
    if inserted > 0:
        logger.info(f"[{source_label}] 写入数据库 {inserted} 条新记录")
    
    return inserted

def get_db_count():
    """获取数据库中当前记录数"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM books')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def crawl_all(spiders=None):
    """全量爬取所有中文书籍"""
    ensure_database()
    
    if spiders is None:
        spiders = ['douban', 'dangdang', 'wikidata', 'openlibrary']
    
    logger.info("=" * 80)
    logger.info("开始全量采集所有中文书籍数据")
    logger.info(f"启用爬虫: {spiders}")
    logger.info(f"数据库: {DB_PATH}")
    logger.info("=" * 80)
    
    def on_batch(books, label):
        batch_insert_to_db(books, label)
        count = get_db_count()
        logger.info(f"数据库当前总记录数: {count}")
    
    if 'douban' in spiders:
        logger.info("\n" + "=" * 60)
        logger.info("启动豆瓣读书全量爬虫（标签浏览模式）")
        logger.info("=" * 60)
        try:
            douban_spider = DoubanSpider()
            douban_spider.crawl_all(on_batch=on_batch)
        except Exception as e:
            logger.error(f"豆瓣读书爬虫失败: {str(e)}")
    
    if 'dangdang' in spiders:
        logger.info("\n" + "=" * 60)
        logger.info("启动当当网全量爬虫（分类浏览模式）")
        logger.info("=" * 60)
        try:
            dangdang_spider = DangdangSpider()
            dangdang_spider.crawl_all(on_batch=on_batch)
        except Exception as e:
            logger.error(f"当当网爬虫失败: {str(e)}")
    
    if 'wikidata' in spiders:
        logger.info("\n" + "=" * 60)
        logger.info("启动Wikidata全量爬虫（SPARQL查询模式）")
        logger.info("=" * 60)
        try:
            wikidata_spider = WikidataSpider()
            wikidata_spider.crawl_all(on_batch=on_batch)
        except Exception as e:
            logger.error(f"Wikidata爬虫失败: {str(e)}")
    
    if 'openlibrary' in spiders:
        logger.info("\n" + "=" * 60)
        logger.info("启动Open Library全量爬虫（语言筛选模式）")
        logger.info("=" * 60)
        try:
            openlibrary_spider = OpenLibrarySpider()
            openlibrary_spider.crawl_all(on_batch=on_batch)
        except Exception as e:
            logger.error(f"Open Library爬虫失败: {str(e)}")
    
    final_count = get_db_count()
    
    logger.info("\n" + "=" * 80)
    logger.info(f"全量采集完成！数据库共 {final_count} 条记录")
    logger.info(f"数据库文件: {DB_PATH}")
    logger.info("=" * 80)
    
    print(f"\n采集完成！数据库共 {final_count} 条中文书籍记录")
    print(f"数据库文件: {DB_PATH}")
    print(f"可用 gui_search.py 打开检索界面查询")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='全量采集所有中文书籍数据')
    parser.add_argument('--spiders', nargs='+', default=['douban', 'dangdang', 'wikidata', 'openlibrary'],
                        choices=['douban', 'dangdang', 'wikidata', 'openlibrary'],
                        help='启用的爬虫列表')
    args = parser.parse_args()
    
    crawl_all(spiders=args.spiders)
