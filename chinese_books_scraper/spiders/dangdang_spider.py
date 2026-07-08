import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import random
import time
import json
import re
from bs4 import BeautifulSoup
from config.config import DANGDANG_SEARCH_URL, DANGDANG_MAX_PAGES, USER_AGENTS, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX
from config.logging import get_logger

logger = get_logger(__name__)

class DangdangSpider:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0'
        })
    
    def _get_random_user_agent(self):
        return random.choice(USER_AGENTS)
    
    def _add_random_delay(self):
        delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        time.sleep(delay)
    
    def search_books(self, keyword, page=1):
        try:
            headers = {
                'User-Agent': self._get_random_user_agent(),
                'Referer': 'https://www.dangdang.com/'
            }
            
            from urllib.parse import quote
            encoded_keyword = quote(keyword, encoding='utf-8')
            
            params = {
                'key': encoded_keyword,
                'act': 'input',
                'page_index': page,
                'medium': '01',
                'category_path': '01.00.00.00.00.00',
                'q': encoded_keyword
            }
            
            response = self.session.get(DANGDANG_SEARCH_URL, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'lxml')
                books = []
                
                book_items = soup.find_all('li', class_='line1')
                
                for item in book_items:
                    title_tag = item.find('a', class_='pic')
                    if title_tag:
                        title = title_tag.get('title', '')
                        title = title.strip()
                    else:
                        continue
                    
                    author_tag = item.find('span', class_='search_book_author')
                    if author_tag:
                        author_text = author_tag.get_text(strip=True)
                        author_parts = author_text.split('/')
                        author = author_parts[0].strip() if author_parts else ''
                    else:
                        author = ''
                    
                    if title and author:
                        books.append({
                            'title': title,
                            'author': author,
                            'source': 'dangdang'
                        })
                
                logger.info(f"当当网搜索 '{keyword}' 第{page}页，获取 {len(books)} 本书")
                return books
            
            else:
                logger.warning(f"当当网请求失败，状态码: {response.status_code}")
                return []
        
        except Exception as e:
            logger.error(f"当当网爬虫异常: {str(e)}")
            return []
    
    def crawl_keyword(self, keyword, max_results=None):
        all_books = []
        max_pages = DANGDANG_MAX_PAGES
        
        for page in range(1, max_pages + 1):
            books = self.search_books(keyword, page)
            
            if not books:
                break
            
            all_books.extend(books)
            
            if max_results and len(all_books) >= max_results:
                all_books = all_books[:max_results]
                break
            
            self._add_random_delay()
        
        logger.info(f"当当网关键词 '{keyword}' 爬取完成，共获取 {len(all_books)} 本书")
        return all_books
    
    def crawl(self, keywords=None):
        if keywords is None:
            keywords = ['中国文学', '小说', '历史', '哲学', '科学', '艺术', '经济', '教育']
        
        all_books = []
        
        for keyword in keywords:
            books = self.crawl_keyword(keyword)
            all_books.extend(books)
        
        logger.info(f"当当网爬虫完成，总计获取 {len(all_books)} 本书")
        return all_books

if __name__ == '__main__':
    spider = DangdangSpider()
    books = spider.crawl_keyword('中国文学')
    print(f"获取书籍数量: {len(books)}")
    for book in books[:5]:
        print(f"书名: {book['title']}, 作者: {book['author']}")