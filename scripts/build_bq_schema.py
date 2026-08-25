"""Generate the BigQuery JSON schema file for activities_raw.

The field declaration in trail_insight_agent.schema is the single source of
truth; this file is derived from it, never hand-edited.

Usage: uv run scripts/build_bq_schema.py
"""

import json
from pathlib import Path

from trail_insight_agent.schema import ACTIVITIES_RAW_FIELDS

OUTPUT_PATH = Path("schema/activities_raw.json")


def main() -> None:
    schema = [
        {"name": name, "type": bq_type, "mode": mode}
        for name, bq_type, mode in ACTIVITIES_RAW_FIELDS
    ]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(schema, indent=2) + "\n")

    print(f"Wrote {len(schema)} fields to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
