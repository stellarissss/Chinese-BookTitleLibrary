# 中文书籍数据库项目 - 产品需求文档

## Overview
- **Summary**: 构建一个Python爬虫项目，从多个公开数据源（豆瓣读书、当当网、孔夫子旧书网、Wikidata、Open Library等）采集中文书籍数据（书名、作者），经过数据清洗和去重处理后，生成统一格式的书籍数据库。
- **Purpose**: 收集尽可能多的中文书籍数据，建立一个高质量、无重复的中文书籍数据库，供后续研究和应用使用。
- **Target Users**: 书籍研究者、数据分析师、开发者、图书馆工作人员等需要中文书籍数据的人群。

## Goals
- 构建多源数据爬虫系统，覆盖至少5个可靠数据源
- 采集书名和作者信息，确保数据完整性
- 实现数据清洗功能（去除空格、特殊符号、乱码等）
- 实现数据去重功能，确保数据唯一性
- 生成统一格式的数据库（CSV/JSON/SQLite）

## Non-Goals (Out of Scope)
- 不采集书籍内容、摘要、封面等详细信息（仅采集书名和作者）
- 不处理需要登录认证的网站（如多抓鱼、各省市图书馆OPAC等）
- 不构建图形化用户界面（GUI）
- 不实现大规模分布式爬虫架构

## Background & Context
用户提供了20个潜在数据源，经过调研分析：
- **可直接API访问**：豆瓣读书（非官方）、当当网、孔夫子旧书网、Wikidata、Open Library
- **需要认证/限制访问**：CALIS联合目录、中国国家图书馆OPAC、各省市公共图书馆OPAC等
- **爬取难度高**：京东图书（反爬机制严格）、多抓鱼（需要登录）

本项目将优先实现可直接访问的数据源爬虫。

## Functional Requirements
- **FR-1**: 豆瓣读书爬虫 - 通过非官方API获取中文书籍数据
- **FR-2**: 当当网爬虫 - 通过公开API获取书籍数据
- **FR-3**: 孔夫子旧书网爬虫 - 通过开放平台API获取古籍和二手书数据
- **FR-4**: Wikidata爬虫 - 通过SPARQL查询获取中文书籍数据
- **FR-5**: Open Library爬虫 - 通过公开API获取书籍数据
- **FR-6**: 数据清洗模块 - 去除空格、特殊符号、乱码，统一格式
- **FR-7**: 数据去重模块 - 基于书名和作者组合去除重复数据
- **FR-8**: 数据存储模块 - 支持CSV、JSON、SQLite三种格式输出

## Non-Functional Requirements
- **NFR-1**: 反爬虫策略 - 添加随机延迟、User-Agent轮换、请求间隔控制
- **NFR-2**: 错误处理 - 实现异常捕获、重试机制、日志记录
- **NFR-3**: 可配置性 - 支持配置请求频率、数据源开关等参数
- **NFR-4**: 数据质量 - 确保书名和作者字段的完整性和准确性

## Constraints
- **Technical**: Python 3.8+，使用requests、beautifulsoup4、pandas等常用库
- **Dependencies**: 需要安装requests、beautifulsoup4、pandas、sqlite3等依赖
- **Ethical**: 遵守各网站robots.txt协议和使用条款，控制请求频率

## Assumptions
- 豆瓣读书非官方API在项目期间可用
- 各网站API接口格式稳定
- 用户已阅读并同意相关网站的使用条款

## Acceptance Criteria

### AC-1: 豆瓣读书爬虫功能
- **Given**: 配置好豆瓣读书爬虫参数
- **When**: 运行爬虫脚本
- **Then**: 成功获取中文书籍的书名和作者数据
- **Verification**: `programmatic`

### AC-2: 当当网爬虫功能
- **Given**: 配置好当当网爬虫参数
- **When**: 运行爬虫脚本
- **Then**: 成功获取书籍的书名和作者数据
- **Verification**: `programmatic`

### AC-3: 孔夫子旧书网爬虫功能
- **Given**: 配置好孔夫子旧书网API Key和爬虫参数
- **When**: 运行爬虫脚本
- **Then**: 成功获取古籍和二手书的书名和作者数据
- **Verification**: `programmatic`

### AC-4: Wikidata爬虫功能
- **Given**: 配置好SPARQL查询参数
- **When**: 运行爬虫脚本
- **Then**: 成功通过SPARQL查询获取中文书籍数据
- **Verification**: `programmatic`

### AC-5: Open Library爬虫功能
- **Given**: 配置好Open Library爬虫参数
- **When**: 运行爬虫脚本
- **Then**: 成功获取书籍的书名和作者数据
- **Verification**: `programmatic`

### AC-6: 数据清洗功能
- **Given**: 原始采集数据包含空格、特殊符号、乱码
- **When**: 运行数据清洗模块
- **Then**: 数据中不再包含多余空格、特殊符号和乱码，格式统一
- **Verification**: `programmatic`

### AC-7: 数据去重功能
- **Given**: 数据中存在重复的书名+作者组合
- **When**: 运行数据去重模块
- **Then**: 重复数据被移除，数据库中每本书的书名+作者组合唯一
- **Verification**: `programmatic`

### AC-8: 数据存储功能
- **Given**: 清洗和去重后的书籍数据
- **When**: 运行数据存储模块
- **Then**: 数据成功保存为CSV、JSON和SQLite格式文件
- **Verification**: `programmatic`

## Open Questions
- [ ] 孔夫子旧书网API Key的获取需要用户自行申请，如何处理未申请的情况？
- [ ] 豆瓣读书非官方API可能随时失效，需要备用方案
- [ ] 数据量较大时的存储和处理性能问题