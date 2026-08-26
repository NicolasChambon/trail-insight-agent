-- The curated view: the only object the agent is allowed to read.
-- Layer 1 (base) computes; layer 2 formats for a human reader.
CREATE OR REPLACE VIEW
  `trail-insight-agent.trail_insight.v_activities` AS
WITH base AS (
  SELECT
    -- Identity and context
    id AS activity_id,
    name AS activity_name,  -- display label only, never a filter
    DATE(start_date_local) AS activity_date,
    TIME(start_date_local) AS start_time_local,
    sport_type AS sport,
    -- workout_type is sport-dependent (0-3 running, runumbered from 10 for 
    -- cycling, 30 on WeightTraining) and absent on most sports. The simple 
    -- CASE form cannot match NULL, so this is the searched form.
    CASE
      WHEN workout_type IS NULL THEN 'unspecified'  -- Strava recorded none
      WHEN workout_type = 0 THEN 'default'
      WHEN workout_type = 1 THEN 'race'
      WHEN workout_type = 2 THEN 'long_run'
      WHEN workout_type = 3 THEN 'workout'
      WHEN workout_type = 10 THEN 'default'
      WHEN workout_type = 11 THEN 'race'
      WHEN workout_type = 12 THEN 'workout'
      ELSE 'unknown'  -- undocumented codes are not guessed
    END AS workout_label,

    -- Volume, in units a human reads
    ROUND(distance / 1000, 2) AS distance_km,
    ROUND(total_elevation_gain) AS elevation_gain_m,
    ROUND(SAFE_DIVIDE(total_elevation_gain, distance / 1000), 1)
      AS elevation_gain_per_km,

    -- French trail convention: a linear approximation, not a
    -- measurement. Ignores descent; underestimates on steep ground.
    ROUND(distance / 1000 + total_elevation_gain / 100, 2) AS effort_km,

    -- Time. duration_s is the reference clock: watch start to stop.
    elapsed_time AS duration_s,
    moving_time AS moving_time_s,
    elapsed_time - moving_time AS stopped_time_s,
    ROUND(100 * SAFE_DIVIDE(elapsed_time - moving_time, elapsed_time))
      AS stopped_share_pct,

    -- Pace: one canonical unit for every row and every sport,
    -- computed here from elapsed_time. Neither Strava's average_speed
    -- nor its moving_time is used: both are vendor-computed, and
    -- moving_time drops sub-threshold speeds, which is exactly what
    -- happens on steep climbs. Always read with stopped_share_pct.
    ROUND(SAFE_DIVIDE(elapsed_time, distance / 1000)) AS pace_s_per_km,

    -- Effort-km pace is a running convention; NULL elsewhere.
    CASE
      WHEN sport_type IN ('Run', 'TrailRun', 'VirtualRun', 'Hike',
                          'Walk', 'BackcountrySki')
        THEN ROUND(SAFE_DIVIDE(
          elapsed_time,
          distance / 1000 + total_elevation_gain / 100))
    END AS pace_s_per_effort_km,

    -- Physiology, with its coverage flag
    ROUND(average_heartrate) AS avg_heartrate_bpm,
    has_heartrate,
    ROUND(average_cadence, 1) AS avg_cadence_spm,
    average_temp AS avg_temperature_c,
    suffer_score AS relative_effort,

    -- Provenance and context flags
    manual AS is_manual_entry,
    trainer AS is_indoor,
    commute AS is_commute
  FROM
    `trail-insight-agent.trail_insight.activities_raw`
)
SELECT
  base.*,

  -- Display columns: the presentation layer, moved into SQL because
  -- the consumer is an LLM, i.e. a renderer with no format().
  -- Every one of these is derived from a base column above, so it can
  -- never disagree with it. Copy verbatim, never recompute.
  CASE
    WHEN pace_s_per_km IS NULL THEN NULL
    WHEN sport IN ('Run', 'TrailRun', 'VirtualRun', 'Hike', 'Walk', 'BackcountrySki')
      THEN FORMAT(
        "%d'%02d\"/km",
        DIV(CAST(pace_s_per_km AS INT64), 60),
        MOD(CAST(pace_s_per_km AS INT64), 60))
    ELSE FORMAT('%.1f km/h', 3600 / pace_s_per_km)
  END AS pace_display,

  CASE
    WHEN pace_s_per_effort_km IS NULL THEN NULL
    ELSE FORMAT(
      "%d'%02d\"/km-effort",
      DIV(CAST(pace_s_per_effort_km AS INT64), 60),
      MOD(CAST(pace_s_per_effort_km AS INT64), 60))
  END AS pace_per_effort_display,

  CASE
    WHEN duration_s >= 3600
      THEN FORMAT('%dh%02d', DIV(duration_s, 3600),
                  DIV(MOD(duration_s, 3600), 60))
    ELSE FORMAT('%dmin', DIV(duration_s, 60))
  END AS duration_display,

  CASE
    WHEN stopped_time_s >= 3600
      THEN FORMAT('%dh%02d', DIV(stopped_time_s, 3600),
                  DIV(MOD(stopped_time_s, 3600), 60))
    ELSE FORMAT('%dmin', DIV(stopped_time_s, 60))
  END AS stopped_time_display
FROM
  base
