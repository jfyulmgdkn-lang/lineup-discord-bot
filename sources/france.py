from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from models import TeamLineup, MatchLineup


# ============================================================
# KONFIGURATION
# ============================================================

BERLIN_TIMEZONE = ZoneInfo("Europe/Berlin")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/152.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

COMPETITIONS = {
    "ligue1": {
        "league_code": "fra.1",
        "league_name": "Ligue 1",
    },
    "ligue2": {
        "league_code": "fra.2",
        "league_name": "Ligue 2",
    },
}


# ============================================================
# ESPN
# ============================================================

def _espn_base(league_code):

    return (
        "https://site.api.espn.com/"
        "apis/site/v2/sports/soccer/"
        f"{league_code}"
    )


def _get_json(url, params=None):

    response = requests.get(
        url,
        params=params,
        headers=HEADERS,
        timeout=20,
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# EVENT-ID
# ============================================================

def _extract_event_id(value):

    value = str(value).strip()

    if value.isdigit():

        return value

    marker = "/gameId/"

    if marker in value:

        event_id = (
            value
            .split(marker, 1)[1]
            .split("/", 1)[0]
        )

        if event_id.isdigit():

            return event_id

    raise ValueError(
        "Ungültige ESPN-Match-ID oder URL."
    )


# ============================================================
# TEAMNAME
# ============================================================

def _team_name(competitor):

    team = competitor.get(
        "team",
        {},
    )

    return (
        team.get("displayName")
        or team.get("shortDisplayName")
        or team.get("name")
        or "Unbekannt"
    )


# ============================================================
# EVENT
# ============================================================

def _parse_event(event):

    event_id = str(
        event.get(
            "id",
            "",
        )
    )

    if not event_id:

        raise ValueError(
            "ESPN Event-ID fehlt."
        )

    date_text = event.get("date")

    if not date_text:

        raise ValueError(
            "Anstoßzeit fehlt."
        )

    kickoff = datetime.fromisoformat(
        date_text.replace(
            "Z",
            "+00:00",
        )
    ).astimezone(
        BERLIN_TIMEZONE
    )

    competitions = event.get(
        "competitions",
        [],
    )

    if not competitions:

        raise ValueError(
            "Competition-Daten fehlen."
        )

    competitors = competitions[0].get(
        "competitors",
        [],
    )

    home = None
    away = None

    for competitor in competitors:

        home_away = competitor.get(
            "homeAway"
        )

        if home_away == "home":

            home = competitor

        elif home_away == "away":

            away = competitor

    if home is None or away is None:

        raise ValueError(
            "Heim- oder Auswärtsteam fehlt."
        )

    return {
        "kickoff": kickoff,
        "home_team": _team_name(home),
        "away_team": _team_name(away),
        "event_id": event_id,
        "url": event_id,
    }


# ============================================================
# SPIELPLAN
# ============================================================

def _get_upcoming_matches(
    league_code,
    days=2,
):

    now = datetime.now(
        BERLIN_TIMEZONE
    )

    start_time = (
        now
        - timedelta(minutes=30)
    )

    end_time = (
        now
        + timedelta(days=days)
    )

    start_date = (
        now
        - timedelta(days=1)
    )

    end_date = (
        now
        + timedelta(days=days + 1)
    )

    date_range = (
        f"{start_date.strftime('%Y%m%d')}"
        "-"
        f"{end_date.strftime('%Y%m%d')}"
    )

    data = _get_json(
        f"{_espn_base(league_code)}/scoreboard",
        params={
            "dates": date_range,
            "limit": 200,
        },
    )

    matches = []

    for event in data.get(
        "events",
        [],
    ):

        try:

            match = _parse_event(
                event
            )

        except Exception:

            continue

        kickoff = match[
            "kickoff"
        ]

        if kickoff < start_time:

            continue

        if kickoff > end_time:

            continue

        matches.append(
            match
        )

    matches.sort(
        key=lambda item: item[
            "kickoff"
        ]
    )

    return matches


def get_ligue1_upcoming_matches(
    days=2,
):

    return _get_upcoming_matches(
        "fra.1",
        days,
    )


def get_ligue2_upcoming_matches(
    days=2,
):

    return _get_upcoming_matches(
        "fra.2",
        days,
    )


# ============================================================
# SPIELER
# ============================================================

def _player_name(player):

    athlete = player.get(
        "athlete",
        {},
    )

    if isinstance(
        athlete,
        dict,
    ):

        name = (
            athlete.get("displayName")
            or athlete.get("shortName")
            or athlete.get("fullName")
        )

        if name:

            return str(
                name
            ).strip()

    name = (
        player.get("displayName")
        or player.get("name")
    )

    if name:

        return str(
            name
        ).strip()

    return ""


def _is_starter(player):

    starter = player.get(
        "starter"
    )

    if starter is True:

        return True

    if isinstance(
        starter,
        str,
    ):

        if starter.lower() == "true":

            return True

    starter = player.get(
        "isStarter"
    )

    if starter is True:

        return True

    if isinstance(
        starter,
        str,
    ):

        if starter.lower() == "true":

            return True

    return False


# ============================================================
# ROSTER
# ============================================================

def _parse_roster_team(
    roster_block,
):

    team = roster_block.get(
        "team",
        {},
    )

    team_name = (
        team.get("displayName")
        or team.get("shortDisplayName")
        or team.get("name")
        or "Unbekannt"
    )

    players = (
        roster_block.get("roster")
        or roster_block.get("athletes")
        or []
    )

    starters = []
    substitutes = []

    for player in players:

        name = _player_name(
            player
        )

        if not name:

            continue

        if _is_starter(
            player
        ):

            if name not in starters:

                starters.append(
                    name
                )

        else:

            if name not in substitutes:

                substitutes.append(
                    name
                )

    return {
        "team_name": team_name,
        "home_away": roster_block.get(
            "homeAway"
        ),
        "starters": starters,
        "substitutes": substitutes,
    }


# ============================================================
# AUFSTELLUNG
# ============================================================

def _get_lineup(
    league_code,
    league_name,
    match_id,
):

    event_id = _extract_event_id(
        match_id
    )

    data = _get_json(
        f"{_espn_base(league_code)}/summary",
        params={
            "event": event_id,
        },
    )

    rosters = data.get(
        "rosters",
        [],
    )

    if not rosters:

        raise ValueError(
            "Aufstellung noch nicht verfügbar."
        )

    parsed_teams = [
        _parse_roster_team(roster)
        for roster in rosters
    ]

    home = None
    away = None

    for team in parsed_teams:

        if team["home_away"] == "home":

            home = team

        elif team["home_away"] == "away":

            away = team

    # ESPN liefert bei Fußball teilweise kein homeAway
    # direkt im Roster. Dann verwenden wir die Reihenfolge.
    if home is None or away is None:

        if len(parsed_teams) >= 2:

            home = parsed_teams[0]
            away = parsed_teams[1]

    if home is None or away is None:

        raise ValueError(
            "Mannschaften nicht erkannt."
        )

    if len(
        home["starters"]
    ) != 11:

        raise ValueError(
            "Heim-Startelf unvollständig: "
            f"{len(home['starters'])} Spieler."
        )

    if len(
        away["starters"]
    ) != 11:

        raise ValueError(
            "Auswärts-Startelf unvollständig: "
            f"{len(away['starters'])} Spieler."
        )

    if not home[
        "substitutes"
    ]:

        raise ValueError(
            "Heim-Bank fehlt."
        )

    if not away[
        "substitutes"
    ]:

        raise ValueError(
            "Auswärts-Bank fehlt."
        )

    return MatchLineup(
        league=league_name,

        home_team=TeamLineup(
            team_name=home[
                "team_name"
            ],
            starters=home[
                "starters"
            ],
            substitutes=home[
                "substitutes"
            ],
        ),

        away_team=TeamLineup(
            team_name=away[
                "team_name"
            ],
            starters=away[
                "starters"
            ],
            substitutes=away[
                "substitutes"
            ],
        ),

        match_url=(
            "https://www.espn.com/"
            "soccer/match/_/gameId/"
            f"{event_id}"
        ),
    )


def get_ligue1_lineup(
    match_id,
):

    return _get_lineup(
        "fra.1",
        "Ligue 1",
        match_id,
    )


def get_ligue2_lineup(
    match_id,
):

    return _get_lineup(
        "fra.2",
        "Ligue 2",
        match_id,
    )


# ============================================================
# TEST: LETZTE VOLLSTÄNDIGE AUFSTELLUNG FINDEN
# ============================================================

def _find_recent_lineup(
    league_code,
    league_name,
):

    now = datetime.now(
        BERLIN_TIMEZONE
    )

    # Wir suchen bis zu 90 Tage zurück.
    # Dadurch sollten wir für beide Ligen sicher
    # ein abgeschlossenes Spiel finden.
    for days_back in (
        30,
        60,
        90,
    ):

        start_date = (
            now
            - timedelta(
                days=days_back
            )
        )

        date_range = (
            f"{start_date.strftime('%Y%m%d')}"
            "-"
            f"{now.strftime('%Y%m%d')}"
        )

        data = _get_json(
            f"{_espn_base(league_code)}/scoreboard",
            params={
                "dates": date_range,
                "limit": 500,
            },
        )

        events = data.get(
            "events",
            [],
        )

        for event in reversed(
            events
        ):

            event_id = str(
                event.get(
                    "id",
                    "",
                )
            )

            if not event_id:

                continue

            try:

                lineup = _get_lineup(
                    league_code,
                    league_name,
                    event_id,
                )

                return (
                    event_id,
                    lineup,
                )

            except Exception:

                continue

    return (
        None,
        None,
    )


# ============================================================
# TEST-AUSGABE
# ============================================================

def _print_schedule(
    league_name,
    matches,
):

    print("")
    print(
        f"📅 {league_name} SPIELPLAN TEST"
    )
    print(
        "--------------------------------------------"
    )

    print(
        f"Gefundene Spiele: {len(matches)}"
    )

    print("")

    for index, match in enumerate(
        matches,
        start=1,
    ):

        print(
            f"{index}. "
            f"{match['home_team']} "
            f"vs. "
            f"{match['away_team']}"
        )

        print(
            "   🕒 "
            f"{match['kickoff'].strftime('%d.%m.%Y %H:%M')}"
        )

        print(
            "   ESPN-ID: "
            f"{match['event_id']}"
        )

        print("")


def _print_lineup(
    event_id,
    lineup,
):

    print(
        f"Test-ID: {event_id}"
    )

    print("")

    print(
        f"🏠 {lineup.home_team.team_name}"
    )

    print("")

    print(
        "STARTELF "
        f"({len(lineup.home_team.starters)}):"
    )

    for player in (
        lineup.home_team.starters
    ):

        print(
            f"• {player}"
        )

    print("")

    print(
        "BANK "
        f"({len(lineup.home_team.substitutes)}):"
    )

    for player in (
        lineup.home_team.substitutes
    ):

        print(
            f"• {player}"
        )

    print("")

    print(
        f"✈️ {lineup.away_team.team_name}"
    )

    print("")

    print(
        "STARTELF "
        f"({len(lineup.away_team.starters)}):"
    )

    for player in (
        lineup.away_team.starters
    ):

        print(
            f"• {player}"
        )

    print("")

    print(
        "BANK "
        f"({len(lineup.away_team.substitutes)}):"
    )

    for player in (
        lineup.away_team.substitutes
    ):

        print(
            f"• {player}"
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
        "🇫🇷 FRANKREICH TEST"
    )
    print(
        "============================================"
    )

    # ========================================================
    # LIGUE 1
    # ========================================================

    print("")
    print(
        "============================================"
    )
    print(
        "🇫🇷 LIGUE 1"
    )
    print(
        "============================================"
    )

    try:

        matches = (
            get_ligue1_upcoming_matches(
                10
            )
        )

        _print_schedule(
            "LIGUE 1",
            matches,
        )

    except Exception as error:

        print(
            f"❌ Spielplan-Fehler: {error}"
        )

    print("")
    print(
        "👕 AUFSTELLUNG TEST"
    )
    print(
        "--------------------------------------------"
    )

    try:

        event_id, lineup = (
            _find_recent_lineup(
                "fra.1",
                "Ligue 1",
            )
        )

        if lineup is None:

            raise ValueError(
                "Kein Spiel mit vollständiger "
                "Aufstellung gefunden."
            )

        _print_lineup(
            event_id,
            lineup,
        )

    except Exception as error:

        print(
            f"❌ Aufstellungs-Fehler: {error}"
        )

    # ========================================================
    # LIGUE 2
    # ========================================================

    print("")
    print(
        "============================================"
    )
    print(
        "🇫🇷 LIGUE 2"
    )
    print(
        "============================================"
    )

    try:

        matches = (
            get_ligue2_upcoming_matches(
                10
            )
        )

        _print_schedule(
            "LIGUE 2",
            matches,
        )

    except Exception as error:

        print(
            f"❌ Spielplan-Fehler: {error}"
        )

    print("")
    print(
        "👕 AUFSTELLUNG TEST"
    )
    print(
        "--------------------------------------------"
    )

    try:

        event_id, lineup = (
            _find_recent_lineup(
                "fra.2",
                "Ligue 2",
            )
        )

        if lineup is None:

            raise ValueError(
                "Kein Spiel mit vollständiger "
                "Aufstellung gefunden."
            )

        _print_lineup(
            event_id,
            lineup,
        )

    except Exception as error:

        print(
            f"❌ Aufstellungs-Fehler: {error}"
        )

    print("")
    print(
        "============================================"
    )
    print(
        "🏁 FRANKREICH TEST FERTIG"
    )
    print(
        "============================================"
    )