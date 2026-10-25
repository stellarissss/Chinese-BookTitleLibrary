from .dangdang import Dangdang
from .douban import Douban
from .weread import Weread

__all__ = ["Dangdang", "Douban", "Weread"]

# PDC 需要账号（CNBOOK_PDC_COOKIE），默认不注册进命令行，按需手动引入。
REGISTRY = {
    "dangdang": Dangdang,
    "douban": Douban,
    "weread": Weread,
}
