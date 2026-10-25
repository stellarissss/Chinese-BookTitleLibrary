"""中华书名库 · 采集与去重内核。

模块划分
--------
config    运行参数（速率、路径、UA）
net       带限速与重试的 HTTP 会话
textnorm  书名/作者归一化
quality   书目质量判定与营销文本剥离
store     SQLite 存储（原始记录 + 规范条目 + 断点）
sources   各数据源适配器
dedup     跨源聚类与规范名选择
"""

__version__ = "2.0.0"
