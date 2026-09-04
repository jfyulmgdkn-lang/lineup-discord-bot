from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from models import TeamLineup, MatchLineup


# ============================================================
# KONFIGURATION
# ============================================================

BERLIN_TIMEZONE = ZoneInfo(
    "Europe/Berlin"
)

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
    "uefa_cl": {
        "league_code": "uefa.champions",
        "league_name": "Champions League",
        "flag": "🇪🇺",
    },

    "uefa_el": {
        "league_code": "uefa.europa",
        "league_name": "Europa League",
        "flag": "🇪🇺",
    },

    "uefa_ecl": {
        "league_code": "uefa.europa.conf",
        "league_name": "Conference League",
        "flag": "🇪🇺",
    },
}


# ============================================================
# ESPN BASE URL
# ============================================================

def _espn_base(
    league_code,
):

    return (
        "https://site.api.espn.com/"
        "apis/site/v2/sports/soccer/"
        f"{league_code}"
    )


# ============================================================
# HTTP
# ============================================================

def _get_json(
    url,
    params=None,
):

    response = requests.get(
        url,
        params=params,
        headers=HEADERS,
        timeout=20,
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# EVENT ID
# ============================================================

def _extract_event_id(
    value,
):

    value = str(
        value
    ).strip()

    if value.isdigit():

        return value

    marker = "/gameId/"

    if marker in value:

        after = value.split(
            marker,
            1,
        )[1]

        event_id = (
            after.split(
                "/",
                1,
            )[0]
        )

        if event_id.isdigit():

            return event_id

    raise ValueError(
        "Ungültige ESPN-Match-ID oder URL."
    )


# ============================================================
# TEAMNAME
# ============================================================

def _team_name(
    competitor,
):

    team = competitor.get(
        "team",
        {}
    )

    return (
        team.get("displayName")
        or team.get("shortDisplayName")
        or team.get("name")
        or "Unbekannt"
    )


# ============================================================
# EVENT PARSEN
# ============================================================

def _parse_event(
    event,
):

    event_id = str(
        event.get(
            "id",
            ""
        )
    )

    if not event_id:

        raise ValueError(
            "ESPN Event-ID fehlt."
        )

    date_text = event.get(
        "date"
    )

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
        []
    )

    if not competitions:

        raise ValueError(
            "Competition-Daten fehlen."
        )

    competitors = competitions[0].get(
        "competitors",
        []
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
        "home_team": _team_name(
            home
        ),
        "away_team": _team_name(
            away
        ),
        "event_id": event_id,
        "url": event_id,
    }


# ============================================================
# SPIELPLAN GENERISCH
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
        - timedelta(
            minutes=30
        )
    )

    end_time = (
        now
        + timedelta(
            days=days
        )
    )

    start_date = (
        now
        - timedelta(
            days=1
        )
    )

    end_date = (
        now
        + timedelta(
            days=days + 1
        )
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
        []
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


# ============================================================
# CHAMPIONS LEAGUE SPIELPLAN
# ============================================================

def get_uefa_cl_upcoming_matches(
    days=2,
):

    return _get_upcoming_matches(
        "uefa.champions",
        days,
    )


# ============================================================
# EUROPA LEAGUE SPIELPLAN
# ============================================================

def get_uefa_el_upcoming_matches(
    days=2,
):

    return _get_upcoming_matches(
        "uefa.europa",
        days,
    )


# ============================================================
# CONFERENCE LEAGUE SPIELPLAN
# ============================================================

def get_uefa_ecl_upcoming_matches(
    days=2,
):

    return _get_upcoming_matches(
        "uefa.europa.conf",
        days,
    )


# ============================================================
# SPIELERNAME
# ============================================================

def _player_name(
    player,
):

    athlete = player.get(
        "athlete",
        {}
    )

    if isinstance(
        athlete,
        dict,
    ):

        name = (
            athlete.get(
                "displayName"
            )
            or athlete.get(
                "shortName"
            )
            or athlete.get(
                "fullName"
            )
        )

        if name:

            return str(
                name
            ).strip()

    name = (
        player.get(
            "displayName"
        )
        or player.get(
            "name"
        )
    )

    if name:

        return str(
            name
        ).strip()

    return ""


# ============================================================
# STARTER
# ============================================================

def _is_starter(
    player,
):

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
# ROSTER TEAM
# ============================================================

def _parse_roster_team(
    roster_block,
):

    team = roster_block.get(
        "team",
        {}
    )

    team_name = (
        team.get(
            "displayName"
        )
        or team.get(
            "shortDisplayName"
        )
        or team.get(
            "name"
        )
        or "Unbekannt"
    )

    players = (
        roster_block.get(
            "roster"
        )
        or roster_block.get(
            "athletes"
        )
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
# AUFSTELLUNG GENERISCH
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
        []
    )

    if not rosters:

        raise ValueError(
            "Aufstellung noch nicht verfügbar."
        )

    parsed_teams = []

    for roster in rosters:

        parsed_teams.append(
            _parse_roster_team(
                roster
            )
        )

    home = None
    away = None

    for team in parsed_teams:

        if team[
            "home_away"
        ] == "home":

            home = team

        elif team[
            "home_away"
        ] == "away":

            away = team

    if (
        home is None
        or away is None
    ):

        if len(
            parsed_teams
        ) >= 2:

            home = (
                parsed_teams[0]
            )

            away = (
                parsed_teams[1]
            )

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


# ============================================================
# CHAMPIONS LEAGUE AUFSTELLUNG
# ============================================================

def get_uefa_cl_lineup(
    match_id,
):

    return _get_lineup(
        "uefa.champions",
        "Champions League",
        match_id,
    )


# ============================================================
# EUROPA LEAGUE AUFSTELLUNG
# ============================================================

def get_uefa_el_lineup(
    match_id,
):

    return _get_lineup(
        "uefa.europa",
        "Europa League",
        match_id,
    )


# ============================================================
# CONFERENCE LEAGUE AUFSTELLUNG
# ============================================================

def get_uefa_ecl_lineup(
    match_id,
):

    return _get_lineup(
        "uefa.europa.conf",
        "Conference League",
        match_id,
    )


# ============================================================
# TEST HELFER
# ============================================================

def _find_recent_lineup(
    league_code,
    league_name,
):

    now = datetime.now(
        BERLIN_TIMEZONE
    )

    start_date = (
        now
        - timedelta(
            days=180
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
        []
    )

    events = list(
        reversed(
            events
        )
    )

    for event in events:

        event_id = str(
            event.get(
                "id",
                ""
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
# TEST AUSGABE
# ============================================================

def _print_lineup(
    event_id,
    lineup,
):

    print(
        f"Test-ID: {event_id}"
    )

    print("")

    print(
        "🏠 "
        f"{lineup.home_team.team_name}"
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
        "✈️ "
        f"{lineup.away_team.team_name}"
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
        "🇪🇺 UEFA TEST"
    )
    print(
        "============================================"
    )

    # ========================================================
    # CHAMPIONS LEAGUE
    # ========================================================

    print("")
    print(
        "============================================"
    )
    print(
        "🏆 CHAMPIONS LEAGUE"
    )
    print(
        "============================================"
    )

    print("")
    print(
        "📅 SPIELPLAN TEST"
    )
    print(
        "--------------------------------------------"
    )

    try:

        matches = (
            get_uefa_cl_upcoming_matches(
                30
            )
        )

        print(
            f"Gefundene Spiele: "
            f"{len(matches)}"
        )

        for match in matches:

            print(
                f"• "
                f"{match['home_team']} "
                f"vs. "
                f"{match['away_team']} "
                f"| "
                f"{match['kickoff'].strftime('%d.%m.%Y %H:%M')} "
                f"| ID {match['event_id']}"
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
                "uefa.champions",
                "Champions League",
            )
        )

        if not lineup:

            raise ValueError(
                "Kein Testspiel mit "
                "vollständiger Aufstellung gefunden."
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
    # EUROPA LEAGUE
    # ========================================================

    print("")
    print(
        "============================================"
    )
    print(
        "🏆 EUROPA LEAGUE"
    )
    print(
        "============================================"
    )

    print("")
    print(
        "📅 SPIELPLAN TEST"
    )
    print(
        "--------------------------------------------"
    )

    try:

        matches = (
            get_uefa_el_upcoming_matches(
                30
            )
        )

        print(
            f"Gefundene Spiele: "
            f"{len(matches)}"
        )

        for match in matches:

            print(
                f"• "
                f"{match['home_team']} "
                f"vs. "
                f"{match['away_team']} "
                f"| "
                f"{match['kickoff'].strftime('%d.%m.%Y %H:%M')} "
                f"| ID {match['event_id']}"
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
                "uefa.europa",
                "Europa League",
            )
        )

        if not lineup:

            raise ValueError(
                "Kein Testspiel mit "
                "vollständiger Aufstellung gefunden."
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
    # CONFERENCE LEAGUE
    # ========================================================

    print("")
    print(
        "============================================"
    )
    print(
        "🏆 CONFERENCE LEAGUE"
    )
    print(
        "============================================"
    )

    print("")
    print(
        "📅 SPIELPLAN TEST"
    )
    print(
        "--------------------------------------------"
    )

    try:

        matches = (
            get_uefa_ecl_upcoming_matches(
                30
            )
        )

        print(
            f"Gefundene Spiele: "
            f"{len(matches)}"
        )

        for match in matches:

            print(
                f"• "
                f"{match['home_team']} "
                f"vs. "
                f"{match['away_team']} "
                f"| "
                f"{match['kickoff'].strftime('%d.%m.%Y %H:%M')} "
                f"| ID {match['event_id']}"
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
                "uefa.europa.conf",
                "Conference League",
            )
        )

        if not lineup:

            raise ValueError(
                "Kein Testspiel mit "
                "vollständiger Aufstellung gefunden."
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
        "🏁 UEFA TEST FERTIG"
    )
    print(
        "============================================"
    )