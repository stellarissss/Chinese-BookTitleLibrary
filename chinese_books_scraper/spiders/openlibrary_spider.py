import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import random
import time
import json
from config.config import OPENLIBRARY_SEARCH_URL, USER_AGENTS, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX
from config.logging import get_logger

logger = get_logger(__name__)

class OpenLibrarySpider:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        })
    
    def _get_random_user_agent(self):
        return random.choice(USER_AGENTS)
    
    def _add_random_delay(self):
        delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        time.sleep(delay)
    
    def search_books(self, keyword, page=1, limit=100):
        try:
            headers = {
                'User-Agent': self._get_random_user_agent()
            }
            
            params = {
                'q': keyword,
                'page': page,
                'limit': limit,
                'fields': 'title,authors'
            }
            
            response = self.session.get(OPENLIBRARY_SEARCH_URL, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                books = []
                
                for doc in data.get('docs', []):
                    title = doc.get('title', '')
                    
                    authors = []
                    author_keys = doc.get('author_key', [])
                    if author_keys:
                        for i, key in enumerate(author_keys):
                            author_name = doc.get(f'author_name_{i}', '')
                            if not author_name:
                                author_name = doc.get('author_name', [])
                                if isinstance(author_name, list) and i < len(author_name):
                                    author_name = author_name[i]
                                elif isinstance(author_name, str):
                                    author_name = author_name
                                else:
                                    continue
                            authors.append(author_name)
                    
                    author_str = ', '.join(authors) if authors else ''
                    
                    if title and author_str:
                        books.append({
                            'title': title,
                            'author': author_str,
                            'source': 'openlibrary'
                        })
                
                num_found = data.get('num_found', 0)
                logger.info(f"Open Library搜索 '{keyword}' 第{page}页，获取 {len(books)} 本书，总计 {num_found} 本")
                return books, num_found
            else:
                logger.warning(f"Open Library请求失败，状态码: {response.status_code}")
                return [], 0
        
        except Exception as e:
            logger.error(f"Open Library爬虫异常: {str(e)}")
            return [], 0
    
    def crawl_keyword(self, keyword, max_results=1000):
        all_books = []
        page = 1
        limit = 100
        total = max_results
        
        while len(all_books) < total:
            books, current_total = self.search_books(keyword, page, limit)
            
            if not books:
                break
            
            all_books.extend(books)
            
            if page == 1:
                total = min(current_total, max_results)
            
            page += 1
            
            if len(all_books) < total:
                self._add_random_delay()
        
        all_books = all_books[:max_results]
        logger.info(f"Open Library关键词 '{keyword}' 爬取完成，共获取 {len(all_books)} 本书")
        return all_books
    
    def crawl(self, keywords=None, max_results=1000):
        if keywords is None:
            keywords = ['Chinese literature', 'Chinese novel', 'Chinese history', 'Chinese philosophy']
        
        all_books = []
        
        for keyword in keywords:
            books = self.crawl_keyword(keyword, max_results // len(keywords))
            all_books.extend(books)
        
        logger.info(f"Open Library爬虫完成，总计获取 {len(all_books)} 本书")
        return all_books

if __name__ == '__main__':
    spider = OpenLibrarySpider()
    books = spider.crawl_keyword('Chinese literature', 50)
    print(f"获取书籍数量: {len(books)}")
    for book in books[:5]:
        print(f"书名: {book['title']}, 作者: {book['author']}")