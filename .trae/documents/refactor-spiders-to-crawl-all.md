# 重构爬虫：从关键词搜索改为全量分类浏览

## 概述
将4个爬虫从"关键词搜索"模式改为"全量分类浏览"模式，一次性爬取所有中文书籍（书名+作者），存入SQLite数据库。

## 当前状态分析
- 所有4个爬虫（douban、dangdang、wikidata、openlibrary）均基于关键词搜索
- `crawl_all.py` 使用30+个关键词列表遍历，但关键词永远无法覆盖所有中文书籍
- 需要改为：通过浏览分类/标签页来遍历所有书籍

## 各数据源全量爬取方案

### 1. 豆瓣读书 — 标签浏览模式
- **入口URL**: `https://book.douban.com/tag/`
- **方法**: 先获取所有标签（文学、小说、历史、哲学等约100+个标签），然后对每个中文相关标签遍历所有分页
- **分页URL**: `https://book.douban.com/tag/{tag}?start={offset}&type=T`
- **每页**: 20本书，最多约50页（共1000本/标签）
- **解析**: `<li class="subject-item">` → `<div class="info">` → `<h2><a title="书名">` + `<div class="pub">` 提取作者
- **文件**: `/workspace/chinese_books_scraper/spiders/douban_spider.py`

### 2. 当当网 — 分类浏览模式
- **入口URL**: `https://book.dangdang.com/` (左侧分类导航)
- **分类URL格式**: `http://category.dangdang.com/cp{category_id}.html` (如 `cp01.03.12.00.00.00`)
- **分页**: URL加 `pg{page}-` 前缀，如 `http://category.dangdang.com/pg2-cp01.03.12.00.00.00.html`
- **每页**: 约60本书，最多100页
- **解析**: `<ul class="bigimg">` → `<li>` → 书名从 `<a title="">` 或 `<img alt="">`，作者从 `<span class="search_book_author">`
- **文件**: `/workspace/chinese_books_scraper/spiders/dangdang_spider.py`

### 3. Wikidata — SPARQL全量查询
- **无需关键词**，直接用SPARQL查询"语言为中文的书"(P407: Q35288) 且 "实例为书"(P31: Q571)
- **SPARQL**:
  ```sparql
  SELECT ?item ?itemLabel ?authorLabel WHERE {
    ?item wdt:P31 wd:Q571.
    ?item wdt:P50 ?author.
    ?item wdt:P407 wd:Q35288.
    SERVICE wikibase:label { bd:serviceParam wikibase:language "zh,en". }
  } LIMIT 10000 OFFSET 0
  ```
- 用分页(OFFSET/LIMIT)获取所有结果
- **文件**: `/workspace/chinese_books_scraper/spiders/wikidata_spider.py`

### 4. Open Library — 语言筛选全量搜索
- **API URL**: `https://openlibrary.org/search.json`
- **参数**: `q=language:chi&limit=100&page=1` 或 `q=language:zho&limit=100&page=1`
- **分页**: page参数递增，直到无结果
- **文件**: `/workspace/chinese_books_scraper/spiders/openlibrary_spider.py`

### 5. crawl_all.py — 重写入口脚本
- 移除关键词列表，改为直接调用各爬虫的全量爬取方法
- 增加进度显示和断点续传

## 具体修改内容

### 修改1: `spiders/douban_spider.py`
- 新增 `fetch_all_tags()` 方法：访问 `https://book.douban.com/tag/` 获取所有标签列表
- 新增 `crawl_by_tag(tag)` 方法：对单个标签遍历所有分页
- 修改 `crawl()` 方法：改为 `crawl_all()` — 获取所有标签 → 逐标签遍历分页 → 返回全部数据
- 保留 `search_books()` 作为备用方法

### 修改2: `spiders/dangdang_spider.py`
- 新增 `fetch_all_categories()` 方法：访问当当网图书首页获取所有分类及其URL
- 新增 `crawl_by_category(category_url)` 方法：对单个分类遍历所有分页
- 修改 `crawl()` 方法：改为 `crawl_all()` — 获取所有分类 → 逐分类遍历分页 → 返回全部数据
- 保留 `search_books()` 作为备用方法

### 修改3: `spiders/wikidata_spider.py`
- 当前已使用SPARQL查询中文书籍，但限制了结果数量
- 修改：增加LIMIT上限，使用分页获取所有结果（每次10000条，OFFSET递增）
- 增加第二个查询：不仅查P407=Q35288（中文语言），还查中国作者(P27=Q148)写的书

### 修改4: `spiders/openlibrary_spider.py`
- 新增 `crawl_all_chinese()` 方法：用 `language:chi` 和 `language:zho` 搜索所有中文书
- 分页获取全部结果（每页100条，page递增直到无结果）

### 修改5: `crawl_all.py`
- 移除关键词列表
- 调用各爬虫的 `crawl_all()` 方法
- 增加进度显示：每爬取一批数据后打印当前总数
- 增加断点续传：每次成功爬取后立即写入数据库（增量写入）

## 假设与决策
1. **豆瓣标签页**：每个标签最多显示约1000本书（50页×20本），这是豆瓣的限制。部分热门标签可能有更多书无法完全获取，但已覆盖大部分
2. **当当网分类**：每分类最多100页×60本=6000本，超过6000本的分类需要按价格/评分进一步细分，但为简化实现先不处理
3. **Wikidata**：中文书籍数据量可能达数十万条，需要多次分页查询
4. **Open Library**：使用 `language:chi` 和 `language:zho` 两种语言代码搜索，合并去重
5. **增量写入**：每批次数据立即写入SQLite（INSERT OR IGNORE），避免内存溢出

## 验证步骤
1. 豆瓣爬虫：能获取标签列表（>50个标签），能对单个标签遍历分页
2. 当当网爬虫：能获取分类列表，能对单个分类遍历分页
3. Wikidata爬虫：SPARQL查询返回结果，分页正常
4. Open Library爬虫：语言筛选搜索返回中文书籍，分页正常
5. 最终数据库包含多个来源的数据，无重复记录
