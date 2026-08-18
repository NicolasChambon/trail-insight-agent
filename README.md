# trail-insight-agent

A conversational GenAI agent that **explains** the performance of my trail-running
training, grounded in my own Strava data stored in BigQuery. It explains what the
numbers say — it never prescribes training nor gives medical advice.

## Why this project

I'm an ultra-trail runner and a long-time sports-data tinkerer. I wanted an agent
that answers questions like _"why was Sunday's run slower than the same route in
May?"_ with real figures pulled from my history — not vague generalities, and not
made-up numbers. It's also my hands-on way to build a production-shaped GenAI
system end to end: grounded answers, least-privilege data access, explicit scope
guardrails, and an evaluation harness.

## What it can (and can't) do

- **Answers, with figures from BigQuery**: pace and heart-rate drift, elevation-gain
  volume vs my 2-year average, comparison of a run against similar past runs.
- **Refuses, by design**: training prescriptions ("what should I do this week?") and
  anything medical ("do I have an injury?"). It explains, it does not advise.

## Stack

- Google ADK — agent framework
- BigQuery — data warehouse (partitioned, curated views)
- MCP (Model Context Protocol) — data connectivity: MCP Toolbox for BigQuery plus a
  custom FastMCP server for peer-comparison logic
- Evaluation harness — factual accuracy, grounding, and guardrail compliance

## Status

Work in progress. See `docs/JOURNAL.md` for progress and `docs/DECISIONS.md` for
architecture decisions.
