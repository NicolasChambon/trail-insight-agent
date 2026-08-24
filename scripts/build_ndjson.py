"""Turn the raw Strava JSON array into newline-delimited JSON.

Usage: uv run scripts/build_ndjson.py
"""

import json
from pathlib import Path

from trail_insight_agent.schema import project

RAW_PATH = Path("data/raw/activities.json")
OUTPUT_PATH = Path("data/processed/activities.ndjson")


def main() -> None:
    activities = json.loads(RAW_PATH.read_text(encoding="utf-8"))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as out:
        for activity in activities:
            row = project(activity)
            out.write(json.dumps(row, ensure_ascii=False))
            out.write("\n")

    print(f"Wrote {len(activities)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
