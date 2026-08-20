"""Thin client for the Strava API v3.

Everything that talks to Strava lives here, so the token refresh sits in
 exactly one place and scripts stay short
"""

import os

import httpx
from dotenv import load_dotenv

API_BASE = "https://www.strava.com/api/v3"
TOKEN_URL = "https://www.strava.com/oauth/token"


def get_access_token() -> str:
    """Trade the stored refresh token for a short-lived access token."""
    load_dotenv()
    stored_refresh_token = os.environ["STRAVA_REFRESH_TOKEN"]

    response = httpx.post(
        TOKEN_URL,
        data={
            "client_id": os.environ["STRAVA_CLIENT_ID"],
            "client_secret": os.environ["STRAVA_CLIENT_SECRET"],
            "refresh_token": stored_refresh_token,
            "grant_type": "refresh_token",
        },
    )
    response.raise_for_status()
    tokens = response.json()

    # Strava may rotate the refresh token. Silently ignoring a new one locks us
    # out on the next run, so make it loud.
    if tokens["refresh_token"] != stored_refresh_token:
        print(
            "WARNING: Strava rotated the refresh token.\n"
            "Update STRAVA_REFRESH_TOKEN in .env with:\n"
            f"  {tokens['refresh_token']}"
        )

    return tokens["access_token"]


PAGE_SIZE = 200
MAX_PAGES = 50


def fetch_all_activities(access_token: str) -> list[dict]:
    """Return every activity of the authenticated athlete, newest first."""
    headers = {"Authorization": f"Bearer {access_token}"}
    activities: list[dict] = []

    for page in range(1, MAX_PAGES + 1):
        response = httpx.get(
            f"{API_BASE}/athlete/activities",
            headers=headers,
            params={"page": page, "per_page": PAGE_SIZE},
            timeout=30.0,
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            return activities

        activities.extend(batch)
        print(
            f"page {page:>2}: {len(batch):>3} activities "
            f"({len(activities)} so far)"
        )

    raise RuntimeError(f"stopper after {MAX_PAGES} pages - raise MAX_PAGES?")
