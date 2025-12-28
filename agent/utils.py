import re
from typing import Optional, Tuple

# 小时转换为分钟数
def parse_time_to_minutes(raw: str) -> Optional[int]:
    value = raw.strip().lower()
    match_12h = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*([ap]m)$", value)
    if match_12h:
        hour = int(match_12h.group(1))
        minute = int(match_12h.group(2) or 0)
        meridiem = match_12h.group(3)
        if hour == 12:
            hour = 0
        if meridiem == "pm":
            hour += 12
        return hour * 60 + minute

    match_24h = re.match(r"^(\d{1,2}):(\d{2})$", value)
    if match_24h:
        hour = int(match_24h.group(1))
        minute = int(match_24h.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour * 60 + minute
    return None

# 中文字符转换为分钟数
def parse_localized_time(prefix: str, hour: int, minute: int) -> Optional[int]:
    meridiem = prefix.strip()
    if meridiem in ("上午", "凌晨"):
        if hour == 12:
            hour = 0
    elif meridiem in ("下午", "晚上", "中午"):
        if hour != 12:
            hour += 12
    else:
        return None
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour * 60 + minute
    return None

# 从文本中提取时间范围，返回开始和结束的分钟数
def extract_time_range(text: str) -> Optional[Tuple[int, int]]:
    normalized = text.lower().replace("\u2013", "-").replace("\u2014", "-")
    if "all day" in normalized or "全天" in text:
        return 0, 24 * 60

    match = re.search(
        r"(\d{1,2}(?::\d{2})?\s*[ap]m|\d{1,2}:\d{2})\s*(?:-|\bto\b)\s*(\d{1,2}(?::\d{2})?\s*[ap]m|\d{1,2}:\d{2})",
        normalized,
    )
    if match:
        start = parse_time_to_minutes(match.group(1))
        end = parse_time_to_minutes(match.group(2))
        if start is not None and end is not None:
            return start, end

    match_local = re.search(
        r"(上午|下午|晚上|中午|凌晨)\s*(\d{1,2}):(\d{2})\s*-\s*(上午|下午|晚上|中午|凌晨)\s*(\d{1,2}):(\d{2})",
        text,
    )
    if match_local:
        start = parse_localized_time(match_local.group(1), int(match_local.group(2)), int(match_local.group(3)))
        end = parse_localized_time(match_local.group(4), int(match_local.group(5)), int(match_local.group(6)))
        if start is not None and end is not None:
            return start, end

    match_local_single = re.search(
        r"(上午|下午|晚上|中午|凌晨)\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})",
        text,
    )
    if match_local_single:
        start = parse_localized_time(match_local_single.group(1), int(match_local_single.group(2)), int(match_local_single.group(3)))
        if start is None:
            return None
        end = parse_time_to_minutes(f"{match_local_single.group(4)}:{match_local_single.group(5)}")
        if end is not None:
            return start, end

    return None