"""Field declaration for the raw Strava landing table

One declaration drives both the NDJSON projection and, in the next step, the
BigQuery schema file.
"""

# (Strava API field name, BigQuery type, BigQuery mode).
# The raw table mirrors the API: no renaming, no unit conversion.
# Business names and readable units belong to the curated view.
ACTIVITIES_RAW_FIELDS = [
    ("id", "INT64", "REQUIRED"),
    ("name", "STRING", "NULLABLE"),
    ("sport_type", "STRING", "REQUIRED"),
    ("workout_type", "INT64", "NULLABLE"),
    ("start_date_local", "DATETIME", "REQUIRED"),
    ("distance", "FLOAT64", "REQUIRED"),
    ("moving_time", "INT64", "REQUIRED"),
    ("elapsed_time", "INT64", "REQUIRED"),
    ("total_elevation_gain", "FLOAT64", "REQUIRED"),
    ("average_speed", "FLOAT64", "REQUIRED"),
    ("average_heartrate", "FLOAT64", "NULLABLE"),
    ("has_heartrate", "BOOL", "REQUIRED"),
    ("average_cadence", "FLOAT64", "NULLABLE"),
    ("average_temp", "INT64", "NULLABLE"),
    ("suffer_score", "FLOAT64", "NULLABLE"),
    ("manual", "BOOL", "REQUIRED"),
    ("trainer", "BOOL", "NULLABLE"),
    ("commute", "BOOL", "NULLABLE"),
    ("device_name", "STRING", "NULLABLE"),
    ("elev_high", "FLOAT64", "NULLABLE"),
    ("elev_low", "FLOAT64", "NULLABLE"),
]


def project(activity: dict) -> dict:
    """Keep only declared fields, in the declared order.

    Strava serialises local time with a misleading "Z" suffix. Dropping it is a
    format fix, not a value change: BigQuery then reads the string as a
    zone-less DATETIME instead of shifting it by the UTC offset.
    """
    row = {name: activity.get(name) for name, _, _ in ACTIVITIES_RAW_FIELDS}
    if row["start_date_local"] is not None:
        row["start_date_local"] = row["start_date_local"].removesuffix("Z")
    return row
