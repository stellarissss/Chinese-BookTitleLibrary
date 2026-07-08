import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOG_DIR = os.path.join(BASE_DIR, 'logs')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

REQUEST_DELAY_MIN = 1
REQUEST_DELAY_MAX = 3

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15'
]

DOUBAN_API_URL = 'https://api.douban.com/v2/book/search'
DOUBAN_MAX_RESULTS = 1000

DANGDANG_SEARCH_URL = 'https://search.dangdang.com/'
DANGDANG_MAX_PAGES = 50

KONGFZ_API_KEY = os.getenv('KONGFZ_API_KEY', '')
KONGFZ_API_URL = 'https://api.kongfz.com/api/v1/books/search'

WIKIDATA_QUERY_URL = 'https://query.wikidata.org/sparql'

OPENLIBRARY_SEARCH_URL = 'https://openlibrary.org/search.json'
OPENLIBRARY_BOOK_URL = 'https://openlibrary.org/api/books'

OUTPUT_FORMATS = ['csv', 'json', 'sqlite']
OUTPUT_FILENAME = 'chinese_books'

SOURCES = {
    'douban': True,
    'dangdang': True,
    'kongfz': True,
    'wikidata': True,
    'openlibrary': True
}