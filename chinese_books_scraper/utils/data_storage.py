import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import csv
import sqlite3
import pandas as pd
from config.logging import get_logger

logger = get_logger(__name__)

class DataStorage:
    def __init__(self, output_dir='output'):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def save_to_csv(self, books, filename='chinese_books.csv'):
        try:
            filepath = os.path.join(self.output_dir, filename)
            
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['书名', '作者', '来源'])
                
                for book in books:
                    writer.writerow([
                        book.get('title', ''),
                        book.get('author', ''),
                        book.get('source', '')
                    ])
            
            logger.info(f"数据已保存到CSV文件: {filepath}，共 {len(books)} 条记录")
            return filepath
        
        except Exception as e:
            logger.error(f"保存CSV文件失败: {str(e)}")
            return None
    
    def save_to_json(self, books, filename='chinese_books.json'):
        try:
            filepath = os.path.join(self.output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(books, f, ensure_ascii=False, indent=2)
            
            logger.info(f"数据已保存到JSON文件: {filepath}，共 {len(books)} 条记录")
            return filepath
        
        except Exception as e:
            logger.error(f"保存JSON文件失败: {str(e)}")
            return None
    
    def save_to_sqlite(self, books, filename='chinese_books.db'):
        try:
            filepath = os.path.join(self.output_dir, filename)
            
            conn = sqlite3.connect(filepath)
            
            if books:
                df = pd.DataFrame(books)
                df.to_sql('books', conn, if_exists='replace', index=False)
                
                cursor = conn.cursor()
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_title ON books(title)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_author ON books(author)')
            else:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS books (
                        title TEXT,
                        author TEXT,
                        source TEXT
                    )
                ''')
            
            conn.commit()
            conn.close()
            
            logger.info(f"数据已保存到SQLite数据库: {filepath}，共 {len(books)} 条记录")
            return filepath
        
        except Exception as e:
            logger.error(f"保存SQLite数据库失败: {str(e)}")
            return None
    
    def save_all(self, books):
        results = {}
        
        csv_path = self.save_to_csv(books)
        results['csv'] = csv_path
        
        json_path = self.save_to_json(books)
        results['json'] = json_path
        
        sqlite_path = self.save_to_sqlite(books)
        results['sqlite'] = sqlite_path
        
        return results
    
    def load_from_csv(self, filename='chinese_books.csv'):
        try:
            filepath = os.path.join(self.output_dir, filename)
            
            if not os.path.exists(filepath):
                logger.warning(f"CSV文件不存在: {filepath}")
                return []
            
            books = []
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    books.append({
                        'title': row.get('书名', ''),
                        'author': row.get('作者', ''),
                        'source': row.get('来源', '')
                    })
            
            logger.info(f"从CSV文件加载数据完成，共 {len(books)} 条记录")
            return books
        
        except Exception as e:
            logger.error(f"加载CSV文件失败: {str(e)}")
            return []
    
    def load_from_json(self, filename='chinese_books.json'):
        try:
            filepath = os.path.join(self.output_dir, filename)
            
            if not os.path.exists(filepath):
                logger.warning(f"JSON文件不存在: {filepath}")
                return []
            
            with open(filepath, 'r', encoding='utf-8') as f:
                books = json.load(f)
            
            logger.info(f"从JSON文件加载数据完成，共 {len(books)} 条记录")
            return books
        
        except Exception as e:
            logger.error(f"加载JSON文件失败: {str(e)}")
            return []
    
    def load_from_sqlite(self, filename='chinese_books.db'):
        try:
            filepath = os.path.join(self.output_dir, filename)
            
            if not os.path.exists(filepath):
                logger.warning(f"SQLite数据库不存在: {filepath}")
                return []
            
            conn = sqlite3.connect(filepath)
            df = pd.read_sql('SELECT * FROM books', conn)
            conn.close()
            
            books = df.to_dict('records')
            
            logger.info(f"从SQLite数据库加载数据完成，共 {len(books)} 条记录")
            return books
        
        except Exception as e:
            logger.error(f"加载SQLite数据库失败: {str(e)}")
            return []

if __name__ == '__main__':
    test_books = [
        {'title': '红楼梦', 'author': '曹雪芹', 'source': 'douban'},
        {'title': '三国演义', 'author': '罗贯中', 'source': 'douban'},
        {'title': '水浒传', 'author': '施耐庵', 'source': 'dangdang'},
        {'title': '西游记', 'author': '吴承恩', 'source': 'wikidata'},
        {'title': '唐诗三百首', 'author': '蘅塘退士', 'source': 'openlibrary'},
    ]
    
    storage = DataStorage()
    
    print("保存数据...")
    results = storage.save_all(test_books)
    print(f"保存结果: {results}")
    
    print("\n从CSV加载...")
    csv_books = storage.load_from_csv()
    print(f"加载数量: {len(csv_books)}")
    
    print("\n从JSON加载...")
    json_books = storage.load_from_json()
    print(f"加载数量: {len(json_books)}")
    
    print("\n从SQLite加载...")
    sqlite_books = storage.load_from_sqlite()
    print(f"加载数量: {len(sqlite_books)}")
    
    print("\n验证数据一致性:")
    print(f"原始: {len(test_books)}, CSV: {len(csv_books)}, JSON: {len(json_books)}, SQLite: {len(sqlite_books)}")