# trail-insight-agent

A conversational GenAI agent that reads and explains the performance of my
trail-running training, grounded in my own Strava data stored in BigQuery.
Every figure it reports comes from a tool call; nothing is answered from
memory. The one thing it refuses outright is anything medical.

## Why this project

I'm an ultra-trail runner and a long-time sports-data tinkerer. I wanted an agent
that answers questions like _"why was Sunday's run slower than the same route in
May?"_ with real figures pulled from my history — not vague generalities, and not
made-up numbers. It's also my hands-on way to build a production-shaped GenAI
system end to end: grounded answers, least-privilege data access, explicit scope
guardrails, and an evaluation harness.

## What it can (and can't) do

- **Grounded, or silent**: it reports what a tool returned, and says so when no
  tool can answer. It never writes SQL, and never names a table or a column it
  has not read.
- **Refuses, by design**: anything medical ("do I have an injury?"). That is
  the only outright refusal — narrow, true, and therefore testable.
- **Acts, narrowly**: it reads the athlete's Google Calendar and can add a
  training session to it, under a user OAuth consent kept separate from the
  service account that reads BigQuery. It cannot delete an event, cannot touch
  calendar but the primary one, and cannot reach a mailbox at all.

## Stack

- Google ADK — agent framework
- BigQuery — data warehouse (partitioned, curated views)
- MCP (Model Context Protocol) — two stdio servers behind one agent: MCP
  Toolbox serves the BigQuery queries declaratively under a service account, a
  hand-written FastMCP server serves everything that is not SQL and carries the
  user OAuth consent for Google Calendar.
- Evaluation harness — factual accuracy, grounding, and guardrail compliance

## Setup

### 1. Prerequisites

| Tool                      | Version                     | Managed by                            |
| :------------------------ | :-------------------------- | :------------------------------------ |
| Python                    | 3.12                        | `uv`, pinned in `.python-version`     |
| Google Cloud CLI          | any recent                  | system install, bundles `bq`          |
| MCP Toolbox for Databases | **1.9.0**                   | manual, see below                     |
| Strava account            | with an active subscription | required for API access since 2026-06 |

Toolbox is a compiled Go binary, not a Python package, so `uv.lock` cannot
own it. Its version is pinned **here and nowhere else** — this file
documents, it does not constrain. Containerising the server would restore a
machine-checkable guarantee; it is listed as a possible extension.

```sh
mkdir -p ~/.local/bin
curl -L -o ~/.local/bin/toolbox \
  https://storage.googleapis.com/mcp-toolbox-for-databases/v1.9.0/linux/amd64/toolbox
chmod +x ~/.local/bin/toolbox
toolbox --version   # must print 1.9.0
```

Note the bucket name: the project was renamed from genai-toolbox to
mcp-toolbox, and search results still point at the old bucket, which
404s on 1.x and serves 0.x — where the tools.yaml format is different.

### 2. Python environment

`uv sync`

### 3. Credentials

#### 3.1 BigQuery

`gcloud auth login                # your indentity, for gcloud and bq`  
`gcloud auth application-default  # the identity your CODE uses`  
`gcloud auth application-default set-quota-project trail-insight-agent`

Both are required and theu are not the same thing: bq uses the gcloud session, while any third-party binary — Toolbox included — uses ADC.

#### 3.2 Strava

The Strava API requires a Strava subscription since 2026-06 (individual
athletes keep free bulk export; only the API was paywalled).

**Register the application** at <https://www.strava.com/settings/api>.
Set _Authorization Callback Domain_ to the bare domain `localhost` —
no scheme, no port, no path. Anything else is rejected.

Copy `.env.example` to `.env` and fill in `STRAVA_CLIENT_ID` and
`STRAVA_CLIENT_SECRET`.

**Run the OAuth exchange once, by hand.** Open this URL in a browser,
replacing `<CLIENT_ID>`:

https://www.strava.com/oauth/authorize?client_id=<CLIENT_ID>&response_type=code&redirect_uri=http://localhost/exchange_token&approval_prompt=force&scope=activity:read_all

Approve the requested scope. The browser is then redirected to
`http://localhost/exchange_token?state=&code=...&scope=...` and **fails to
load** — nothing is listening on `localhost`. That is expected: read the
value of `code=` straight out of the address bar. It is single-use and
short-lived, which is exactly why the browser carries it rather than the
token itself.

Trade it for tokens:

```sh
uv run scripts/strava_auth.py <authorization code>
```

Copy the printed refresh token into STRAVA_REFRESH_TOKEN in .env. Only
that one is persisted; the access token (~6 h) is re-derived at the start of
every run.

Verify:

`uv run scripts/strava_whoami.py`

#### 3.3 Google Calendar

BigQuery is read by a service account, because the data belongs to the
project. The calendar does not: it belongs to a person, and Google hands it
over only against a consent that person gave in a browser. Two identity models
in one project, on purpose.

```sh
gcloud services enable calendar-json.googleapis.com --project trail-insight-agent
```

Then in the console, under **Google Auth Platform** — the pages that replaced
the old "OAuth consent screen" wizard:

- **Branding** — app name and a support email. Everything else stays empty: a
  Desktop client has no domain, no home page and no privacy policy to show.
- **Audience** — user type `External`, publishing status `Testing`, and the
  athlete's Google account added under **Test users**. This is the page that
  decides whether the flow works at all; an account missing here gets a bare
  `403 access_denied`. Note that this need not be the account the console is
  open with — the client belongs to the project, the consent belongs to a
  person.
- **Data Access** — add `https://www.googleapis.com/auth/calendar.events`, and
  nothing else. It writes events and nothing about the calendars themselves:
  no sharing, no ACL, no deleting a calendar.
- **Clients** — create an OAuth client of type **Desktop app**, not "Web
  application". Only the Desktop type accepts an arbitrary
  `http://127.0.0.1:<port>` callback, which is what lets the script pick a free
  port instead of registering one in the console.

Download the client JSON and save it as `credentials/google_oauth_client.json`.
The whole directory is gitignored; check that before going further.

```sh
git check-ignore -v credentials/google_oauth_client.json   # must print a rule
```

**Run the consent once:**

```sh
uv run scripts/google_auth.py
```

A browser opens. Sign in **as the athlete**, and approve. The "Google hasn't
verified this app" screen is expected while the app is in Testing: Advanced →
Continue. Only the refresh token is persisted, in
`credentials/google_token.json`; the access token lives about an hour and is
re-derived on demand, exactly like Strava's.

Verify:

```sh
uv run python -c "from trail_insight_agent.google_auth import get_access_token; \
print(get_access_token()[:16], '...')"
```

**Note the seven days.** While the publishing status is `Testing`, Google
expires refresh tokens after a week. When every calendar tool starts answering
"run scripts/google_auth.py", that is why. Switching the app to "In production"
removes the limit at the cost of an unverified-app warning, and will be
required the day anything runs unattended.

### 4. Fetch the activity history

`uv run scripts/strava_fetch.py   # write data/raw/activities.json`

### 5. Build the Google Cloud side

`/scripts/setup_gcp.sh`

Idempotent. It creates the dataset, loads the raw table, creates the
curated view, provisions the agent's service account and its IAM bindings,
and **ends by asserting the security invariant**: the service account reads
`v_activities` and gets a `403` on `activities_raw`. It exits non-zero
otherwise.

The project carries a billing account — the Gemini API needs one: the free
tier stops at 20 requests per day per model, and a question that chains two
tools spends three of them. BigQuery therefore no longer runs in sandbox
mode, and tables no longer expire.

### 6. Run the MCP server

`toolbox --config mcp/tools.yaml invoke describe_dataset  # smoke test`

The same server has two stdio clients, and neither is privileged over the
other: `.mcp.json` wires it into Claude Code, picked up automatically when
Claude Code starts in this directory, and `agents/trail_coach/agent.py` wires
it into the ADK agent through an `McpToolset`. Same binary, same `tools.yaml`,
same service account — one security surface to audit.
