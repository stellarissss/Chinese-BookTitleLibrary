import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
import hashlib
import unicodedata
from config.logging import get_logger

logger = get_logger(__name__)

class DataCleaner:
    @staticmethod
    def clean_text(text):
        if not text:
            return ''
        
        text = str(text).strip()
        
        text = re.sub(r'\s+', ' ', text)
        
        text = text.replace('\u3000', ' ').replace('\xa0', ' ')
        
        text = text.replace('《', '').replace('》', '')
        text = text.replace('【', '').replace('】', '')
        text = text.replace('[', '').replace(']', '')
        text = text.replace('（', '').replace('）', '')
        text = text.replace('(', '').replace(')', '')
        text = text.replace('「', '').replace('」', '')
        text = text.replace('『', '').replace('』', '')
        
        text = re.sub(r'[^\w\s\u4e00-\u9fff，。！？、；：""''·…—–-]', '', text)
        
        text = unicodedata.normalize('NFKC', text)
        
        text = re.sub(r'[<>/\\|:*?"\']', '', text)
        
        text = text.strip()
        
        return text
    
    @staticmethod
    def clean_title(title):
        title = DataCleaner.clean_text(title)
        
        title = re.sub(r'\s*[第卷部册].*$', '', title)
        
        title = re.sub(r'\s*\(\s*[\d一二三四五六七八九十]+[版版次印次]\s*\)', '', title)
        title = re.sub(r'\s*[\[\(]*(修订版|增订版|新版|典藏版|精装版|平装版|图文版|插图版)[\]\)]*\s*', '', title)
        
        return title.strip()
    
    @staticmethod
    def clean_author(author):
        author = DataCleaner.clean_text(author)
        
        author = re.sub(r'\s*[著编主编编著译译著校注校点整理注疏笺注辑注辑校].*$', '', author)
        
        return author.strip()
    
    @staticmethod
    def clean_book(book):
        return {
            'title': DataCleaner.clean_title(book.get('title', '')),
            'author': DataCleaner.clean_author(book.get('author', '')),
            'source': book.get('source', '')
        }
    
    @staticmethod
    def generate_book_key(title, author):
        key = f"{title.lower().strip()}_{author.lower().strip()}"
        return hashlib.md5(key.encode('utf-8')).hexdigest()
    
    @staticmethod
    def remove_duplicates(books):
        seen = set()
        unique_books = []
        
        for book in books:
            title = book.get('title', '')
            author = book.get('author', '')
            
            if not title or not author:
                continue
            
            key = DataCleaner.generate_book_key(title, author)
            
            if key not in seen:
                seen.add(key)
                unique_books.append(book)
        
        original_count = len(books)
        unique_count = len(unique_books)
        duplicate_count = original_count - unique_count
        
        logger.info(f"数据去重完成: 原始 {original_count} 条，去重后 {unique_count} 条，移除重复 {duplicate_count} 条")
        
        return unique_books
    
    @staticmethod
    def clean_and_deduplicate(books):
        cleaned_books = []
        
        for book in books:
            cleaned_book = DataCleaner.clean_book(book)
            
            if cleaned_book['title'] and cleaned_book['author']:
                cleaned_books.append(cleaned_book)
        
        logger.info(f"数据清洗完成，清洗前 {len(books)} 条，清洗后 {len(cleaned_books)} 条")
        
        deduplicated_books = DataCleaner.remove_duplicates(cleaned_books)
        
        return deduplicated_books

if __name__ == '__main__':
    test_books = [
        {'title': '  红楼梦  ', 'author': '曹雪芹', 'source': 'douban'},
        {'title': '红楼梦', 'author': '曹雪芹', 'source': 'dangdang'},
        {'title': '《三国演义》', 'author': '罗贯中', 'source': 'douban'},
        {'title': '三国演义（修订版）', 'author': '罗贯中 著', 'source': 'dangdang'},
        {'title': '水浒传第1版', 'author': '施耐庵', 'source': 'douban'},
        {'title': '西游记', 'author': '吴承恩', 'source': 'douban'},
        {'title': '', 'author': '吴承恩', 'source': 'test'},
        {'title': '西游记', 'author': '', 'source': 'test'},
        {'title': '书名\u3000含空格', 'author': '作者', 'source': 'test'},
    ]
    
    cleaned = DataCleaner.clean_and_deduplicate(test_books)
    print(f"清洗后书籍数量: {len(cleaned)}")
    for book in cleaned:
        print(f"书名: '{book['title']}', 作者: '{book['author']}', 来源: {book['source']}")