import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import random
import time
from config.config import WIKIDATA_QUERY_URL, USER_AGENTS, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX
from config.logging import get_logger

logger = get_logger(__name__)

class WikidataSpider:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/sparql-results+json',
            'Content-Type': 'application/x-www-form-urlencoded',
        })
    
    def _get_random_user_agent(self):
        return random.choice(USER_AGENTS)
    
    def _add_random_delay(self):
        delay = random.uniform(REQUEST_DELAY_MIN * 2, REQUEST_DELAY_MAX * 2)
        time.sleep(delay)
    
    def _run_sparql(self, query):
        """执行SPARQL查询并返回结果"""
        try:
            headers = {
                'User-Agent': self._get_random_user_agent()
            }
            data = {
                'query': query,
                'format': 'json'
            }
            response = self.session.post(WIKIDATA_QUERY_URL, headers=headers, data=data, timeout=60)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Wikidata SPARQL请求失败，状态码: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Wikidata SPARQL查询异常: {str(e)}")
            return None
    
    def query_chinese_language_books(self, limit=10000, offset=0):
        """查询语言为中文的书籍 (P407=Q35288 中文, P31=Q571 书)"""
        sparql = """
        SELECT ?item ?itemLabel ?authorLabel
        WHERE {
            ?item wdt:P31 wd:Q571.
            ?item wdt:P50 ?author.
            ?item wdt:P407 wd:Q35288.
            SERVICE wikibase:label {
                bd:serviceParam wikibase:language "zh,en".
            }
        }
        LIMIT %d OFFSET %d
        """ % (limit, offset)
        return self._run_sparql(sparql)
    
    def query_chinese_author_books(self, limit=10000, offset=0):
        """查询中国作者写的书 (P27=Q148 中国, P31=Q571 书)"""
        sparql = """
        SELECT ?item ?itemLabel ?authorLabel
        WHERE {
            ?item wdt:P31 wd:Q571.
            ?item wdt:P50 ?author.
            ?author wdt:P27 wd:Q148.
            SERVICE wikibase:label {
                bd:serviceParam wikibase:language "zh,en".
            }
        }
        LIMIT %d OFFSET %d
        """ % (limit, offset)
        return self._run_sparql(sparql)
    
    def _parse_sparql_results(self, results):
        """解析SPARQL查询结果，提取书名和作者"""
        books = []
        if not results:
            return books
        
        for item in results.get('results', {}).get('bindings', []):
            title = item.get('itemLabel', {}).get('value', '')
            author = item.get('authorLabel', {}).get('value', '')
            
            # 过滤掉Q数字ID（未获取到标签的情况）
            if title and title.startswith('Q') and title[1:].isdigit():
                continue
            if author and author.startswith('Q') and author[1:].isdigit():
                continue
            
            if title and author:
                books.append({
                    'title': title,
                    'author': author,
                    'source': 'wikidata'
                })
        
        return books
    
    def crawl_all(self, on_batch=None):
        """全量爬取：分页查询所有中文书籍和中国作者写的书"""
        all_books = []
        limit = 10000
        seen_keys = set()
        
        # 查询1：语言为中文的书籍
        logger.info("开始查询Wikidata：语言为中文的书籍")
        offset = 0
        while True:
            logger.info(f"Wikidata中文语言书籍查询 OFFSET={offset}")
            results = self.query_chinese_language_books(limit, offset)
            books = self._parse_sparql_results(results)
            
            if not books:
                break
            
            new_books = []
            for book in books:
                key = (book['title'], book['author'])
                if key not in seen_keys:
                    seen_keys.add(key)
                    new_books.append(book)
            
            all_books.extend(new_books)
            logger.info(f"Wikidata中文语言书籍 OFFSET={offset}，获取 {len(books)} 本，新增 {len(new_books)} 本，累计 {len(all_books)} 本")
            
            if on_batch:
                on_batch(new_books, f'wikidata-chi-lang-offset{offset}')
            
            if len(books) < limit:
                break
            
            offset += limit
            self._add_random_delay()
        
        # 查询2：中国作者写的书
        logger.info("开始查询Wikidata：中国作者写的书")
        offset = 0
        while True:
            logger.info(f"Wikidata中国作者书籍查询 OFFSET={offset}")
            results = self.query_chinese_author_books(limit, offset)
            books = self._parse_sparql_results(results)
            
            if not books:
                break
            
            new_books = []
            for book in books:
                key = (book['title'], book['author'])
                if key not in seen_keys:
                    seen_keys.add(key)
                    new_books.append(book)
            
            all_books.extend(new_books)
            logger.info(f"Wikidata中国作者书籍 OFFSET={offset}，获取 {len(books)} 本，新增 {len(new_books)} 本，累计 {len(all_books)} 本")
            
            if on_batch:
                on_batch(new_books, f'wikidata-cn-author-offset{offset}')
            
            if len(books) < limit:
                break
            
            offset += limit
            self._add_random_delay()
        
        logger.info(f"Wikidata全量爬取完成，共获取 {len(all_books)} 本书")
        return all_books

if __name__ == '__main__':
    spider = WikidataSpider()
    books = spider.crawl_all()
    print(f"获取书籍数量: {len(books)}")
    for book in books[:10]:
        print(f"书名: {book['title']}, 作者: {book['author']}")
