"""자잘한 공용 도구."""

import re


def safe_name(text, fallback="sprite"):
    """파일/폴더 이름으로 쓸 수 있게 정리."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text).strip(" .")
    return cleaned[:40] or fallback

