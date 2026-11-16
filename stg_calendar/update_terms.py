"""Preview and apply a reviewed, complete PMO annual publication."""

import argparse
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from .hko_terms import HKO_TERMS
from .pmo_terms import OFFICIAL_TERMS, UPDATE_FILE, load_updates, parse_annual_update, unique_keys


def preview_update(year, document):
    incoming = parse_annual_update(year, document)
    changes = []
    for key, new in incoming.items():
        old = OFFICIAL_TERMS.get(key) or HKO_TERMS.get(key)
        old_source = "pmo" if key in OFFICIAL_TERMS else "hko" if old else None
        changes.append({
            "term": key[1],
            "old": old.isoformat(timespec="minutes") if old else None,
            "old_source": old_source,
            "new": new.isoformat(timespec="minutes"),
            "new_source": "pmo",
            "delta_minutes": int((new - old).total_seconds() // 60) if old else None,
        })
    return changes


def apply_update(year, document):
    parse_annual_update(year, document)
    records = load_updates()
    records[str(year)] = document
    UPDATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=UPDATE_FILE.parent,
                            suffix=".tmp", delete=False) as output:
        temp = Path(output.name)
        json.dump(records, output, ensure_ascii=False, indent=2, sort_keys=True)
        output.write("\n")
    try:
        temp.replace(UPDATE_FILE)
    finally:
        temp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="导入已人工核对的紫金山天文台年度节气表")
    parser.add_argument("year", type=int)
    parser.add_argument("input", type=Path)
    parser.add_argument("--apply", action="store_true", help="确认预览后写入项目数据文件")
    args = parser.parse_args()
    try:
        document = json.loads(args.input.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_keys)
        changes = preview_update(args.year, document)
        if args.apply:
            apply_update(args.year, document)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"year": args.year, "applied": args.apply, "publication": document["publication"],
                      "source_url": document["source_url"], "terms": changes}, indent=2))


if __name__ == "__main__":
    main()
