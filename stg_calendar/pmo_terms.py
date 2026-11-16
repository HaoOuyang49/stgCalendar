"""Minute-resolution solar terms from the PMO annual calendar PDFs."""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from os import environ
from urllib.parse import urlsplit

from .pmo_historical import HISTORICAL_TIMES

# 2022: https://pmo.cas.cn/xwdt2019/kpdt2019/202203/P020240201504886742716.pdf
# 2023: https://pmo.cas.cn/xwdt2019/kpdt2019/202203/P020240201504887882408.pdf
# 2024: https://pmo.cas.cn/xwdt2019/kpdt2019/202203/P020240201504888053250.pdf
# 2025: https://pmo.cas.cn/xwdt2019/kpdt2019/202203/P020241223526694003756.pdf
# 2026: https://pmo.cas.cn/xwdt2019/kpdt2019/202203/P020251230620718707826.pdf
MONTH_TERMS = (
    ("小寒", "大寒"), ("立春", "雨水"), ("惊蛰", "春分"), ("清明", "谷雨"),
    ("立夏", "小满"), ("芒种", "夏至"), ("小暑", "大暑"), ("立秋", "处暑"),
    ("白露", "秋分"), ("寒露", "霜降"), ("立冬", "小雪"), ("大雪", "冬至"),
)
YEAR_TIMES = {
    2022: (
        "05 17:14 20 10:39", "04 04:51 19 00:43", "05 22:44 20 23:33",
        "05 03:20 20 10:24", "05 20:26 21 09:23", "06 00:26 21 17:14",
        "07 10:38 23 04:07", "07 20:29 23 11:16", "07 23:32 23 09:04",
        "08 15:22 23 18:36", "07 18:45 22 16:20", "07 11:46 22 05:48",
    ),
    2023: (
        "05 23:05 20 16:30", "04 10:43 19 06:34", "06 04:36 21 05:24",
        "05 09:13 20 16:14", "06 02:19 21 15:09", "06 06:18 21 22:58",
        "07 16:31 23 09:50", "08 02:23 23 17:01", "08 05:27 23 14:50",
        "08 21:16 24 00:21", "08 00:36 22 22:03", "07 17:33 22 11:27",
    ),
    2024: (
        "06 04:49 20 22:07", "04 16:27 19 12:13", "05 10:23 20 11:06",
        "04 15:02 19 22:00", "05 08:10 20 21:00", "05 12:10 21 04:51",
        "06 22:20 22 15:44", "07 08:09 22 22:55", "07 11:11 22 20:44",
        "08 03:00 23 06:15", "07 06:20 22 03:56", "06 23:17 21 17:21",
    ),
    2025: (
        "05 10:33 20 04:00", "03 22:10 18 18:07", "05 16:07 20 17:01",
        "04 20:49 20 03:56", "05 13:57 21 02:55", "05 17:57 21 10:42",
        "07 04:05 22 21:29", "07 13:52 23 04:34", "07 16:52 23 02:19",
        "08 08:41 23 11:51", "07 12:04 22 09:36", "07 05:05 21 23:03",
    ),
    2026: (
        "05 16:23 20 09:45", "04 04:02 18 23:52", "05 21:59 20 22:46",
        "05 02:40 20 09:39", "05 19:49 21 08:37", "05 23:48 21 16:25",
        "07 09:57 23 03:13", "07 19:43 23 10:19", "07 22:41 23 08:05",
        "08 14:29 23 17:38", "07 17:52 22 15:23", "07 10:53 22 04:50",
    ),
    # January and February 2027 appear at the end of the 2026 calendar.
    2027: ("05 22:10 20 15:30", "04 09:46 19 05:33"),
}

# These identify the publications actually transcribed, not their accuracy bounds.
ANNUAL_PUBLICATIONS = {
    2022: "https://pmo.cas.cn/xwdt2019/kpdt2019/202203/P020240201504886742716.pdf",
    2023: "https://pmo.cas.cn/xwdt2019/kpdt2019/202203/P020240201504887882408.pdf",
    2024: "https://pmo.cas.cn/xwdt2019/kpdt2019/202203/P020240201504888053250.pdf",
    2025: "https://pmo.cas.cn/xwdt2019/kpdt2019/202203/P020241223526694003756.pdf",
    2026: "https://pmo.cas.cn/xwdt2019/kpdt2019/202203/P020251230620718707826.pdf",
}
HISTORICAL_PUBLICATION = "https://pmo.cas.cn/xwdt2019/kpdt2019/202203/P020250414456381274062.pdf"


def publication_for(year):
    """Match the same update > annual > historical precedence as the term table."""
    if str(year) in UPDATES:
        document = UPDATES[str(year)]
        return {"title": document["publication"], "url": document["source_url"],
                "edition": document["publication"], "kind": "reviewed_annual_update"}
    if year in YEAR_TIMES:
        edition = 2026 if year == 2027 else year
        return {"title": f"{edition}年日历资料", "url": ANNUAL_PUBLICATIONS[edition],
                "edition": str(edition), "kind": "annual_calendar"}
    return {"title": "1900–2025年日历", "url": HISTORICAL_PUBLICATION,
            "edition": "1900–2025", "kind": "historical_calendar"}


def parse_terms(year_times):
    result = {}
    for year, months in year_times.items():
        for month, (names, values) in enumerate(zip(MONTH_TERMS, months), 1):
            day1, time1, day2, time2 = values.split()
            for name, day, clock in zip(names, (day1, day2), (time1, time2)):
                result[year, name] = datetime.fromisoformat(f"{year}-{month:02d}-{day}T{clock}+08:00")
    return result


def historical_terms():
    result = {}
    for year, row in HISTORICAL_TIMES.items():
        for index, (name, value) in enumerate(zip(
            (name for pair in MONTH_TERMS for name in pair), row.split(), strict=True
        )):
            month = index // 2 + 1
            result[year, name] = datetime.fromisoformat(
                f"{year}-{month:02d}-{value[:2]}T{value[2:4]}:{value[4:]}+08:00"
            )
    return result


UPDATE_FILE = Path(environ.get("STG_CALENDAR_UPDATES", Path(__file__).with_name("pmo_updates.json")))
JIE_MONTH = {pair[0]: month for month, pair in enumerate(MONTH_TERMS, 1)}
TERM_MONTH = {name: month for month, pair in enumerate(MONTH_TERMS, 1) for name in pair}


def parse_annual_update(year, document):
    if not isinstance(document, dict):
        raise ValueError("年表须为 JSON 对象")
    url = document.get("source_url")
    parts = urlsplit(url if isinstance(url, str) else "")
    if parts.scheme != "https" or parts.netloc not in {"pmo.cas.cn", "www.pmo.cas.cn"}:
        raise ValueError("source_url 须指向紫金山天文台官网")
    version = document.get("publication")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("请填写 publication（资料标题及发布版本）")
    times = document.get("terms")
    if not isinstance(times, dict) or times.keys() != TERM_MONTH.keys():
        raise ValueError("完整年表须包含全部 24 个节气，名称不得重复")
    result = {}
    previous = None
    for name, month in TERM_MONTH.items():
        value = times[name]
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}\+08:00", value):
            raise ValueError(f"{name}须用 YYYY-MM-DDTHH:MM+08:00 格式")
        instant = datetime.fromisoformat(value)
        if (instant.year, instant.month) != (year, month):
            raise ValueError(f"{name}年份或月份不符")
        if previous is not None and not timedelta(days=10) < instant - previous < timedelta(days=20):
            raise ValueError(f"{name}与前一个节气的间隔异常")
        result[year, name] = instant
        previous = instant
    return result


def load_updates():
    if not UPDATE_FILE.exists():
        return {}
    return json.loads(UPDATE_FILE.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"JSON 键重复：{key}")
        result[key] = value
    return result


UPDATES = load_updates()
# Prefer dedicated annual publications, then reviewed updates, for overlapping terms.
OFFICIAL_TERMS = historical_terms() | parse_terms(YEAR_TIMES)
for year, document in UPDATES.items():
    OFFICIAL_TERMS.update(parse_annual_update(int(year), document))
