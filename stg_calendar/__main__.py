"""JSON CLI; confirmation requests are data, not implicit permission."""

import argparse
import json
import sys
from zoneinfo import ZoneInfoNotFoundError

from . import __version__, calendar_at, coverage, get_term, terms_for_year
from .provenance import ResultConfirmationRequired, SCHEMA_VERSION


def main():
    parser = argparse.ArgumentParser(description="官方公布历表优先的节气与公历钟表换算；第三方独立实现")
    parser.add_argument("--version", action="version", version=__version__)
    modes = parser.add_subparsers(dest="mode", required=True)
    at = modes.add_parser("at", help="本地公历钟表时间转四柱与节气")
    at.add_argument("timestamp", help="含时分的ISO时间，或now")
    term = modes.add_parser("term", help="查询一个节气，年份以北京时间资料为准")
    term.add_argument("year", type=int)
    term.add_argument("name")
    year = modes.add_parser("year", help="查询全年24个节气")
    year.add_argument("year", type=int)
    modes.add_parser("coverage", help="查看本地官方资料覆盖")
    for mode in (at, term, year):
        mode.add_argument("--timezone", help="IANA时区名；at的输入也可直接带UTC偏移")
        mode.add_argument("--allow-estimated-terms", action="store_true", help="明确同意官方缺项时的第三方估算")
        mode.add_argument("--require-second-precision", action="store_true", help="请求秒级分辨率，不表示秒级误差保证")
        mode.add_argument("--accept-minute-boundaries", action="store_true", help="明确接受从公布分钟起点切换")
    args = parser.parse_args()
    try:
        if args.mode == "coverage":
            result = coverage()
        else:
            policy = {"allow_estimated_terms": args.allow_estimated_terms,
                      "require_second_precision": args.require_second_precision,
                      "accept_minute_boundaries": args.accept_minute_boundaries}
            if args.mode == "at":
                result = calendar_at(args.timestamp, args.timezone, **policy)
            elif args.mode == "term":
                result = get_term(args.year, args.name, args.timezone, **policy)
            else:
                result = terms_for_year(args.year, args.timezone, **policy)
    except ResultConfirmationRequired as exc:
        print(json.dumps(exc.to_dict(), ensure_ascii=True, indent=2), file=sys.stderr)
        return 2
    except (ValueError, ZoneInfoNotFoundError, OSError) as exc:
        print(json.dumps({"schema_version": SCHEMA_VERSION, "status": "error",
                          "error": {"code": "invalid_input", "message": str(exc)}},
                         ensure_ascii=True, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
