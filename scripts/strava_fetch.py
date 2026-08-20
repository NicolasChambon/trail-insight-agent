"""Download the full Strva activity history into a raw JSON file.

Usage: uv run scripts/strava_fetch.py
"""

import json
from pathlib import Path

from trail_insight_agent.strava import fetch_all_activities, get_access_token

OUTPUT_PATH = Path("data/raw/activities.json")


def main() -> None:
    token = get_access_token()
    activities = fetch_all_activities(token)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(
            activities,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {len(activities)} activities to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
