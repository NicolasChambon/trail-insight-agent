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

## Stack

- Google ADK — agent framework
- BigQuery — data warehouse (partitioned, curated views)
- MCP (Model Context Protocol) — data connectivity: MCP Toolbox for BigQuery plus a
  custom FastMCP server for peer-comparison logic
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

### 4. Fetch the activity history

`uv run scripts/strava_fetch.py   # write data/raw/activities.json`

### 5. Build the Google Cloud side

`/scripts/setup_gcp.sh`

Idempotent. It creates the dataset, loads the raw table, creates the
curated view, provisions the agent's service account and its IAM bindings,
and **ends by asserting the security invariant**: the service account reads
`v_activities` and gets a `403` on `activities_raw`. It exits non-zero
otherwise.

BigQuery runs in sandbox mode (no billing account), so every table expires
60 days after creation. Re-run the script to rebuild.

### 6. Run the MCP server

`toolbox --config mcp/tools.yaml invoke describe_dataset  # smoke test`

The same server has two stdio clients, and neither is privileged over the
other: `.mcp.json` wires it into Claude Code, picked up automatically when
Claude Code starts in this directory, and `agents/trail_coach/agent.py` wires
it into the ADK agent through an `McpToolset`. Same binary, same `tools.yaml`,
same service account — one security surface to audit.
