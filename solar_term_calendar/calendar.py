"""Civil-clock conversion and official-first solar-term selection."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from zoneinfo import ZoneInfo

from .constants import BRANCHES, CYCLE, STEMS
from .pmo_terms import JIE_MONTH, OFFICIAL_TERMS, UPDATES
from .hko_terms import HKO_TERMS
from .provenance import (ResultConfirmationRequired, SCHEMA_VERSION, calendar_dependency,
                         collect_term, term_evidence)

BEIJING = timezone(timedelta(hours=8))


TERM_DATA_VERSION = sha256(json.dumps({
    "pmo": [(year, name, value.isoformat()) for (year, name), value in sorted(OFFICIAL_TERMS.items())],
    "hko": [(year, name, value.isoformat()) for (year, name), value in sorted(HKO_TERMS.items())],
    "publications": UPDATES,
}, sort_keys=True).encode("utf-8")).hexdigest()


def local_clock(timestamp, source_zone=None):
    if timestamp == "now":
        return datetime.now(ZoneInfo(source_zone)) if source_zone else datetime.now().astimezone()
    if "T" not in timestamp and " " not in timestamp:
        raise ValueError("请输入完整的 ISO 时间，包含时分")
    instant = datetime.fromisoformat(timestamp)
    if instant.tzinfo is None:
        if source_zone is None:
            raise ValueError("没有 UTC 偏移量时，须提供 --timezone")
        zone = ZoneInfo(source_zone)
        first = instant.replace(tzinfo=zone, fold=0)
        second = instant.replace(tzinfo=zone, fold=1)
        if first.utcoffset() != second.utcoffset():
            raise ValueError("当地时间在夏令时切换附近，请提供含明确 UTC 偏移量的时间")
        instant = first
    elif source_zone is not None:
        raise ValueError("UTC 偏移量和 --timezone 请选择一种")
    return instant


def lunar_at(clock):
    try:
        from lunar_python import Solar
    except ModuleNotFoundError as exc:
        raise ValueError('公历换算需要安装日历依赖：python -m pip install ".[calendar]"') from exc
    return Solar.fromYmdHms(clock.year, clock.month, clock.day,
                           clock.hour, clock.minute, clock.second).getLunar()


def day_hour_pillars(moment):
    day = lunar_at(moment).getDayInGanZhiExact()  # 本地钟表 23:00 换干支日
    branch_index = ((moment.hour + 1) // 2) % 12
    stem_index = (STEMS.index(day[0]) * 2 + branch_index) % 10
    return day, STEMS[stem_index] + BRANCHES[branch_index]


def term_instant(term):
    return datetime.fromisoformat(term.getSolar().toYmdHms()).replace(tzinfo=BEIJING)


def solar_term(moment, *, following=False, jie_only=False):
    """Return name, operational boundary and source in chronological order."""
    clock = moment.astimezone(BEIJING)
    lunar = lunar_at(clock)
    prev = "getPrevJie" if jie_only else "getPrevJieQi"
    nxt = "getNextJie" if jie_only else "getNextJieQi"

    def get_term(cal, method):
        term = getattr(cal, method)(False)
        raw = term_instant(term)
        name = term.getName()
        key = raw.year, name
        if key in OFFICIAL_TERMS:
            return name, OFFICIAL_TERMS[key], "pmo", raw
        if key in HKO_TERMS:
            return name, HKO_TERMS[key], "hko", raw
        return name, raw, "lunar-python", raw

    previous = get_term(lunar, prev)
    upcoming = get_term(lunar, nxt)
    if following:
        if previous[1] > clock:
            return previous[:3]
        if upcoming[1] <= clock:
            upcoming = get_term(lunar_at(upcoming[3]), nxt)
        return upcoming[:3]
    if upcoming[1] <= clock:
        return upcoming[:3]
    if previous[1] > clock:
        previous = get_term(lunar_at(previous[3] - timedelta(seconds=1)), prev)
    return previous[:3]


class EstimatedTermConsentRequired(ResultConfirmationRequired):
    code = "estimated_term_consent_required"

    def __init__(self, term, year, evidence=None):
        self.term = term
        self.year = year
        self.evidence = evidence or {"name": term, "year": year}
        super().__init__(f"{year} 年{term}缺少已录入的紫金山天文台和香港天文台交节资料。"
                         "是否接受使用 lunar-python 的估算时刻？")


class TermPrecisionConsentRequired(ResultConfirmationRequired):
    code = "term_precision_consent_required"

    def __init__(self, evidence):
        self.evidence = evidence
        super().__init__(f"{evidence['name']}的官方资料仅公布到分钟，不能保证秒级边界。"
                         "是否接受从公布分钟起点切换，或提供更细的官方资料？")


def describe_term(term, display_zone=None, *, allow_estimated_terms=False,
                  require_second_precision=False, accept_minute_boundaries=False):
    return term_evidence(term, official_terms=OFFICIAL_TERMS, hko_terms=HKO_TERMS,
                         data_version=TERM_DATA_VERSION, display_zone=display_zone,
                         allow_estimated_terms=allow_estimated_terms,
                         require_second_precision=require_second_precision,
                         accept_minute_boundaries=accept_minute_boundaries)


def require_term_source(term, allow_estimated_terms, *, require_second_precision=False,
                        accept_minute_boundaries=False):
    name, boundary, source = term
    if source == "lunar-python" and not allow_estimated_terms:
        raise EstimatedTermConsentRequired(name, boundary.year, describe_term(
            term, require_second_precision=require_second_precision))
    if source != "lunar-python" and require_second_precision and not accept_minute_boundaries:
        raise TermPrecisionConsentRequired(describe_term(term, require_second_precision=True))


def year_month_pillars(moment, *, allow_estimated_terms=False, require_second_precision=False,
                       accept_minute_boundaries=False, term_records=None):
    term = solar_term(moment, jie_only=True)
    policy = {"allow_estimated_terms": allow_estimated_terms,
              "require_second_precision": require_second_precision,
              "accept_minute_boundaries": accept_minute_boundaries}
    require_term_source(term, **policy)
    if term_records is not None:
        collect_term(term_records, describe_term(term, moment.tzinfo, **policy))
    jie, start, _ = term
    month = JIE_MONTH[jie]
    year = start.year - (month == 1)
    year_pillar = CYCLE[(year - 1984) % 60]
    month_offset = (month - 2) % 12
    month_stem = STEMS[(2 * STEMS.index(year_pillar[0]) + 2 + month_offset) % 10]
    return year_pillar, month_stem + BRANCHES[(month_offset + 2) % 12]
