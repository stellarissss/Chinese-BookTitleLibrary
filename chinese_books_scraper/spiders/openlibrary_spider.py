import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import random
import time
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
    
    def _search_by_language(self, language_code, page=1, limit=100):
        """按语言代码搜索所有书籍"""
        try:
            headers = {
                'User-Agent': self._get_random_user_agent()
            }
            
            params = {
                'q': f'language:{language_code}',
                'page': page,
                'limit': limit,
                'fields': 'title,author_name'
            }
            
            response = self.session.get(OPENLIBRARY_SEARCH_URL, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                books = []
                
                for doc in data.get('docs', []):
                    title = doc.get('title', '')
                    
                    authors = doc.get('author_name', [])
                    if isinstance(authors, list):
                        author_str = ', '.join(authors)
                    elif isinstance(authors, str):
                        author_str = authors
                    else:
                        author_str = ''
                    
                    if title and author_str:
                        books.append({
                            'title': title,
                            'author': author_str,
                            'source': 'openlibrary'
                        })
                
                num_found = data.get('num_found', 0)
                logger.info(f"Open Library language:{language_code} 第{page}页，获取 {len(books)} 本书，总计 {num_found} 本")
                return books, num_found
            else:
                logger.warning(f"Open Library请求失败，状态码: {response.status_code}")
                return [], 0
        
        except Exception as e:
            logger.error(f"Open Library爬虫异常: {str(e)}")
            return [], 0
    
    def crawl_by_language(self, language_code, on_batch=None):
        """按语言代码遍历所有分页，获取该语言的所有书籍"""
        all_books = []
        page = 1
        limit = 100
        total = float('inf')
        
        while len(all_books) < total:
            books, current_total = self._search_by_language(language_code, page, limit)
            
            if not books:
                break
            
            all_books.extend(books)
            
            if page == 1:
                total = current_total
                logger.info(f"Open Library language:{language_code} 共有 {total} 本书")
            
            if on_batch:
                on_batch(books, f'openlibrary-{language_code}-page{page}')
            
            page += 1
            
            if len(all_books) >= total:
                break
            
            self._add_random_delay()
        
        logger.info(f"Open Library language:{language_code} 爬取完成，共获取 {len(all_books)} 本书")
        return all_books
    
    def crawl_all(self, on_batch=None):
        """全量爬取：用 chi 和 zho 两种语言代码搜索所有中文书籍"""
        all_books = []
        seen_keys = set()
        
        # 语言代码 chi = 中文（ISO 639-2 bibliographic），zho = 中文（ISO 639-2 terminological）
        for lang_code in ['chi', 'zho']:
            logger.info(f"开始爬取Open Library language:{lang_code}")
            books = self.crawl_by_language(lang_code, on_batch=on_batch)
            
            new_books = []
            for book in books:
                key = (book['title'].lower().strip(), book['author'].lower().strip())
                if key not in seen_keys:
                    seen_keys.add(key)
                    new_books.append(book)
            
            all_books.extend(new_books)
            logger.info(f"Open Library language:{lang_code} 去重后新增 {len(new_books)} 本，累计 {len(all_books)} 本")
        
        logger.info(f"Open Library全量爬取完成，共获取 {len(all_books)} 本书")
        return all_books

if __name__ == '__main__':
    spider = OpenLibrarySpider()
    books = spider.crawl_all()
    print(f"获取书籍数量: {len(books)}")
    for book in books[:10]:
        print(f"书名: {book['title']}, 作者: {book['author']}")
