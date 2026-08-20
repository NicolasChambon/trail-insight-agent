"""Exchange a Strava authorization code for access and refresh tokens.

One-off script: run it once with the code obtained in the browser using this
url:
https://www.strava.com/oauth/authorize?client_id=<CLIENT_ID>&response_type=code&redirect_uri=http://localhost/exchange_token&approval_prompt=force&scope=activity:read_all
then copy the print refresh token into .env.

Usage: uv run scripts/strava_auth.py <authorization code>
"""

import os
import sys
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

TOKEN_URL = "https://www.strava.com/oauth/token"


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: uv run scripts/strava_auth.py <authorization code>")

    load_dotenv()

    response = httpx.post(
        TOKEN_URL,
        data={
            "client_id": os.environ["STRAVA_CLIENT_ID"],
            "client_secret": os.environ["STRAVA_CLIENT_SECRET"],
            "code": sys.argv[1],
            "grant_type": "authorization_code",
        },
    )
    response.raise_for_status()
    tokens = response.json()

    athlete = tokens["athlete"]
    expires_at = datetime.fromtimestamp(tokens["expires_at"], tz=timezone.utc)

    print(
        f"athlete       : {athlete['firstname']} {athlete['lastname']} "
        f"(id {athlete['id']})"
    )
    print(f"expires at    : {expires_at:%Y-%m-%d %H:%M} UTC")
    print(
        f"access token  : {tokens['access_token'][:8]}... "
        f"(short-lived, not stored)"
    )
    print(f"refresh token : {tokens['refresh_token']} <-- put this in .env")


if __name__ == "__main__":
    main()
