from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

from models import MatchLineup, TeamLineup


# ============================================================
# MLS EINSTELLUNGEN
# ============================================================

STATS_BASE_URL = "https://stats-api.mlssoccer.com"

SEASON_ID = "MLS-SEA-0001KA"
COMPETITION_ID = "MLS-COM-000001"

BERLIN_TIMEZONE = ZoneInfo("Europe/Berlin")

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "curl",
}


# ============================================================
# HTTP
# ============================================================

def _get_json(
    url,
    params=None,
):
    response = requests.get(
        url,
        headers=HEADERS,
        params=params,
        timeout=30,
    )

    if response.status_code == 204:
        return None

    response.raise_for_status()

    return response.json()


# ============================================================
# DATUM
# ============================================================

def _parse_datetime(value):
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.astimezone(
            BERLIN_TIMEZONE
        )

    except Exception:
        return None


# ============================================================
# SPIELERNAME
# ============================================================

def _player_name(player):
    first_name = (
        player.get("first_name")
        or ""
    ).strip()

    last_name = (
        player.get("last_name")
        or ""
    ).strip()

    full_name = (
        f"{first_name} {last_name}"
    ).strip()

    if full_name:
        return full_name

    short_name = (
        player.get("short_name")
        or ""
    ).strip()

    if short_name:
        return short_name

    return "Unbekannt"


# ============================================================
# TRUE / FALSE
# ============================================================

def _is_true(value):
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return (
            value.lower().strip()
            == "true"
        )

    if isinstance(value, int):
        return value == 1

    return False


# ============================================================
# MATCHLISTE ERKENNEN
# ============================================================

def _extract_matches(data):
    if data is None:
        return []

    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return []

    possible_keys = [
        "schedule",
        "matches",
        "data",
        "items",
        "results",
        "content",
    ]

    for key in possible_keys:
        value = data.get(key)

        if isinstance(value, list):
            return value

    if data.get("match_id"):
        return [data]

    return []


# ============================================================
# KOMMENDE MLS-SPIELE
# ============================================================

def get_mls_upcoming_matches(days=2):
    url = (
        f"{STATS_BASE_URL}"
        f"/matches/seasons/{SEASON_ID}"
    )

    now = datetime.now(
        BERLIN_TIMEZONE
    )

    start_date = (
        now
        - timedelta(days=1)
    )

    end_date = (
        now
        + timedelta(days=days)
    )

    params = {
        "match_date[gte]": (
            start_date.strftime(
                "%Y-%m-%d"
            )
        ),
        "match_date[lte]": (
            end_date.strftime(
                "%Y-%m-%d"
            )
        ),
        "competition_id": (
            COMPETITION_ID
        ),
        "per_page": "100",
        "sort": (
            "planned_kickoff_time:asc,"
            "home_team_name:asc"
        ),
    }

    try:
        data = _get_json(
            url,
            params=params,
        )

    except Exception as error:
        print(
            f"❌ MLS Spielplan Fehler: "
            f"{error}"
        )
        return []

    matches = _extract_matches(
        data
    )

    earliest = (
        now
        - timedelta(minutes=30)
    )

    latest = (
        now
        + timedelta(days=days)
    )

    result = []

    for match in matches:
        if not isinstance(
            match,
            dict,
        ):
            continue

        competition_id = (
            match.get(
                "competition_id"
            )
            or ""
        )

        if (
            competition_id
            and competition_id
            != COMPETITION_ID
        ):
            continue

        kickoff_raw = (
            match.get(
                "planned_kickoff_time"
            )
            or match.get(
                "kickoff_time"
            )
        )

        kickoff = _parse_datetime(
            kickoff_raw
        )

        if kickoff is None:
            continue

        if kickoff < earliest:
            continue

        if kickoff > latest:
            continue

        match_id = (
            match.get("match_id")
            or ""
        )

        if not match_id:
            continue

        home_team = (
            match.get(
                "home_team_name"
            )
            or match.get(
                "home_team_short_name"
            )
            or "Heimteam"
        )

        away_team = (
            match.get(
                "away_team_name"
            )
            or match.get(
                "away_team_short_name"
            )
            or "Auswärtsteam"
        )

        result.append(
            {
                "match_id": match_id,
                "home_team": home_team,
                "away_team": away_team,
                "kickoff": kickoff,
                "match_url": (
                    f"{STATS_BASE_URL}"
                    f"/matches/{match_id}"
                ),
            }
        )

    result.sort(
        key=lambda item:
        item["kickoff"]
    )

    return result


# ============================================================
# MLS AUFSTELLUNG
# ============================================================

def get_mls_lineup(match):
    if isinstance(match, dict):
        match_id = match.get(
            "match_id"
        )
    else:
        match_id = str(
            match
        )

    if not match_id:
        return None

    url = (
        f"{STATS_BASE_URL}"
        f"/matches/{match_id}"
    )

    try:
        data = _get_json(
            url
        )

    except requests.HTTPError as error:
        status = (
            error.response.status_code
            if error.response
            else None
        )

        if status in (
            404,
            204,
        ):
            return None

        print(
            f"❌ MLS Lineup HTTP Fehler "
            f"{match_id}: {error}"
        )

        return None

    except Exception as error:
        print(
            f"❌ MLS Lineup Fehler "
            f"{match_id}: {error}"
        )

        return None

    if not isinstance(
        data,
        dict,
    ):
        return None

    home = data.get(
        "home"
    )

    away = data.get(
        "away"
    )

    if (
        not isinstance(home, dict)
        or not isinstance(
            away,
            dict,
        )
    ):
        return None

    home_players = (
        home.get("players")
        or []
    )

    away_players = (
        away.get("players")
        or []
    )

    if (
        not home_players
        or not away_players
    ):
        return None

    # ========================================================
    # HOME
    # ========================================================

    home_starters = []
    home_substitutes = []

    for player in home_players:
        if not isinstance(
            player,
            dict,
        ):
            continue

        name = _player_name(
            player
        )

        if _is_true(
            player.get("starting")
        ):
            home_starters.append(
                name
            )

        else:
            home_substitutes.append(
                name
            )

    # ========================================================
    # AWAY
    # ========================================================

    away_starters = []
    away_substitutes = []

    for player in away_players:
        if not isinstance(
            player,
            dict,
        ):
            continue

        name = _player_name(
            player
        )

        if _is_true(
            player.get("starting")
        ):
            away_starters.append(
                name
            )

        else:
            away_substitutes.append(
                name
            )

    if (
        len(home_starters) != 11
        or len(away_starters) != 11
    ):
        return None

    if (
        not home_substitutes
        or not away_substitutes
    ):
        return None

    return MatchLineup(
        league="MLS",
        home_team=TeamLineup(
            team_name=(
                home.get("team_name")
                or "Heimteam"
            ),
            starters=home_starters,
            substitutes=home_substitutes,
        ),
        away_team=TeamLineup(
            team_name=(
                away.get("team_name")
                or "Auswärtsteam"
            ),
            starters=away_starters,
            substitutes=away_substitutes,
        ),
        match_url=url,
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    print("")
    print(
        "============================================"
    )
    print(
        "🇺🇸 MLS SPIELPLAN TEST"
    )
    print(
        "============================================"
    )
    print("")

    matches = (
        get_mls_upcoming_matches(
            days=3
        )
    )

    print(
        f"Gefundene Spiele: "
        f"{len(matches)}"
    )

    print("")

    if not matches:
        print(
            "❌ Keine kommenden "
            "MLS-Spiele gefunden."
        )

    else:
        for index, match in enumerate(
            matches,
            start=1,
        ):
            kickoff = (
                match["kickoff"]
            )

            print(
                f"{index}. "
                f"{match['home_team']} "
                f"vs "
                f"{match['away_team']}"
            )

            print(
                f"   🕒 "
                f"{kickoff.strftime('%d.%m.%Y %H:%M')}"
            )

            print(
                f"   ID: "
                f"{match['match_id']}"
            )

            print("")

    print(
        "============================================"
    )
    print(
        "🏁 FERTIG"
    )
    print(
        "============================================"
    )
    print("")