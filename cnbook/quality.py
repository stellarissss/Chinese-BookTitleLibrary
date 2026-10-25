"""书目判定：这条记录到底是不是一本书。

电商站点的图书频道会混入文具、电子设备、课程卡、日历等非图书商品；
古籍与教材则常有「题名即丛书名」的情况。这里用显式规则做二元判定，
宁可漏掉边缘品类，也不让噪声进入书名库。
"""

from __future__ import annotations

import re

from . import textnorm as tn

# 明显非图书的商品词。命中即拒。
_NON_BOOK = (
    "会议平板", "触控一体机", "投影仪", "打印机", "学习机", "点读笔", "智能笔",
    "台灯", "书包", "文具", "玩具", "拼图", "积木", "手办", "盲盒", "挂历",
    "台历", "日历本", "笔记本子", "手账", "贴纸", "水杯", "抱枕", "帆布袋",
    "耳机", "键盘", "鼠标", "硬盘", "路由器", "充电宝", "数据线", "屏幕",
    "课程卡", "网课", "会员卡", "点卡", "优惠券", "代金券", "礼盒装茶叶",
    "窗帘", "床品", "厨具", "健身器材", "化妆品", "保健品", "食品",
)

# 标题层面不可接受的模式（价格、链接、纯符号）。
_RE_BAD_TITLE = re.compile(
    r"(?:http|www\.|\.com|\.cn|￥|¥|\d+\.\d+\s*元|包邮|客服|发票|运费|"
    r"拍下|下单|咨询|联系客服)"
)

_RE_ONLY_PUNCT = re.compile(r"^[\W_]+$", re.UNICODE)


def is_book(
    title: str,
    *,
    min_han_ratio: float = 0.34,
    max_len: int = 60,
) -> tuple[bool, str]:
    """判定一条记录是否收录。返回 (是否收录, 拒绝原因)。"""
    if not title or len(title) < 1:
        return False, "empty"
    if len(title) > max_len:
        return False, "too_long"
    if _RE_ONLY_PUNCT.match(title):
        return False, "punct_only"
    if _RE_BAD_TITLE.search(title):
        return False, "marketing"
    for word in _NON_BOOK:
        if word in title:
            return False, "non_book"

    # 中文书名应含汉字；纯外文条目在中文书名库中暂不收录。
    if tn.cjk_ratio(title) < min_han_ratio:
        return False, "not_chinese"

    # 连续 6 个以上相同字符，多为刷屏或占位。
    if re.search(r"(.)\1{5,}", title):
        return False, "repeated_char"
    return True, ""


def score(confidence: float, n_sources: int, has_author: bool, has_isbn: bool) -> float:
    """条目可信度：清洗置信度为主，多源互证与字段完整度为辅。"""
    s = confidence
    s += min(n_sources - 1, 3) * 0.08
    if has_author:
        s += 0.04
    if has_isbn:
        s += 0.04
    return round(min(s, 1.0), 3)
