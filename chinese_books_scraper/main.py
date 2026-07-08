#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
from spiders.douban_spider import DoubanSpider
from spiders.dangdang_spider import DangdangSpider
from spiders.wikidata_spider import WikidataSpider
from spiders.openlibrary_spider import OpenLibrarySpider
from utils.data_cleaner import DataCleaner
from utils.data_storage import DataStorage
from config.logging import get_logger

logger = get_logger(__name__)

def main():
    parser = argparse.ArgumentParser(description='中文书籍数据采集工具')
    parser.add_argument('--keywords', nargs='+', default=['中国文学', '中国历史', '中国哲学', '中国小说'],
                        help='搜索关键词列表')
    parser.add_argument('--max-results', type=int, default=1000,
                        help='每个关键词最大获取书籍数量')
    parser.add_argument('--output-dir', default='output',
                        help='输出目录')
    parser.add_argument('--spiders', nargs='+', default=['douban', 'dangdang', 'wikidata', 'openlibrary'],
                        help='启用的爬虫列表')
    parser.add_argument('--skip-clean', action='store_true',
                        help='跳过数据清洗')
    parser.add_argument('--skip-dedup', action='store_true',
                        help='跳过去重')
    parser.add_argument('--format', nargs='+', default=['csv', 'json', 'sqlite'],
                        help='输出格式')
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("中文书籍数据采集工具启动")
    logger.info(f"搜索关键词: {args.keywords}")
    logger.info(f"最大结果数: {args.max_results}")
    logger.info(f"启用爬虫: {args.spiders}")
    logger.info(f"输出格式: {args.format}")
    logger.info("=" * 60)
    
    all_books = []
    
    if 'douban' in args.spiders:
        logger.info("启动豆瓣读书爬虫...")
        try:
            douban_spider = DoubanSpider()
            for keyword in args.keywords:
                books = douban_spider.crawl_keyword(keyword, args.max_results // len(args.keywords))
                all_books.extend(books)
        except Exception as e:
            logger.error(f"豆瓣读书爬虫失败: {str(e)}")
    
    if 'dangdang' in args.spiders:
        logger.info("启动当当网爬虫...")
        try:
            dangdang_spider = DangdangSpider()
            for keyword in args.keywords:
                books = dangdang_spider.crawl_keyword(keyword, args.max_results // len(args.keywords))
                all_books.extend(books)
        except Exception as e:
            logger.error(f"当当网爬虫失败: {str(e)}")
    
    if 'wikidata' in args.spiders:
        logger.info("启动Wikidata爬虫...")
        try:
            wikidata_spider = WikidataSpider()
            books = wikidata_spider.crawl(args.max_results)
            all_books.extend(books)
        except Exception as e:
            logger.error(f"Wikidata爬虫失败: {str(e)}")
    
    if 'openlibrary' in args.spiders:
        logger.info("启动Open Library爬虫...")
        try:
            openlibrary_spider = OpenLibrarySpider()
            books = openlibrary_spider.crawl(max_results=args.max_results)
            all_books.extend(books)
        except Exception as e:
            logger.error(f"Open Library爬虫失败: {str(e)}")
    
    logger.info(f"数据采集完成，共获取 {len(all_books)} 条原始数据")
    
    if not args.skip_clean:
        logger.info("开始数据清洗...")
        all_books = [DataCleaner.clean_book(book) for book in all_books]
        all_books = [b for b in all_books if b['title'] and b['author']]
        logger.info(f"数据清洗完成，剩余 {len(all_books)} 条有效数据")
    
    if not args.skip_dedup:
        logger.info("开始数据去重...")
        all_books = DataCleaner.remove_duplicates(all_books)
        logger.info(f"数据去重完成，剩余 {len(all_books)} 条唯一数据")
    
    storage = DataStorage(args.output_dir)
    
    if 'csv' in args.format:
        storage.save_to_csv(all_books)
    
    if 'json' in args.format:
        storage.save_to_json(all_books)
    
    if 'sqlite' in args.format:
        storage.save_to_sqlite(all_books)
    
    logger.info("=" * 60)
    logger.info("中文书籍数据采集工具执行完成")
    logger.info(f"最终数据量: {len(all_books)} 条")
    logger.info("=" * 60)
    
    print(f"\n数据采集完成！")
    print(f"原始数据: {len(all_books)} 条")
    print(f"输出目录: {args.output_dir}")
    print(f"输出格式: {args.format}")

if __name__ == '__main__':
    main()