"""Sprite Studio 코어 — UI 와 무관한 스프라이트 처리 로직.

tkinter 에 의존하지 않으므로 데스크톱 앱과 웹(Pyodide) 이 같은 코드를
공유한다. 파일 시스템을 쓰는 함수는 `atlas.parse_atlas_file` 과
`atlas.find_sibling_atlas` 뿐이고, 둘 다 내용만 받는 짝이 따로 있다.
"""

from .constants import ATLAS_EXTS, BORDER, IMAGE_EXTS
from .i18n import (
    FONTS,
    LANG_CODES,
    LANG_NAMES,
    TRANSLATIONS,
    set_lang,
    t,
)
from .detect import (
    bboxes_from_labels,
    build_mask,
    crop_sprites,
    detect_boxes,
    dilate,
    label_components,
    sort_reading_order,
)
from .packing import (
    auto_width,
    find_overlaps,
    grid_positions,
    next_pot,
    pack_shelf,
)
from .atlas import (
    extract_atlas_frame,
    find_sibling_atlas,
    parse_atlas_data,
    parse_atlas_file,
    parse_cocos_plist,
    parse_libgdx_atlas,
    parse_own_json,
    parse_sparrow_xml,
    parse_texturepacker_json,
)
from .util import make_checker, safe_name

__all__ = [
    "ATLAS_EXTS", "BORDER", "IMAGE_EXTS",
    "FONTS", "LANG_CODES", "LANG_NAMES", "TRANSLATIONS", "set_lang", "t",
    "bboxes_from_labels", "build_mask", "crop_sprites", "detect_boxes",
    "dilate", "label_components", "sort_reading_order",
    "auto_width", "find_overlaps", "grid_positions", "next_pot", "pack_shelf",
    "extract_atlas_frame", "find_sibling_atlas", "parse_atlas_data",
    "parse_atlas_file", "parse_cocos_plist", "parse_libgdx_atlas",
    "parse_own_json", "parse_sparrow_xml", "parse_texturepacker_json",
    "make_checker", "safe_name",
]
