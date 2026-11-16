"""Convert timing candidates into local Gregorian intervals."""

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .calendar import (TERM_DATA_VERSION, day_hour_pillars, describe_term,
                       require_term_source, solar_term, year_month_pillars)
from .provenance import SCHEMA_VERSION, calendar_dependency, collect_term

UTC = timezone.utc
MAX_DAYS = {"hour": 31, "day": 370, "month": 3660, "year": 36600}


def wall_boundaries(start, end, zone, unit):
    first_day = start.astimezone(zone).date() - timedelta(days=1)
    last_day = end.astimezone(zone).date() + timedelta(days=1)
    hours = (23,) if unit == "day" else range(1, 24, 2)
    boundaries = set()
    for offset in range((last_day - first_day).days + 1):
        date = first_day + timedelta(days=offset)
        for hour in hours:
            wall = datetime.combine(date, time(hour))
            for fold in (0, 1):
                instant = wall.replace(tzinfo=zone, fold=fold).astimezone(UTC)
                if start < instant < end and instant.astimezone(zone).replace(tzinfo=None) == wall:
                    boundaries.add(instant)

    # A clock change can skip a boundary or move the clock into a different pillar.
    left = int(start.timestamp())
    limit = int(end.timestamp())
    while left < limit:
        right = min(left + 21600, limit)
        previous = datetime.fromtimestamp(left, zone).utcoffset()
        if previous != datetime.fromtimestamp(right, zone).utcoffset():
            low, high = left, right
            while high - low > 1:
                mid = (low + high) // 2
                if datetime.fromtimestamp(mid, zone).utcoffset() == previous:
                    low = mid
                else:
                    high = mid
            transition = datetime.fromtimestamp(high, UTC)
            if start < transition < end:
                boundaries.add(transition)
        left = right
    return sorted(boundaries)


def term_boundaries(start, end, unit, allow_estimated_terms, sources, *, term_records=None,
                     require_second_precision=False, accept_minute_boundaries=False):
    cursor = start
    while True:
        term = solar_term(cursor, following=True, jie_only=True)
        name, boundary, source = term
        instant = boundary.astimezone(UTC)
        if instant >= end:
            return
        if unit == "month" or name == "立春":
            policy = {"allow_estimated_terms": allow_estimated_terms,
                      "require_second_precision": require_second_precision,
                      "accept_minute_boundaries": accept_minute_boundaries}
            require_term_source(term, **policy)
            if term_records is not None:
                collect_term(term_records, describe_term(term, **policy))
            if sources is not None:
                sources.add(source)
            yield instant
        cursor = instant


def pillar_at(instant, zone, unit, allow_estimated_terms, *, term_records=None,
               require_second_precision=False, accept_minute_boundaries=False):
    if unit in ("day", "hour"):
        day, hour = day_hour_pillars(instant.astimezone(zone))
        return day if unit == "day" else hour
    year, month = year_month_pillars(instant, allow_estimated_terms=allow_estimated_terms,
                                    term_records=term_records,
                                    require_second_precision=require_second_precision,
                                    accept_minute_boundaries=accept_minute_boundaries)
    return year if unit == "year" else month


def resolve_windows(timing, start, end, zone, *, allow_estimated_terms=False, term_sources=None,
                     term_records=None, require_second_precision=False, accept_minute_boundaries=False):
    """Return matching intervals clipped to the requested search range."""
    unit = timing.get("unit")
    if unit not in MAX_DAYS:
        raise ValueError("换算公历时段须指定年、月、日或时")
    if any(value.tzinfo is None or value.utcoffset() is None for value in (start, end)):
        raise ValueError("起止时间须包含时区；请先用 local_clock 解析当地时间")
    start, end = start.astimezone(UTC), end.astimezone(UTC)
    if not timedelta(0) < end - start <= timedelta(days=MAX_DAYS[unit]):
        raise ValueError(f"截止时间须晚于查询开始时间，且最多相隔 {MAX_DAYS[unit]} 天")
    candidates = timing["candidates"] + [
        item for item in timing.get("secondary_candidates", []) if item["unit"] == unit
    ]
    if not candidates:
        return []
    if unit in ("day", "hour"):
        boundaries = wall_boundaries(start, end, zone, unit)
    else:
        if term_sources is not None:
            term_sources.add(solar_term(start, jie_only=True)[2])
        boundaries = term_boundaries(start, end, unit, allow_estimated_terms, term_sources,
                                     term_records=term_records,
                                     require_second_precision=require_second_precision,
                                     accept_minute_boundaries=accept_minute_boundaries)
    cuts = [start, *boundaries, end]
    matches = []
    for left, right in zip(cuts, cuts[1:]):
        pillar = pillar_at(left, zone, unit, allow_estimated_terms, term_records=term_records,
                           require_second_precision=require_second_precision,
                           accept_minute_boundaries=accept_minute_boundaries)
        rules = list(dict.fromkeys(
            item["rule"] for item in candidates
            if (item["pillar"] == pillar if "pillar" in item else item["branch"] == pillar[1])
        ))
        if not rules:
            continue
        local_end = right.astimezone(zone).isoformat()
        if matches and matches[-1]["pillar"] == pillar and matches[-1]["end"] == left.astimezone(zone).isoformat():
            matches[-1]["end"] = local_end
        else:
            matches.append({"pillar": pillar, "start": left.astimezone(zone).isoformat(),
                            "end": local_end, "rules": rules})
    return matches


def resolve_windows_report(timing, start, end, zone, *, allow_estimated_terms=False,
                            term_sources=None, require_second_precision=False,
                            accept_minute_boundaries=False):
    """Add source evidence without changing the legacy list-returning interface."""
    records = []
    windows = resolve_windows(timing, start, end, zone, allow_estimated_terms=allow_estimated_terms,
                              term_sources=term_sources, term_records=records,
                              require_second_precision=require_second_precision,
                              accept_minute_boundaries=accept_minute_boundaries)
    has_candidates = bool(timing["candidates"] or any(
        item["unit"] == timing["unit"] for item in timing.get("secondary_candidates", [])))
    dependency_uses = (("day_pillar",) if timing["unit"] in ("day", "hour")
                       else ("adjacent_term_candidates",)) if has_candidates else ()
    return {"windows": windows, "provenance": {
        "schema_version": SCHEMA_VERSION, "method": "candidate_pillar_interval_match",
        "unit": timing["unit"], "search_range": {"start": start.isoformat(), "end": end.isoformat()},
        "term_data_version": TERM_DATA_VERSION, "term_records": records,
        "calendar_dependency": calendar_dependency(dependency_uses),
        "precision": {"interval_convention": "start_inclusive_end_exclusive",
                      "accuracy_bound_seconds": None},
        "validation": {"status": "partial_regression_tests", "validated_year_range": None,
                       "note": "区间匹配测试不证明时段预测准确性。"},
        "usage": {"status": "ready", "estimated": any(r["usage"]["estimated"] for r in records),
                  "limitations": ["区间只匹配输入候选，不是已确定的事件发生时间或概率。",
                                   "空列表表示范围内无匹配候选，不能据此断定事件不会发生。"]},
    }}


def calendar_zone(calendar):
    if calendar["timezone"]:
        return ZoneInfo(calendar["timezone"])
    return datetime.fromisoformat(calendar["local_time"]).tzinfo
