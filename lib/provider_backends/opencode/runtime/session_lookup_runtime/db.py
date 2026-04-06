from __future__ import annotations

from .common import directories_match, session_entry


def get_latest_session_from_db(reader) -> dict | None:
    if not reader._work_dir_candidates():
        return None

    rows = reader._fetch_opencode_db_rows("SELECT * FROM session ORDER BY time_updated DESC LIMIT 200", ())
    best_match: dict | None = None
    best_updated = -1
    latest_unfiltered: dict | None = None
    latest_unfiltered_updated = -1

    for row in rows:
        entry = _matching_row_entry(reader, row)
        if entry is None:
            continue

        updated = entry["payload"]["time"]["updated"]
        if updated > latest_unfiltered_updated:
            latest_unfiltered = entry
            latest_unfiltered_updated = updated

        if reader._session_id_filter and entry["payload"]["id"] != reader._session_id_filter:
            continue
        if updated > best_updated:
            best_match = entry
            best_updated = updated

    if reader._session_id_filter and reader._allow_session_rollover and latest_unfiltered and latest_unfiltered_updated > best_updated:
        return latest_unfiltered
    return best_match


def _matching_row_entry(reader, row) -> dict | None:
    directory = row["directory"]
    if not directories_match(reader, directory):
        return None
    return session_entry(
        path=None,
        sid=row["id"],
        directory=directory,
        updated=row["time_updated"],
    )


__all__ = ["get_latest_session_from_db"]
