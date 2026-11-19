"""Normalized lap schema shared by ingest, storage, and replay."""

# Column order of every stored laps.parquet file.
LAP_COLUMNS: tuple[str, ...] = (
    "driver",
    "team",
    "lap",
    "lap_time_s",
    "session_time_s",
    "stint",
    "compound",
    "tyre_life",
    "pit_in",
    "pit_out",
    "track_status",
    "is_accurate",
)

# Colour used when FastF1 has no TeamColor for a driver.
DEFAULT_TEAM_COLOR = "#71717A"
