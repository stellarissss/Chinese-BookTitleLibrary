"""归一化与去重的回归测试。

这些用例锁定了几条容易在重构中被破坏的行为，尤其是「不能误合并」的那几条。
运行：``python -m pytest tests -q``
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cnbook import quality, textnorm as tn
from cnbook.dedup import clean_record
from cnbook.lexicon import TitleLexicon


# ---------------------------------------------------------------- 书名清洗

def test_strip_marketing_tail():
    assert tn.clean_title("菊与刀（你真的了解日本吗？全新典雅版，附赠浮世绘）")[0] == "菊与刀"


def test_strip_author_and_press():
    assert tn.clean_title("舞蹈理论概念手册 袁禾编著 上海音乐出版社")[0] == "舞蹈理论概念手册"
    assert tn.clean_title("舞弊审计实务指南 人民邮电出版社")[0] == "舞弊审计实务指南"


def test_keep_legit_brackets():
    # 短括号是副标题，不能删
    title, _, _, _ = tn.clean_title("乡土中国（生育制度）")
    assert "生育制度" in title


def test_edition_extracted_not_deleted():
    title, edition, _, _ = tn.clean_title("有闲阶级论（精装本）")
    assert title == "有闲阶级论"
    assert edition == "精装本"


def test_volume_extracted():
    title, _, volume, _ = tn.clean_title("红楼梦（全二册）")
    assert title == "红楼梦"
    assert "全二册" in volume


def test_chinese_punctuation_preserved():
    # NFKC 会把「，：（）」压成半角，中文书名里这是错的
    assert tn.squash("人类简史：从动物到上帝") == "人类简史：从动物到上帝"
    assert tn.squash("ＡＢＣ１２３") == "ABC123"


def test_title_key_ignores_punctuation():
    assert tn.title_key("红楼梦：又名石头记") == "红楼梦又名石头记"
    assert tn.title_key("The  Great Gatsby") == "thegreatgatsby"


# ---------------------------------------------------------------- 著者

def test_author_role_stripped():
    assert tn.clean_author("曹雪芹 著") == "曹雪芹"
    assert tn.clean_author("余华著") == "余华"


def test_author_junk_rejected():
    assert tn.clean_author("2016-09-01") == ""
    assert tn.clean_author("无") == ""


# ---------------------------------------------------------------- ISBN

def test_isbn13_checksum():
    assert tn.isbn13("978-7-02-000220-7") == "9787020002207"
    assert tn.isbn13("0306406152") == "9780306406157"   # 10 位升 13 位
    assert tn.isbn13("9787020002208") == ""             # 校验位错误
    assert tn.isbn13("0306406153") == ""                # 10 位校验位错误


# ---------------------------------------------------------------- 质量门

def test_non_book_rejected():
    assert quality.is_book("55吋触控萤幕会议平板智能办公设备")[0] is False
    assert quality.is_book("红楼梦")[0] is True


def test_english_only_rejected():
    assert quality.is_book("Quantitative Investment Analysis")[0] is False


# ---------------------------------------------------------------- 词典切分

def test_lexicon_longest_prefix():
    lex = TitleLexicon(["红楼梦", "红楼梦新证"])
    assert lex.match("红楼梦（全二册）当当自营") == "红楼梦"
    assert lex.match("红楼梦新证 周汝昌 著") == "红楼梦新证"


# ---------------------------------------------------------------- 不误合并

def test_clean_record_keeps_distinct_titles():
    lex = TitleLexicon(["西游记"])
    row = (1, "dangdang", "x", "西游记续 著", "", "", "", "", "")
    cand, _ = clean_record(row, lex)
    assert cand is not None
    assert cand.key == tn.title_key("西游记续")   # 不能被《西游记》吞掉


def test_clean_record_single_char_dropped():
    row = (1, "dangdang", "x", "家", "", "", "", "", "")
    cand, reason = clean_record(row, None)
    assert cand is None and reason == "single_char"
