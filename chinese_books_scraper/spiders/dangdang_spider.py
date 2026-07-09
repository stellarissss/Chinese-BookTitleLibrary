import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import random
import time
import re
from bs4 import BeautifulSoup
from config.config import DANGDANG_SEARCH_URL, DANGDANG_MAX_PAGES, USER_AGENTS, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX
from config.logging import get_logger

logger = get_logger(__name__)

DANGDANG_BOOK_HOME = 'https://book.dangdang.com/'
DANGDANG_CATEGORY_URL = 'http://category.dangdang.com/'

class DangdangSpider:
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
    
    def _make_request(self, url, params=None):
        headers = {
            'User-Agent': self._get_random_user_agent(),
            'Referer': 'https://www.dangdang.com/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        try:
            response = self.session.get(url, headers=headers, params=params, timeout=15)
            response.encoding = None
            if 'charset' not in response.headers.get('Content-Type', ''):
                response.encoding = 'gbk'
            return response
        except Exception as e:
            logger.error(f"请求失败 {url}: {str(e)}")
            return None
    
    def fetch_all_categories(self):
        """从当当网图书首页获取所有分类及URL"""
        try:
            response = self._make_request(DANGDANG_BOOK_HOME)
            if not response or response.status_code != 200:
                logger.warning(f"获取当当网首页失败，状态码: {response.status_code if response else 'None'}")
                return []
            
            soup = BeautifulSoup(response.text, 'lxml')
            categories = []
            seen_urls = set()
            
            links = soup.find_all('a', href=re.compile(r'category\.dangdang\.com/cp\d+'))
            for link in links:
                url = link.get('href', '')
                name = link.get_text(strip=True)
                if url and name and url not in seen_urls:
                    seen_urls.add(url)
                    categories.append({'name': name, 'url': url})
            
            if not categories:
                links = soup.find_all('a', href=re.compile(r'book\.dangdang\.com/\d+\.\d+'))
                for link in links:
                    href = link.get('href', '')
                    name = link.get_text(strip=True)
                    match = re.search(r'(\d+\.\d+(?:\.\d+)*)', href)
                    if match and name and href not in seen_urls:
                        cat_id = match.group(1)
                        url = f'http://category.dangdang.com/cp{cat_id}.00.00.00.html'
                        if url not in seen_urls:
                            seen_urls.add(url)
                            categories.append({'name': name, 'url': url})
            
            logger.info(f"获取到 {len(categories)} 个当当网分类")
            return categories
        
        except Exception as e:
            logger.error(f"获取分类列表异常: {str(e)}")
            return []
    
    def crawl_by_category(self, category_url, category_name='', max_pages=100):
        """对单个分类遍历所有分页，获取该分类下的所有书籍"""
        all_books = []
        
        base_url = category_url.replace('.html', '').replace('cp', '')
        if not base_url:
            base_url = category_url
        
        for page in range(1, max_pages + 1):
            try:
                if page == 1:
                    url = category_url
                else:
                    url = category_url.replace('.html', '')
                    url = f'{url.replace("http://category.dangdang.com/", "http://category.dangdang.com/pg" + str(page) + "-")}.html'
                    if url == category_url:
                        url = f'http://category.dangdang.com/pg{page}-cp{base_url}.html'
                
                response = self._make_request(url)
                
                if not response or response.status_code != 200:
                    break
                
                soup = BeautifulSoup(response.text, 'lxml')
                
                book_list = soup.find('ul', class_='bigimg')
                if not book_list:
                    book_list = soup.find('div', class_='shoplist')
                
                if not book_list:
                    break
                
                lis = book_list.find_all('li')
                if not lis:
                    break
                
                page_books = []
                for li in lis:
                    dd_name = li.get('ddt-pit', '')
                    if not dd_name and not li.get('class'):
                        continue
                    
                    title = ''
                    title_tag = li.find('a', attrs={'dd_name': re.compile(r'itemlist-picture|ItemImage')})
                    if not title_tag:
                        title_tag = li.find('a', class_='pic')
                    if not title_tag:
                        title_tag = li.find('img')
                        if title_tag:
                            title = title_tag.get('alt', '').strip()
                    else:
                        title = title_tag.get('title', '').strip() or title_tag.get('alt', '').strip()
                    
                    if not title:
                        a_tags = li.find_all('a')
                        for a in a_tags:
                            t = a.get('title', '').strip()
                            if t:
                                title = t
                                break
                    
                    if not title:
                        continue
                    
                    author = ''
                    author_tag = li.find('span', class_='search_book_author')
                    if not author_tag:
                        author_tag = li.find('p', class_='search_book_author')
                    if not author_tag:
                        author_tag = li.find('span', attrs={'dd_name': 'itemlist-author'})
                    
                    if author_tag:
                        author_text = author_tag.get_text(strip=True)
                        if author_text:
                            author_text = re.sub(r'^[\/\s]+', '', author_text)
                            parts = author_text.split('/')
                            if parts:
                                author = parts[0].strip()
                                author = re.sub(r'^\s*\[.*?\]\s*', '', author)
                    
                    if title and author:
                        page_books.append({
                            'title': title,
                            'author': author,
                            'source': 'dangdang'
                        })
                
                all_books.extend(page_books)
                logger.info(f"分类 '{category_name}' 第{page}页，获取 {len(page_books)} 本书，累计 {len(all_books)} 本")
                
                if len(page_books) < 20:
                    break
                
                self._add_random_delay()
            
            except Exception as e:
                logger.error(f"分类 '{category_name}' 第{page}页爬取异常: {str(e)}")
                break
        
        logger.info(f"分类 '{category_name}' 爬取完成，共获取 {len(all_books)} 本书")
        return all_books
    
    def crawl_all(self, on_batch=None):
        """全量爬取：获取所有分类，逐分类遍历分页"""
        categories = self.fetch_all_categories()
        
        if not categories:
            logger.warning("未获取到分类列表，使用预设分类")
            categories = [
                {'name': '小说', 'url': 'http://category.dangdang.com/cp01.03.00.00.00.00.html'},
                {'name': '文学', 'url': 'http://category.dangdang.com/cp01.01.00.00.00.00.html'},
                {'name': '历史', 'url': 'http://category.dangdang.com/cp01.07.00.00.00.00.html'},
                {'name': '哲学宗教', 'url': 'http://category.dangdang.com/cp01.08.00.00.00.00.html'},
                {'name': '社会科学', 'url': 'http://category.dangdang.com/cp01.10.00.00.00.00.html'},
                {'name': '传记', 'url': 'http://category.dangdang.com/cp01.09.00.00.00.00.html'},
                {'name': '少儿', 'url': 'http://category.dangdang.com/cp01.11.00.00.00.00.html'},
                {'name': '艺术', 'url': 'http://category.dangdang.com/cp01.06.00.00.00.00.html'},
                {'name': '经济', 'url': 'http://category.dangdang.com/cp01.13.00.00.00.00.html'},
                {'name': '管理', 'url': 'http://category.dangdang.com/cp01.14.00.00.00.00.html'},
                {'name': '科技', 'url': 'http://category.dangdang.com/cp01.15.00.00.00.00.html'},
                {'name': '教育', 'url': 'http://category.dangdang.com/cp01.12.00.00.00.00.html'},
                {'name': '生活', 'url': 'http://category.dangdang.com/cp01.16.00.00.00.00.html'},
                {'name': '青春文学', 'url': 'http://category.dangdang.com/cp01.05.00.00.00.00.html'},
                {'name': '成功励志', 'url': 'http://category.dangdang.com/cp01.17.00.00.00.00.html'},
            ]
        
        all_books = []
        for i, cat in enumerate(categories):
            logger.info(f"正在处理分类 [{i+1}/{len(categories)}]: {cat['name']}")
            books = self.crawl_by_category(cat['url'], cat['name'])
            all_books.extend(books)
            
            if on_batch:
                on_batch(books, cat['name'])
            
            if i < len(categories) - 1:
                self._add_random_delay()
        
        logger.info(f"当当网全量爬取完成，共获取 {len(all_books)} 本书")
        return all_books

if __name__ == '__main__':
    spider = DangdangSpider()
    books = spider.crawl_all()
    print(f"获取书籍数量: {len(books)}")
    for book in books[:10]:
        print(f"书名: {book['title']}, 作者: {book['author']}")
