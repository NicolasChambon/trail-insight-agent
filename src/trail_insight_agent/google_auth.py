"""User OAuth credentials for the Google APIs that touch personal data.

BigQuery is reached with a service account: the data belongs to the project, so
an identity the project owns is enough. Calendar and Gmail hold the athlete's
own data, which no project-owned identity is entitled to read. Google hands
those over only against a consent a human gave in a browser, to a named client,
for named scopes. Loading that consent is all this file does.

The browser part happens once, in scripts/google_auth.py. Here we only read the
stored token and refresh it - the same split as strava.py, where the
authorization code is exchanged by a one-off script and the refresh token is
traded for a short-lived access token at the start of every run.
"""

from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Derived from this file, like TOOLS_YAML in the agent: this module runs
# inside an MCP server that a client starts as a child process, from a working
# directory nobody here controls.
CREDENTIALS_DIR = Path(__file__).resolve().parents[2] / "credentials"
CLIENT_SECRETS_FILE = CREDENTIALS_DIR / "google_oauth_client.json"
TOKEN_FILE = CREDENTIALS_DIR / "google_token.json"

# Least privilege, the principle behind the BigQuery service account, applied
# to a human's account instead of a project's:
# - calendar.events writes events, and nothing about the calendars themselves
#   - no sharing, no ACL, no deletion of a calendar.
# - gmail.send sends as the athlete, and nothing else. It cannot list, read or
#   search a single message. The inbox is not merely off-limits to the agent:
#   it is unreachable with this token, whatever the agent decides to do.
# Widening this list invalidates the stored token: scopes are part of what was
# consented to, so a new scope means a new trip through the browser.
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.send",
]


class MissingConsent(RuntimeError):
    """No usable delegation on disk.

    Deliberately its own type, and deliberately verbose: it is the one failure
    no retry can fix. Only the human can, by walking through the browser
    again, so the message has to name the command that does it.
    """


def get_access_token() -> str:
    """Return an access token valid for SCOPES, refreshing it if needed."""
    if not TOKEN_FILE.exists():
        raise MissingConsent(
            f"no Google token at {TOKEN_FILE}. "
            "Run: uv run scripts/google_auth.py"
        )

    credentials = Credentials.from_authorized_user_file(
        str(TOKEN_FILE), scopes=SCOPES
    )

    # valid == there is a token and it has not expired. Access tokens last
    # about an hour; the refresh token is the part that persists.
    if not credentials.valid:
        try:
            credentials.refresh(Request())
        except RefreshError as error:
            raise MissingConsent(
                f"Google refused the stored consent ({error}). "
                "Run: uv run scripts/google_auth.py\n"
                "Refresh tokens issued while the OAuth app is in Testing "
                "expire after seven days; consent is also lost when it is "
                "revoked or the account password changes."
            ) from error

        # Write back. Google may rotate the refresh token, and always returns
        # a new expiry. Same failure mode as Strava rotating its own - drop
        # the new value and the next run is locked out - except silent here,
        # because the file we failed to update still parses.
        TOKEN_FILE.write_text(credentials.to_json())

    return credentials.token
