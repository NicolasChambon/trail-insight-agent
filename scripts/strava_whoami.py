"""Check that the stored Strava credentials still work.

Usage: uv run scripts/strava_whoami.py.
"""

import httpx

from trail_insight_agent.strava import API_BASE, get_access_token


def main() -> None:
    token = get_access_token()

    response = httpx.get(
        f"{API_BASE}/athlete",
        headers={"Authorization": f"Bearer {token}"},
    )
    response.raise_for_status()
    athlete = response.json()

    print(f"{athlete['firstname']} {athlete['lastname']}")
    print(f"id      : {athlete['id']}")
    print(f"country : {athlete.get('country')}")


if __name__ == "__main__":
    main()
