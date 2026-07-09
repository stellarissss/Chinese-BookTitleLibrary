import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import random
import time
import re
from bs4 import BeautifulSoup
from config.config import USER_AGENTS, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX
from config.logging import get_logger

logger = get_logger(__name__)

DOUBAN_TAG_INDEX_URL = 'https://book.douban.com/tag/'
DOUBAN_TAG_URL_TEMPLATE = 'https://book.douban.com/tag/{tag}'
DOUBAN_PAGE_SIZE = 20

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
    
    def _make_request(self, url, params=None):
        headers = {
            'User-Agent': self._get_random_user_agent(),
            'Referer': 'https://book.douban.com/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0',
        }
        try:
            response = self.session.get(url, headers=headers, params=params, timeout=15)
            return response
        except Exception as e:
            logger.error(f"请求失败 {url}: {str(e)}")
            return None
    
    def fetch_all_tags(self):
        """从豆瓣标签首页获取所有图书标签列表"""
        try:
            response = self._make_request(DOUBAN_TAG_INDEX_URL)
            if not response or response.status_code != 200:
                logger.warning(f"获取标签页失败，状态码: {response.status_code if response else 'None'}")
                return []
            
            soup = BeautifulSoup(response.text, 'lxml')
            tags = []
            
            tag_links = soup.select('#content div.article div a')
            if not tag_links:
                tag_links = soup.select('td a')
            if not tag_links:
                tag_links = soup.find_all('a', href=re.compile(r'/tag/'))
            
            for link in tag_links:
                tag_name = link.get_text(strip=True)
                href = link.get('href', '')
                if tag_name and '/tag/' in href:
                    match = re.search(r'/tag/([^/?]+)', href)
                    if match:
                        tag = match.group(1)
                        if tag not in tags:
                            tags.append(tag)
            
            logger.info(f"获取到 {len(tags)} 个豆瓣标签")
            return tags
        
        except Exception as e:
            logger.error(f"获取标签列表异常: {str(e)}")
            return []
    
    def crawl_by_tag(self, tag, max_pages=50):
        """对单个标签遍历所有分页，获取该标签下的所有书籍"""
        all_books = []
        
        for page in range(max_pages):
            start = page * DOUBAN_PAGE_SIZE
            
            try:
                params = {
                    'start': start,
                    'type': 'T'
                }
                url = DOUBAN_TAG_URL_TEMPLATE.format(tag=tag)
                response = self._make_request(url, params=params)
                
                if not response or response.status_code != 200:
                    if response and response.status_code == 403:
                        logger.warning(f"标签 '{tag}' 第{page+1}页被拒绝(403)，停止该标签")
                    break
                
                soup = BeautifulSoup(response.text, 'lxml')
                book_items = soup.find_all('li', class_='subject-item')
                
                if not book_items:
                    break
                
                page_books = []
                for item in book_items:
                    info = item.find('div', class_='info')
                    if not info:
                        continue
                    
                    title_tag = info.find('h2')
                    if title_tag:
                        a_tag = title_tag.find('a')
                        title = a_tag.get('title', '').strip() if a_tag else ''
                    else:
                        continue
                    
                    if not title:
                        continue
                    
                    author = ''
                    pub_div = info.find('div', class_='pub')
                    if pub_div:
                        pub_text = pub_div.get_text(strip=True)
                        if pub_text:
                            parts = pub_text.split('/')
                            if parts:
                                author = parts[0].strip()
                                author = re.sub(r'^\s*\[.*?\]\s*', '', author)
                    
                    if title and author:
                        page_books.append({
                            'title': title,
                            'author': author,
                            'source': 'douban'
                        })
                
                all_books.extend(page_books)
                logger.info(f"标签 '{tag}' 第{page+1}页，获取 {len(page_books)} 本书，累计 {len(all_books)} 本")
                
                if len(page_books) < DOUBAN_PAGE_SIZE:
                    break
                
                self._add_random_delay()
            
            except Exception as e:
                logger.error(f"标签 '{tag}' 第{page+1}页爬取异常: {str(e)}")
                break
        
        logger.info(f"标签 '{tag}' 爬取完成，共获取 {len(all_books)} 本书")
        return all_books
    
    def crawl_all(self, on_batch=None):
        """全量爬取：获取所有标签，逐标签遍历分页"""
        tags = self.fetch_all_tags()
        
        if not tags:
            logger.warning("未获取到标签列表，使用预设标签")
            tags = [
                '小说', '文学', '中国文学', '外国文学', '经典', '散文', '随笔', '诗歌',
                '古典文学', '当代文学', '名著', '杂文', '诗词', '童话', '儿童文学',
                '历史', '中国历史', '哲学', '心理学', '社会学', '文化', '艺术', '政治',
                '传记', '国学', '军事', '佛教', '宗教', '考古', '近代史',
                '武侠', '科幻', '推理', '悬疑', '言情', '奇幻', '网络小说',
                '漫画', '绘本', '青春', '经济', '管理', '商业', '金融', '投资',
                '科普', '科学', '编程', '互联网', '算法', '科技',
                '旅行', '生活', '心理', '励志', '教育', '美食', '健康',
                '设计', '建筑', '电影', '音乐', '摄影', '绘画', '戏剧',
            ]
        
        all_books = []
        for i, tag in enumerate(tags):
            logger.info(f"正在处理标签 [{i+1}/{len(tags)}]: {tag}")
            books = self.crawl_by_tag(tag)
            all_books.extend(books)
            
            if on_batch:
                on_batch(books, tag)
            
            if i < len(tags) - 1:
                self._add_random_delay()
        
        logger.info(f"豆瓣读书全量爬取完成，共获取 {len(all_books)} 本书")
        return all_books

if __name__ == '__main__':
    spider = DoubanSpider()
    books = spider.crawl_all()
    print(f"获取书籍数量: {len(books)}")
    for book in books[:10]:
        print(f"书名: {book['title']}, 作者: {book['author']}")
