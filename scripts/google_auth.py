"""Run the Google OAuth consent flow once, and store the resulting tokens.

The Google counterpart of scripts/strava_auth.py, and one step shorter: the
library runs a loopback web server, so the authorization code is caught
instead of being copied out of the address bar.

This is the only place in the project that opens a browser. The MCP server
reads the token file and refreshes it; it never asks for consent, because a
stdio child process has no human in front of it.

Usage: uv run scripts/google_auth.py
"""

import sys

from google_auth_oauthlib.flow import InstalledAppFlow

from trail_insight_agent.google_auth import (
    CLIENT_SECRETS_FILE,
    SCOPES,
    TOKEN_FILE,
)


def main() -> None:
    if not CLIENT_SECRETS_FILE.exists():
        sys.exit(
            f"missing {CLIENT_SECRETS_FILE}\n"
            "Download the OAuth client JSON from the Google Cloud console "
            "(APIs & Services > Credentials > OAuth client ID, type "
            "'Desktop app') and save it there."
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_SECRETS_FILE), scopes=SCOPES
    )

    credentials = flow.run_local_server(
        # port=0: any free port. A Desktop OAuth client accepts every
        # http://127.0.0.1:<port> callback, so nothing has to be declared in
        # the console - the redirect URI is settled at runtime.
        port=0,
        # offline is what asks for a refresh token at all; without it Google
        # returns an access token that dies in an hour and nothing else.
        access_type="offline",
        # Force the consent screen even when this account has already
        # approved. Google omits the refresh token on a silent re-approval,
        # and a token file without one cannot be refreshed.
        prompt="consent",
    )

    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(credentials.to_json())
    # The file is the athlete's delegation. Nobody else on this machine.
    TOKEN_FILE.chmod(0o600)

    print(f"account       : {credentials.client_id.split('-')[0]}...")
    print(f"scopes        : {' '.join(credentials.scopes)}")
    print(f"access token  : expires {credentials.expiry:%Y-%m-%d %H:%M} UTC")
    print(f"refresh token : stored in {TOKEN_FILE}")


if __name__ == "__main__":
    main()
