import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import random
import time
import json
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
        delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        time.sleep(delay)
    
    def query_chinese_books(self, limit=100, offset=0):
        try:
            headers = {
                'User-Agent': self._get_random_user_agent()
            }
            
            sparql_query = """
            SELECT ?item ?itemLabel ?authorLabel
            WHERE {
                ?item wdt:P31 wd:Q571.
                ?item wdt:P50 ?author.
                ?item wdt:P407 wd:Q35288.
                SERVICE wikibase:label { 
                    bd:serviceParam wikibase:language "zh". 
                }
            }
            LIMIT %d OFFSET %d
            """ % (limit, offset)
            
            data = {
                'query': sparql_query,
                'format': 'json'
            }
            
            response = self.session.post(WIKIDATA_QUERY_URL, headers=headers, data=data, timeout=30)
            
            if response.status_code == 200:
                results = response.json()
                books = []
                
                for item in results.get('results', {}).get('bindings', []):
                    title = item.get('itemLabel', {}).get('value', '')
                    author = item.get('authorLabel', {}).get('value', '')
                    
                    if title and author:
                        books.append({
                            'title': title,
                            'author': author,
                            'source': 'wikidata'
                        })
                
                logger.info(f"Wikidata查询第{offset//limit + 1}页，获取 {len(books)} 本书")
                return books
            else:
                logger.warning(f"Wikidata请求失败，状态码: {response.status_code}")
                return []
        
        except Exception as e:
            logger.error(f"Wikidata爬虫异常: {str(e)}")
            return []
    
    def crawl(self, max_results=1000):
        all_books = []
        offset = 0
        limit = 100
        
        while offset < max_results:
            books = self.query_chinese_books(limit, offset)
            
            if not books:
                break
            
            all_books.extend(books)
            offset += limit
            
            if offset < max_results:
                self._add_random_delay()
        
        logger.info(f"Wikidata爬虫完成，总计获取 {len(all_books)} 本书")
        return all_books

if __name__ == '__main__':
    spider = WikidataSpider()
    books = spider.crawl(50)
    print(f"获取书籍数量: {len(books)}")
    for book in books[:5]:
        print(f"书名: {book['title']}, 作者: {book['author']}")