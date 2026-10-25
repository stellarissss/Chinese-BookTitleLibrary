"""书名与著者的归一化。

中文书名著录的真正难点不在编码，而在「同一条记录里混进了多少非书名文本」：
电商标题往往是 `书名 + 卖点 + 赠品 + 出版社` 的拼接，古籍则有卷次、版本、
丛书名层层嵌套。本模块只做可解释的确定性变换，任何一步都不猜测语义。
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------- 基础清洗

_RE_SPACE = re.compile(r"[\s\u3000\u00a0]+")
_RE_TITLE_WRAP = re.compile(r"^[《〈「『【\[]\s*(.+?)\s*[》〉」』】\]]$", re.S)


def squash(text: str) -> str:
    """折叠空白、统一全角字母数字。

    刻意**不做** NFKC：NFKC 会把「，：（）」压成「,:()」，中文书名里这是错的。
    只折叠真正该折叠的部分——全角字母数字与各类空白。
    """
    if not text:
        return ""
    out = []
    for ch in str(text):
        code = ord(ch)
        if 0xFF10 <= code <= 0xFF19 or 0xFF21 <= code <= 0xFF3A or 0xFF41 <= code <= 0xFF5A:
            out.append(chr(code - 0xFEE0))
        elif ch in "\u3000\xa0\u2002\u2003\u2009":
            out.append(" ")
        else:
            out.append(ch)
    s = "".join(out)
    return _RE_SPACE.sub(" ", s).strip()


def strip_title_wrap(text: str) -> str:
    """去掉成对的《》等包裹符号。"""
    s = squash(text)
    for _ in range(2):
        m = _RE_TITLE_WRAP.match(s)
        if not m:
            break
        s = m.group(1).strip()
    return s


def cjk_ratio(text: str) -> float:
    """汉字占比，用于识别乱码与非中文条目。"""
    if not text:
        return 0.0
    han = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return han / len(text)


# ---------------------------------------------------------------- 版本信息

# 版本修饰词：可以确定性地从书名中剥离，记入 edition 字段。
_EDITION_WORDS = (
    "修订版", "增订版", "新版", "典藏版", "珍藏版", "精装版", "平装版", "图文版",
    "插图版", "彩图版", "注音版", "大字版", "双语版", "英汉对照", "全译版",
    "精装本", "平装本", "特签版", "印特签版", "刷边版", "毛边本", "亲签版",
    "第2版", "第3版", "第4版", "第5版", "第三版", "第四版", "第五版",
)
_RE_EDITION_PAREN = re.compile(
    r"[（(\[【]\s*(" + "|".join(_EDITION_WORDS) + r")\s*[）)\]】]"
)
_RE_EDITION_TAIL = re.compile(
    r"[\s]*(" + "|".join(_EDITION_WORDS) + r")$"
)

# 丛书/系列名：属于书目信息，但不属于书名本体。
_RE_SERIES_PAREN = re.compile(
    r"[（(]\s*([^（()）]{2,30}?(?:系列|丛书|教材|读本|文库|书系|全集))\s*[）)]"
)

_RE_VOLUME = re.compile(
    r"[（(\[【]?\s*(?:全\s*)?([0-9一两二三四五六七八九十百廿]+)\s*[册卷部辑集]\s*[）)\]】]?"
)
_RE_VOLUME_TAIL = re.compile(r"[\s·]*(?:第\s*[0-9一两二三四五六七八九十百]+\s*[册卷部辑集])\s*$")


def extract_edition(text: str) -> tuple[str, str]:
    """剥离括号内版本词与结尾版本词，返回 (正文, 版本描述)。"""
    editions: list[str] = []

    def _take(m: re.Match) -> str:
        editions.append(m.group(1))
        return " "

    out = _RE_EDITION_PAREN.sub(_take, text)
    out = squash(out)
    m = _RE_EDITION_TAIL.search(out)
    if m:
        editions.append(m.group(1))
        out = out[: m.start()].strip()
    return out, "、".join(dict.fromkeys(editions))


def extract_volume(text: str) -> tuple[str, str]:
    """识别「（全三册）」「第一卷」等卷册信息，返回 (正文, 卷册)。"""
    m = _RE_VOLUME.search(text)
    if m and len(m.group(0)) <= len(text) - 1:
        return squash(text.replace(m.group(0), " ")), m.group(0)
    m = _RE_VOLUME_TAIL.search(text)
    if m and m.start() > 0:
        return squash(text[: m.start()]), m.group(0)
    return text, ""


# ---------------------------------------------------------------- 营销噪声

# 电商标题里的卖点词。按「出现即截断」处理，但仅当截断后仍有 >=2 字正文，
# 以免把《正版》这类书名本身误伤。
_PROMO_MARKERS = (
    "正版书籍", "正版图书", "正版现货", "正版包邮", "正版", "当当自营", "当当专享",
    "当当独家", "当当定制", "限量亲签", "限量签名", "限量版", "亲签版", "签名版",
    "印签版", "印特签", "特签版", "刷边版", "印章版", "签章版", "藏书票", "明信片",
    "书签", "海报", "赠品",
    "附赠", "赠送", "包邮", "现货", "全新", "全新正版", "套装", "全店", "旗舰店",
    "自营店", "官方旗舰", "出版社直供", "新华书店", "天猫", "京东", "包发票",
    "速发", "秒杀", "预售", "团购", "批发", "特价", "清仓", "畅销", "好评",
    "网络原名", "全新力作", "重磅新书", "新书首发",
)

_RE_PROMO = re.compile("|".join(re.escape(w) for w in _PROMO_MARKERS))
_RE_PROMO_BRACKET = re.compile(r"[（(【\[]([^）)】\]]{0,40})[）)】\]]")
# 影视/连载类括注：书名里出现即非书名本体
_RE_TIEIN = re.compile(r"(原著|影视|电视剧|电影|同名|番外|周边|全本|完结|连载|广播剧|有声书|外传|前传)")
# 电商标题里的类型词尾巴：「书名 + 悬疑惊悚小说」这类
_RE_GENRE_TAIL = re.compile(
    r"\s+[玄幻武侠都市历史军事青春言情科幻悬疑惊悚恐怖推理爱情仙侠奇幻战争穿越搞笑热血灵异权谋豪门宫斗宅斗年代空间系统]{2,6}小说$"
)

# 超长括号解释（含逗号/句读、且长度 >= 12）几乎都是推荐语而非副标题。
_RE_LONG_PAREN = re.compile(r"[（(]([^（()）]{12,})[）)]")

# 出版社后缀：出现时其后的内容基本可判定为非书名。
_RE_PRESS = re.compile(
    r"(?:[\s,，/]|^)(?:[\u4e00-\u9fff·]{2,15}(?:出版社|出版公司|出版集团|书局|书店|"
    r"印书馆|大学出版社|教育出版社|文艺出版社|少儿出版社|人民出版社|音像出版社))"
)

# 「著者 + 著作方式」：电商标题常写成「书名 张三 著 某出版社」。
_RE_AUTHOR_TAIL = re.compile(
    r"\s([\u4e00-\u9fff·]{2,6}|\[[^\]]{1,8}\][\u4e00-\u9fff·]{0,6})\s*"
    r"(?:等著|等编著|等主编|等译|编著|主编|著|编|译|绘|口述|整理)"
)

# 纯数字化字段（价格、印次、ISBN、开本），出现在标题里即为噪声。
_RE_JUNK = re.compile(
    r"(?:¥|￥|\d+(?:\.\d+)?\s*元|ISBN[\s:：]*[\d\-Xx]{10,17}|"
    r"(?<!\d)97[89]\d{10}(?!\d)|"
    r"\d{4}\s*年\s*\d{1,2}\s*月(?:第\d+次印刷)?|\d{3,4}\s*[开K]本|"
    r"第\s*\d+\s*次印刷|定价[:：]?\s*\d+)"
)


def strip_promo(text: str) -> tuple[str, bool]:
    """剥离营销文本。返回 (正文, 是否发生过截断)。

    策略按可信度排序：先去括号内的卖点，再按卖点词截断，再看「书名 + 一堆人名」
    的推荐语形态，最后按出版社与数字噪声截断。每一步都要求保留至少 2 个字符，
    避免把整条记录清空。
    """
    s = squash(text)
    cut = False

    # 1. 括号内的卖点（如「（当当专享亲签版）」「（同名电视剧原著）」）
    def _bracket(m: re.Match) -> str:
        nonlocal cut
        inner = m.group(1)
        if _RE_PROMO.search(inner) or _RE_JUNK.search(inner) or _RE_TIEIN.search(inner):
            cut = True
            return " "
        return m.group(0)

    s = _RE_PROMO_BRACKET.sub(_bracket, s)

    # 1.5 超长括号解释（推荐语）
    def _long(m: re.Match) -> str:
        nonlocal cut
        inner = m.group(1)
        if re.search(r"[，,。；;！!？?]", inner):
            cut = True
            return " "
        return m.group(0)

    s = _RE_LONG_PAREN.sub(_long, s)

    # 1.7 类型词尾巴：「我是守村人 悬疑惊悚小说」→「我是守村人」
    m = _RE_GENRE_TAIL.search(s)
    if m and m.start() >= 2:
        s, cut = s[: m.start()], True

    # 2. 卖点词截断：只取最早出现、且截断后正文够长的那一处
    positions = [m.start() for m in _RE_PROMO.finditer(s)]
    for pos in positions:
        head = s[:pos].strip(" ,，、/|·-—")
        if len(head) >= 2:
            s, cut = head, True
            break

    # 3. 著者块截断
    m = _RE_AUTHOR_TAIL.search(s)
    if m and m.start() >= 2:
        s, cut = s[: m.start()].strip(" ,，、/|·-—"), True

    # 3.5 「书名 + 推荐人名单」：首段是短书名，其后跟着一长串人名与推荐语。
    #     要求首段至少含 2 个汉字，避免把「Nikon D800 摄影指南」这类外文开头的书名切坏。
    m = re.match(r"^(\S{2,14}) (.+)$", s)
    if m and sum(1 for ch in m.group(1) if "\u4e00" <= ch <= "\u9fff") >= 2:
        if re.search(r"(推荐|著|主编|编著|译|出版社|出品|正版|限量|签名|力荐)", m.group(2)):
            s, cut = m.group(1), True

    # 4. 出版社截断
    m = _RE_PRESS.search(s)
    if m and m.start() >= 2:
        s, cut = s[: m.start()].strip(" ,，、/|·-—"), True

    # 4. 数字噪声截断
    m = _RE_JUNK.search(s)
    if m and m.start() >= 2:
        s, cut = s[: m.start()].strip(), True

    return squash(s), cut


def clean_title(raw: str) -> tuple[str, str, str, float]:
    """把一条原始书名清洗为 (书名, 版本, 卷册, 置信度)。

    置信度含义：1.0 表示未检出营销噪声；0.6 表示做过截断；0.3 表示截断后
    仍残留可疑片段，建议人工复核。导出时保留该字段，供下游按需过滤。
    """
    s = strip_title_wrap(raw)
    s = _RE_SERIES_PAREN.sub(" ", s)          # 先摘掉丛书名，避免干扰后续判断
    s = re.sub(r"\s*[:：]\s*$", "", s)
    s, edition = extract_edition(s)
    s, volume = extract_volume(s)
    s = re.sub(r"[—–]{2,}", "—", s)            # —— 折叠成单个破折号
    s, cut = strip_promo(s)
    s = re.sub(r"\s+(?:等著|等编著|等译|著|编著|主编|编|译|等)$", "", s)
    s = s.strip(" :：,，.。、·—|/\\")
    s = re.sub(r"^[—\-–]+\s*", "", s)
    s = squash(s)

    confidence = 1.0
    if cut:
        confidence = 0.6
    if not s or len(s) > 40:
        confidence = min(confidence, 0.3)
    if _RE_PROMO.search(s) or _RE_JUNK.search(s):
        confidence = min(confidence, 0.3)
    return s, edition, volume, confidence


# ---------------------------------------------------------------- 去重键

_RE_KEY_DROP = re.compile(
    r"[\s·・．.,，。:：;；!！?？\"'“”‘’()（）\[\]【】<>《》〈〉「」『』—–\-~～/\\|*#%&@+_]"
)


def title_key(title: str) -> str:
    """生成用于精确去重的书名键：去标点、去空白、小写。

    保留汉字与拉丁字母数字，其余一律丢弃 —— 标点在中文书名里几乎不承载语义，
    却是同一本书在不同站点间最主要的差异来源。
    """
    s = squash(title)
    s = _RE_KEY_DROP.sub("", s)
    return s.lower()


def is_strong_key(key: str) -> bool:
    """单字书名（如《家》《春》《秋》）混淆率极高，不参与标题级合并。"""
    return len(key) >= 2


# ---------------------------------------------------------------- 著者

_AUTHOR_ROLE = re.compile(
    r"[（(][^）)]{0,12}[）)]|"
    r"(?:等著|等编著|等主编|等译|等编|著|编著|主编|编选|编|译|校注|校点|注疏|笺注|"
    r"整理|辑注|辑校|撰|修|纂|口述|绘|摄影|改编|编译|审校|责任编辑)$"
)
_RE_DATE = re.compile(r"\d{4}[-/年]\d{1,2}|^\d{4}$")


def clean_author(raw: str) -> str:
    """清洗著者字段，返回空串表示无法确定。"""
    s = squash(raw)
    if not s:
        return ""
    if s in {"无", "不详", "佚名", "未知", "匿名", "—", "-", "/"}:
        return "佚名" if s == "佚名" else ""
    if _RE_DATE.search(s):
        return ""
    s = _AUTHOR_ROLE.sub("", s).strip(" ,，、/·")
    s = re.sub(r"^[\[(（]?[^\]]{1,4}[\]）)]?\s*", "", s) if re.match(r"^[\[(（][A-Za-z\u4e00-\u9fff]{1,4}[\]）)]", s) else s
    return s.strip()


# ---------------------------------------------------------------- ISBN

def isbn13(raw: str) -> str:
    """校验并归一化 ISBN-13；不是合法 ISBN 时返回空串。

    ISBN-10 转 13 位时必须**重算**校验位 —— 10 位用的是 mod 11、末位可能是 X，
    直接拼 ``978`` 前缀会把校验位带错。
    """
    digits = re.sub(r"[^0-9Xx]", "", squash(raw)).upper()

    if len(digits) == 10:
        if not digits[:9].isdigit():
            return ""
        total = sum((10 - i) * int(d) for i, d in enumerate(digits[:9]))
        check = (11 - total % 11) % 11
        if check == 10:
            check_digit = "X"
        else:
            check_digit = str(check)
        if digits[9] != check_digit:
            return ""
        digits = "978" + digits[:9]
        body = digits
        total13 = sum((1 if i % 2 == 0 else 3) * int(d) for i, d in enumerate(body))
        return body + str((10 - total13 % 10) % 10)

    if len(digits) != 13 or not digits.isdigit():
        return ""
    total = sum((1 if i % 2 == 0 else 3) * int(d) for i, d in enumerate(digits[:12]))
    if (10 - total % 10) % 10 != int(digits[12]):
        return ""
    return digits


def has_tail_noise(text: str) -> bool:
    """原始标题里是否含有可判定为「书名之外的附加信息」的片段。"""
    return bool(
        _RE_PROMO.search(text) or _RE_PRESS.search(text) or _RE_JUNK.search(text)
    )


def pub_year(raw: str) -> str:
    """从日期串中提取四位年份。"""
    m = re.search(r"(1[89]\d{2}|20\d{2})", squash(raw))
    return m.group(1) if m else ""
