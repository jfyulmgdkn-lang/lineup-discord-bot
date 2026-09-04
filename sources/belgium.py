from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from models import TeamLineup, MatchLineup


# ============================================================
# KONFIGURATION
# ============================================================

ESPN_BASE = (
    "https://site.api.espn.com/"
    "apis/site/v2/sports/soccer/bel.1"
)

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
# EVENT-ID
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

    home_team = _team_name(
        home
    )

    away_team = _team_name(
        away
    )

    return {
        "kickoff": kickoff,
        "home_team": home_team,
        "away_team": away_team,
        "event_id": event_id,
        "url": event_id,
    }


# ============================================================
# SPIELPLAN
# ============================================================

def get_belgium_upcoming_matches(
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
        f"{ESPN_BASE}/scoreboard",
        params={
            "dates": date_range,
            "limit": 100,
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
# ROSTER PARSEN
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
# AUFSTELLUNG
# ============================================================

def get_belgium_lineup(
    match_id,
):

    event_id = _extract_event_id(
        match_id
    )

    data = _get_json(
        f"{ESPN_BASE}/summary",
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
        league="Jupiler Pro League",
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
# TEST
# ============================================================

if __name__ == "__main__":

    print("")
    print(
        "============================================"
    )
    print(
        "🇧🇪 JUPILER PRO LEAGUE TEST"
    )
    print(
        "============================================"
    )
    print("")

    # ========================================================
    # SPIELPLAN
    # ========================================================

    print(
        "📅 SPIELPLAN TEST"
    )
    print(
        "--------------------------------------------"
    )

    try:

        matches = (
            get_belgium_upcoming_matches(
                10
            )
        )

        print(
            f"Gefundene Spiele: "
            f"{len(matches)}"
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

    except Exception as error:

        print(
            "❌ Spielplan-Fehler: "
            f"{error}"
        )

    # ========================================================
    # AUFSTELLUNG
    #
    # Hier nehmen wir automatisch ein kürzlich
    # abgeschlossenes Spiel.
    #
    # Dadurch brauchen wir keine fest eingetragene
    # Test-ID.
    # ========================================================

    print("")
    print(
        "👕 AUFSTELLUNG TEST"
    )
    print(
        "--------------------------------------------"
    )

    try:

        now = datetime.now(
            BERLIN_TIMEZONE
        )

        start_date = (
            now
            - timedelta(
                days=30
            )
        )

        end_date = now

        date_range = (
            f"{start_date.strftime('%Y%m%d')}"
            "-"
            f"{end_date.strftime('%Y%m%d')}"
        )

        data = _get_json(
            f"{ESPN_BASE}/scoreboard",
            params={
                "dates": date_range,
                "limit": 100,
            },
        )

        test_event_id = None

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

                lineup = (
                    get_belgium_lineup(
                        event_id
                    )
                )

                test_event_id = (
                    event_id
                )

                break

            except Exception:

                continue

        if not test_event_id:

            raise ValueError(
                "Kein abgeschlossenes Spiel "
                "mit vollständiger Aufstellung "
                "in den letzten 30 Tagen gefunden."
            )

        print(
            f"Test-ID: {test_event_id}"
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

    except Exception as error:

        print("")
        print(
            "❌ Aufstellungs-Fehler: "
            f"{error}"
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