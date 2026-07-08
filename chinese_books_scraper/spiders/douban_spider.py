import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import random
import time
import json
from bs4 import BeautifulSoup
from config.config import DOUBAN_MAX_RESULTS, USER_AGENTS, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX
from config.logging import get_logger

logger = get_logger(__name__)

DOUBAN_SEARCH_URL = 'https://book.douban.com/subject_search'
DOUBAN_PAGE_SIZE = 15

class DoubanSpider:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
        })
    
    def _get_random_user_agent(self):
        return random.choice(USER_AGENTS)
    
    def _add_random_delay(self):
        delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        time.sleep(delay)
    
    def search_books(self, keyword, start=0, count=15):
        try:
            headers = {
                'User-Agent': self._get_random_user_agent(),
                'Referer': 'https://book.douban.com/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Cache-Control': 'max-age=0',
                'Host': 'book.douban.com'
            }
            
            params = {
                'search_text': keyword,
                'cat': '1001',
                'start': start
            }
            
            response = self.session.get(DOUBAN_SEARCH_URL, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'lxml')
                books = []
                
                book_items = soup.find_all('div', class_='subject-item')
                
                for item in book_items:
                    info = item.find('div', class_='info')
                    if not info:
                        continue
                    
                    title_tag = info.find('h2').find('a') if info.find('h2') else None
                    if title_tag:
                        title = title_tag.get('title', '').strip()
                    else:
                        continue
                    
                    author_info = info.find('div', class_='pub')
                    if author_info:
                        author_text = author_info.get_text(strip=True)
                        if author_text:
                            author_parts = author_text.split('/')
                            author = author_parts[0].strip() if author_parts else ''
                        else:
                            author = ''
                    else:
                        author = ''
                    
                    if title and author:
                        books.append({
                            'title': title,
                            'author': author,
                            'source': 'douban'
                        })
                
                total_text = soup.find('span', class_='result-count')
                total = 0
                if total_text:
                    import re
                    match = re.search(r'(\d+)', total_text.get_text())
                    if match:
                        total = int(match.group(1))
                
                logger.info(f"豆瓣读书搜索 '{keyword}' 第{start//count + 1}页，获取 {len(books)} 本书，总计 {total} 本")
                return books, total
            else:
                logger.warning(f"豆瓣读书请求失败，状态码: {response.status_code}")
                return [], 0
        
        except Exception as e:
            logger.error(f"豆瓣读书爬虫异常: {str(e)}")
            return [], 0
    
    def crawl_keyword(self, keyword, max_results=None):
        all_books = []
        start = 0
        count = DOUBAN_PAGE_SIZE
        total = max_results if max_results else DOUBAN_MAX_RESULTS
        
        while start < total:
            books, current_total = self.search_books(keyword, start, count)
            
            if not books:
                break
            
            all_books.extend(books)
            
            if start == 0:
                total = min(current_total, total)
            
            start += count
            
            if start < total:
                self._add_random_delay()
        
        logger.info(f"豆瓣读书关键词 '{keyword}' 爬取完成，共获取 {len(all_books)} 本书")
        return all_books
    
    def crawl(self, keywords=None):
        if keywords is None:
            keywords = ['中国文学', '小说', '历史', '哲学', '科学', '艺术', '经济', '教育']
        
        all_books = []
        
        for keyword in keywords:
            books = self.crawl_keyword(keyword)
            all_books.extend(books)
        
        logger.info(f"豆瓣读书爬虫完成，总计获取 {len(all_books)} 本书")
        return all_books

if __name__ == '__main__':
    spider = DoubanSpider()
    books = spider.crawl_keyword('红楼梦', 20)
    print(f"获取书籍数量: {len(books)}")
    for book in books[:5]:
        print(f"书名: {book['title']}, 作者: {book['author']}")