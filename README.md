# 中华书名库 · Chinese Book Title Library

把散落在电商、读书社区、图书馆目录里的中文书名，收敛成一份**可去重、可回溯、可续跑**的书目库。

不是「爬虫脚本合集」，是一条完整的数据流水线：采集 → 归一化 → 质量判定 → 跨源聚类 → 导出。

---

## 先说清楚三件事

**一、「中国所有书」做不到。** 不存在完整的全国出版物清单，1949 年以来的正式出版物累计
数百万种，其中大量从未被系统著录。任何声称「全量」的项目都不成立。

**二、瓶颈不是算法，是数据权限。** 最全的中文书目在中国国家版本馆（PDC 平台，馆藏样本库
650 万条），但不注册拿不到。详见 [`docs/RESEARCH.md`](docs/RESEARCH.md)。

**三、本项目真正解决的是「去重」和「质量」。** 拿 50 万条书名不难，难的是这 50 万条里
没有一堆「当当自营正版包邮」的尾巴，也没有把《西游记续》并进《西游记》。
这两件事才是书名库的价值所在。

实测数字见 [`REPORT.md`](REPORT.md)，由 `python -m cnbook report` 从数据库自动生成。

---

## 快速开始

```bash
pip install -r requirements.txt

# 采集（可中断，重跑会跳过已完成的类目）
python -m cnbook crawl dangdang --max-pages 30 --workers 2
python -m cnbook crawl douban
python -m cnbook crawl weread

# 归一化 + 去重 + 写规范表
python -m cnbook build --review

# 导出
python -m cnbook export --min-conf 0.9      # 只要高置信书名
python -m cnbook report                     # 生成 REPORT.md
```

### 关于当当的 cookie

当当对无 cookie 的直连返回 `405`。程序会用真实浏览器（Chrome DevTools Protocol）取一次
cookie，拦截时自动刷新，因此**需要先启动一个带调试端口的 Chrome**：

```bash
google-chrome --headless=new --no-sandbox --remote-debugging-port=9222 \
  --user-data-dir=/root/.cdp-browser/profile
```

取不到浏览器时，也可以手工把 cookie 写进 `.cookies.txt`（`name=value; ...` 格式）。

### 速率

默认按站点串行限速（`CNBOOK_DELAY_MIN` / `CNBOOK_DELAY_MAX`，单位秒）。
**不要调得太激进**——当当在约 2.5 req/s 下会封 IP 十几分钟，豆瓣在连续 150 次请求后开始
限流。项目内已内置冷却重试，但最好的策略是慢慢来。

---

## 目录结构

```
cnbook/
├── config.py         运行参数（速率、路径）
├── net.py            限速 HTTP 会话（重试、编码纠正、cookie 刷新）
├── textnorm.py       书名/著者归一化（本项目最核心的模块）
├── quality.py        书目判定（拒收非图书商品）
├── lexicon.py        书名词典 + 最长前缀切分
├── store.py          SQLite 存储（原始记录 / 规范条目 / 断点）
├── dedup.py          跨源聚类与规范名选择
├── report.py         从库生成 REPORT.md
├── browser_cookie.py 从 CDP 浏览器导出 cookie
├── cli.py            命令行入口
└── sources/
    ├── dangdang.py   当当分类分层遍历
    ├── douban.py     豆瓣标签遍历
    ├── weread.py     微信读书检索
    └── pdc.py        国家版本馆（需账号，默认不启用）

docs/RESEARCH.md      同类项目调研与「全量」可行性分析
docs/ROADMAP.md       从 50 万到「不漏」的四档路径
tests/                归一化与去重的回归测试
data/                 运行产物（SQLite / CSV）
chinese_books_scraper/ 初版爬虫，已被 cnbook 取代，仅作历史保留
```

---

## 数据模型

两层结构，职责分离：

```
raw      一条记录 = 一个数据源的一个页面条目，主键 (source, source_id)
         → 天然幂等，同一页跑十次也只有一行

books    一条记录 = 一个规范化书名，title_key 唯一
         → 携带 sources / aliases / confidence，可回溯到 raw
```

`raw` 保证「不丢」，`books` 保证「不重」。中间的转换是幂等的：随时可以 `build` 重算，
不需要重新采集。

---

## 三个设计决策

### 1. 只对「完全一致」自动合并

中文书名的近似判断是不可靠的：

| 案例 | 应该 | 纯字符串会 |
|---|---|---|
| 《红楼梦》 vs《红楼梦（全二册）》 | 合并 | 能合（卷册已剥离） |
| 《西游记》 vs《西游记续》 | 不合并 | 可能误合 |
| 《大学》 vs《大学·中庸》 | 见仁见智 | 无法判断 |

所以：**规范化后完全相同的才自动合并，近似但不相同的只输出候选清单**
（`data/review_near_duplicates.csv`），交给人判断。

误合并（两本书变一本）比漏合并（一本书两条）更难被发现、危害更大。这条原则牺牲一部分
「不重」，换取「不漏」的可控。

### 2. 每条书名带置信度

电商标题是「书名 + 卖点 + 赠品 + 出版社」的拼接，规则清洗不可能 100% 干净。
与其假装干净，不如**标注干净程度**：

- `1.0` 未检出营销噪声
- `0.6` 做过截断
- `0.3` 截断后仍有可疑片段

导出时加 `--min-conf 0.9` 即可只取可信部分，其余留给人工或词典二次清洗。

### 3. 中文标点不归一化为半角

`NFKC` 会把「，：（）」压成「,:()」。在中文书名里这是错的。
`textnorm.squash` 只折叠全角字母数字与空白，其余原样保留——这条规则有专门的测试守着。

---

## 合规与边界

- 只采集**公开列表页**，不登录、不绕过验证码、不逆向加密参数。
- 限速保守，遇拦截即冷却，不做重试轰炸。
- 遵守各站 `robots` 与使用条款；采集结果仅供研究与个人使用，不二次分发原始页面内容。
- 需要账号的数据源（PDC）**不内置凭据**，请用环境变量传入自己的 cookie。

---

## 下一步

见 [`docs/ROADMAP.md`](docs/ROADMAP.md)。最短的一条路径是：注册 PDC 账号，用本库的书名反查
ISBN，再走平台的「批量套录」（单次 5000 条）把 1949 年以来的馆藏样本数据补齐。

## 许可

Apache License 2.0，见 [`LICENSE`](LICENSE)。
