import logging
import os
from config.config import LOG_DIR

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'scraper.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def get_logger(name):
    return logging.getLogger(name)