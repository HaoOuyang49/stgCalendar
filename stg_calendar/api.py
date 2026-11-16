"""Public calendar APIs, independent of charts, readings and private textbooks."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import calendar as cal
from .pmo_terms import TERM_MONTH
from .provenance import SCHEMA_VERSION, calendar_dependency, package_version


def _year(year):
    if type(year) is not int or not 1 <= year <= 9998:
        raise ValueError("year须为1至9998的整数；跨年查找需要保留下一年")
    return year


def _missing_term(year, name, require_second_precision):
    return cal.EstimatedTermConsentRequired(name, year, {
        "schema_version": SCHEMA_VERSION, "name": name, "year": year, "time": None,
        "source": {"provider": "lunar-python", "kind": "third_party_estimate",
                   "algorithm_version": package_version("lunar-python"),
                   "data_version": cal.TERM_DATA_VERSION},
        "method": "estimate_not_computed", "data_coverage": None,
        "precision": {"published_resolution": None, "computed_resolution": None,
                      "accuracy_bound_seconds": None,
                      "requested_resolution": "second" if require_second_precision else "minute"},
        "validation": {"status": "accuracy_not_established", "validated_year_range": None},
        "usage": {"status": "needs_confirmation", "can_use": False, "estimated": True,
                  "requires_user_consent": True, "confirmations": [{
                      "code": "estimated_terms", "field": "allow_estimated_terms", "status": "pending",
                      "question": f"{year}年{name}缺少已录入的官方资料，是否接受lunar-python估算？",
                      "choices": ["accept_estimate", "provide_official_data"]}],
                  "limitations": ["尚未执行估算；即使计算到秒，也不代表误差小于一秒。"]},
    })


def get_term(year, name, source_zone=None, *, allow_estimated_terms=False,
             require_second_precision=False, accept_minute_boundaries=False):
    """One term in its Beijing-calendar year. Official lookups need no lunar library."""
    _year(year)
    if name not in TERM_MONTH:
        raise ValueError(f"未知节气：{name}")
    zone = ZoneInfo(source_zone) if source_zone else cal.BEIJING
    key = year, name
    if key in cal.OFFICIAL_TERMS:
        term = name, cal.OFFICIAL_TERMS[key], "pmo"
    elif key in cal.HKO_TERMS:
        term = name, cal.HKO_TERMS[key], "hko"
    else:
        if not allow_estimated_terms:
            raise _missing_term(year, name, require_second_precision)
        # Each calendar month contains two terms; find the requested one explicitly.
        cursor = datetime(year, TERM_MONTH[name], 1, tzinfo=cal.BEIJING)
        term = cal.solar_term(cursor, following=True)
        if term[0] != name:
            term = cal.solar_term(term[1] + timedelta(days=1), following=True)
        if term[0] != name or term[1].year != year:
            raise ValueError("历算依赖未返回所请求年份和名称的节气")
    policy = {"allow_estimated_terms": allow_estimated_terms,
              "require_second_precision": require_second_precision,
              "accept_minute_boundaries": accept_minute_boundaries}
    cal.require_term_source(term, **policy)
    return cal.describe_term(term, zone, **policy)


def terms_for_year(year, source_zone=None, **policy):
    """Return all 24 terms or a confirmation request; never silently fill gaps."""
    terms = [get_term(year, name, source_zone, **policy) for name in TERM_MONTH]
    return {"schema_version": SCHEMA_VERSION, "year": year, "year_basis": "Beijing calendar year",
            "terms": terms, "term_data_version": cal.TERM_DATA_VERSION,
            "usage": {"status": "ready", "complete": len(terms) == 24,
                      "estimated": any(item["usage"]["estimated"] for item in terms)}}


def calendar_at(timestamp, source_zone=None, *, allow_estimated_terms=False,
                require_second_precision=False, accept_minute_boundaries=False):
    """Gregorian local civil time to pillars and term evidence, using 23:00 rollover."""
    moment = cal.local_clock(timestamp, source_zone)
    day, hour = cal.day_hour_pillars(moment)
    policy = {"allow_estimated_terms": allow_estimated_terms,
              "require_second_precision": require_second_precision,
              "accept_minute_boundaries": accept_minute_boundaries}
    active = cal.solar_term(moment)
    cal.require_term_source(active, **policy)
    month_term = cal.solar_term(moment, jie_only=True)
    year, month = cal.year_month_pillars(moment, **policy)
    active_record = cal.describe_term(active, moment.tzinfo, **policy)
    month_record = cal.describe_term(month_term, moment.tzinfo, **policy)
    return {"schema_version": SCHEMA_VERSION, "method": "civil-clock-four-pillars-v1",
            "local_time": moment.isoformat(), "timezone": source_zone,
            "pillars": {"year": year, "month": month, "day": day, "hour": hour},
            "active_term": active[0], "active_term_since": active_record["time"],
            "term_data_version": cal.TERM_DATA_VERSION,
            "provenance": {"active_term": active_record, "month_boundary": month_record,
                           "calendar_dependency": calendar_dependency(),
                           "conventions": {"clock": "local_civil_time", "day_boundary": "23:00",
                                           "year_boundary": "立春", "month_boundary": "十二节"}},
            "usage": {"status": "ready", "estimated": any(
                record["usage"]["estimated"] for record in (active_record, month_record)),
                "limitations": ["四柱使用本库明确约定；不包含排盘、解盘或吉凶判断。"]}}


def coverage():
    """Report local records, not guaranteed precision or guaranteed algorithm range."""
    sources = {}
    for provider, table in (("pmo", cal.OFFICIAL_TERMS), ("hko", cal.HKO_TERMS)):
        counts = {}
        for year, _ in table:
            counts[year] = counts.get(year, 0) + 1
        sources[provider] = {"record_count": len(table),
                             "complete_years": sorted(year for year, count in counts.items() if count == 24),
                             "partial_years": {str(year): sorted(name for y, name in table if y == year)
                                               for year, count in sorted(counts.items()) if count != 24}}
    return {"schema_version": SCHEMA_VERSION, "term_data_version": cal.TERM_DATA_VERSION,
            "sources": sources, "validation": {"accuracy_bound_seconds": None,
            "note": "覆盖仅表示本地记录存在，不是全范围精度证明或官方对软件的认证。"}}
