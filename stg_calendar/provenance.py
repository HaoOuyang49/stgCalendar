"""Source evidence and explicit usage conditions, separate from domain verdicts."""

from importlib.metadata import PackageNotFoundError, version
from datetime import datetime

from .pmo_terms import publication_for

SCHEMA_VERSION = "result-evidence-v1"
PROVIDER_NAMES = {"pmo": "中国科学院紫金山天文台", "hko": "香港天文台",
                  "lunar-python": "lunar-python"}


def package_version(name):
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def table_coverage(table, year):
    """Describe records present locally. Coverage is not measured accuracy."""
    years = sorted({item_year for item_year, _ in table})
    names = sorted(name for item_year, name in table if item_year == year)
    return {"year_range": [years[0], years[-1]] if years else None,
            "requested_year": year, "available_terms_in_year": names,
            "complete_requested_year": len(names) == 24, "record_count": len(table)}


def calendar_dependency(uses=("day_pillar", "adjacent_term_candidates")):
    return {"provider": "lunar-python", "version": package_version("lunar-python"),
            "uses": list(uses),
            "validation": {"status": "partial_regression_tests", "accuracy_bound_seconds": None,
                           "scope": "tests/test_calendar.py 中已列出的日期和边界；非全范围精度认证"}}


def term_evidence(term, *, official_terms, hko_terms, data_version, display_zone=None,
                  allow_estimated_terms=False, require_second_precision=False,
                  accept_minute_boundaries=False):
    name, boundary, provider = term
    if provider not in PROVIDER_NAMES:
        raise ValueError(f"未知节气来源：{provider}")
    estimated = provider == "lunar-python"
    year = boundary.year
    table = {"pmo": official_terms, "hko": hko_terms}.get(provider)
    publication = (publication_for(year) if provider == "pmo" else
                   {"title": f"{year}年二十四节气", "edition": str(year), "kind": "annual_table",
                    "url": f"https://www.hko.gov.hk/en/gts/astronomy/data/files/24SolarTerms_{year}.xml"}
                   if provider == "hko" else None)
    confirmations = []
    if estimated:
        confirmations.append({"code": "estimated_terms", "field": "allow_estimated_terms",
                              "status": "granted" if allow_estimated_terms else "pending",
                              "question": f"{year}年{name}缺少已录入的两家官方资料，是否接受lunar-python估算？",
                              "choices": ["accept_estimate", "provide_official_data"]})
    if not estimated and require_second_precision:
        confirmations.append({"code": "minute_boundary", "field": "accept_minute_boundaries",
                              "status": "granted" if accept_minute_boundaries else "pending",
                              "question": f"{year}年{name}资料只公布到分钟，是否接受从该分钟起点切换？",
                              "choices": ["accept_minute_boundary", "provide_finer_official_data"]})
    pending = any(item["status"] == "pending" for item in confirmations)
    limitations = ["显示或公布分辨率不等于实际误差界限；未据此给出准确率或置信度。"]
    if estimated:
        limitations.append("这是第三方历算估算；输出到秒不代表误差小于一秒，也不等于官方资料。")
    else:
        limitations.append("秒位00是程序的分钟边界约定，不是官方确认的真实交节秒数；未假定取整误差范围。")
    return {
        "schema_version": SCHEMA_VERSION, "name": name,
        "time": boundary.astimezone(display_zone).isoformat() if display_zone else boundary.isoformat(),
        "source": {"provider": provider, "name": PROVIDER_NAMES[provider],
                   "kind": "third_party_estimate" if estimated else "official_publication_transcription",
                   "publication": publication, "data_version": data_version,
                   "algorithm_version": package_version("lunar-python") if estimated else None},
        "method": "third_party_calendar_estimate" if estimated else "published_table",
        "precision": {"published_resolution": None if estimated else "minute",
                      "computed_resolution": "second" if estimated else None,
                      "accuracy_bound_seconds": None,
                      "requested_resolution": "second" if require_second_precision else "minute",
                      "meets_requested_resolution": estimated or not require_second_precision},
        "data_coverage": table_coverage(table, year) if table is not None else None,
        "validation": {"status": "accuracy_not_established", "validated_year_range": None,
                       "note": "本地表的覆盖范围与回归测试不构成所有记录的秒级精度证明。"},
        "usage": {"status": "needs_confirmation" if pending else "ready",
                  "can_use": not pending, "estimated": estimated,
                  "requires_user_consent": bool(confirmations), "confirmations": confirmations,
                  "boundary_policy": "calculated_instant" if estimated else "published_minute_start",
                  "limitations": limitations},
    }


class ResultConfirmationRequired(ValueError):
    """A caller may render the question, collect a choice, then retry explicitly."""

    code = "confirmation_required"

    def to_dict(self):
        return {"schema_version": SCHEMA_VERSION, "status": "needs_confirmation",
                "error": {"code": self.code, "message": str(self)},
                "evidence": self.evidence}


def collect_term(records, evidence):
    if records is None:
        return

    def identity(record):
        return (record["name"], datetime.fromisoformat(record["time"]),
                record["source"]["provider"], record["source"]["data_version"])

    if not any(identity(record) == identity(evidence) for record in records):
        records.append(evidence)
