from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from models import MatchLineup, TeamLineup


# ============================================================
# PREMIER LEAGUE API
# ============================================================

API_BASE = (
    "https://sdp-prem-prod."
    "premier-league-prod.pulselive.com"
)

COMPETITION_ID = 8
SEASON_ID = 2026

LONDON_TIMEZONE = ZoneInfo(
    "Europe/London"
)

BERLIN_TIMEZONE = ZoneInfo(
    "Europe/Berlin"
)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/152.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


# ============================================================
# API REQUEST
# ============================================================

def api_get(
    path: str,
    params=None,
):

    response = requests.get(
        API_BASE + path,
        headers=HEADERS,
        params=params,
        timeout=20,
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# TEXT
# ============================================================

def clean_text(
    value,
):

    if value is None:
        return ""

    return " ".join(
        str(value).split()
    ).strip()


# ============================================================
# SPIELERNAME
# ============================================================

def get_player_name(
    player,
):

    if not isinstance(
        player,
        dict,
    ):
        return ""

    known_name = clean_text(
        player.get(
            "knownName"
        )
    )

    if known_name:
        return known_name

    first_name = clean_text(
        player.get(
            "firstName"
        )
    )

    last_name = clean_text(
        player.get(
            "lastName"
        )
    )

    return clean_text(
        f"{first_name} {last_name}"
    )


# ============================================================
# TEAMNAME
# ============================================================

def get_team_name(
    team,
):

    if not isinstance(
        team,
        dict,
    ):
        return ""

    for key in [
        "name",
        "shortName",
        "clubName",
        "abbr",
    ]:

        value = clean_text(
            team.get(
                key
            )
        )

        if value:
            return value

    return ""


# ============================================================
# MATCH-ID AUS URL
# ============================================================

def get_match_id_from_url(
    match_url: str,
):

    parts = (
        match_url
        .strip("/")
        .split("/")
    )

    try:

        index = parts.index(
            "match"
        )

        return int(
            parts[
                index + 1
            ]
        )

    except Exception:

        raise ValueError(
            "Premier-League-Match-ID konnte "
            "nicht aus der URL gelesen werden."
        )


# ============================================================
# WEB URL
# ============================================================

def create_match_url(
    match_id,
):

    return (
        "https://www.premierleague.com/"
        f"en/match/{match_id}"
    )


# ============================================================
# MATCHDETAILS
# ============================================================

def get_match_detail(
    match_id,
):

    return api_get(
        f"/api/v2/matches/{match_id}"
    )


# ============================================================
# LINEUP
# ============================================================

def get_lineup_data(
    match_id,
):

    return api_get(
        f"/api/v3/matches/{match_id}/lineups"
    )


# ============================================================
# HOME / AWAY
# ============================================================

def get_side(
    data,
    side,
):

    if not isinstance(
        data,
        dict,
    ):
        return None

    side = (
        side
        .lower()
        .replace("_", "")
        .replace("-", "")
    )

    for key, value in data.items():

        normalized = (
            str(key)
            .lower()
            .replace("_", "")
            .replace("-", "")
        )

        if normalized in {
            side,
            side + "team",
        }:

            if isinstance(
                value,
                dict,
            ):

                return value

    for value in data.values():

        if isinstance(
            value,
            dict,
        ):

            result = get_side(
                value,
                side,
            )

            if result is not None:
                return result

        elif isinstance(
            value,
            list,
        ):

            for item in value:

                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                result = get_side(
                    item,
                    side,
                )

                if result is not None:
                    return result

    return None


# ============================================================
# SPIELER
# ============================================================

def get_players(
    team_data,
):

    if not isinstance(
        team_data,
        dict,
    ):
        return []

    players = team_data.get(
        "players"
    )

    if isinstance(
        players,
        list,
    ):

        return players

    for value in team_data.values():

        if isinstance(
            value,
            dict,
        ):

            result = get_players(
                value
            )

            if result:
                return result

    return []


# ============================================================
# STARTELF / BANK
# ============================================================

def split_players(
    players,
):

    starters = []
    substitutes = []

    if not isinstance(
        players,
        list,
    ):

        return (
            starters,
            substitutes,
        )

    for player in players:

        if not isinstance(
            player,
            dict,
        ):
            continue

        name = get_player_name(
            player
        )

        if not name:
            continue

        position = clean_text(
            player.get(
                "position"
            )
        ).lower()

        if position == "substitute":

            if name not in substitutes:

                substitutes.append(
                    name
                )

        else:

            if name not in starters:

                starters.append(
                    name
                )

    return (
        starters,
        substitutes,
    )


# ============================================================
# AUFSTELLUNG
# ============================================================

def get_premierleague_lineup(
    match_url: str,
) -> MatchLineup:

    match_id = get_match_id_from_url(
        match_url
    )

    match_data = get_match_detail(
        match_id
    )

    home_name = get_team_name(
        match_data.get(
            "homeTeam",
            {},
        )
    )

    away_name = get_team_name(
        match_data.get(
            "awayTeam",
            {},
        )
    )

    try:

        lineup_data = get_lineup_data(
            match_id
        )

    except requests.HTTPError as error:

        status = None

        if error.response is not None:

            status = (
                error.response.status_code
            )

        if status in {
            400,
            404,
        }:

            raise ValueError(
                "Die offizielle Premier-League-"
                "Aufstellung wurde noch nicht "
                "veröffentlicht."
            )

        raise

    home_lineup = get_side(
        lineup_data,
        "home_team",
    )

    if home_lineup is None:

        home_lineup = get_side(
            lineup_data,
            "home",
        )

    away_lineup = get_side(
        lineup_data,
        "away_team",
    )

    if away_lineup is None:

        away_lineup = get_side(
            lineup_data,
            "away",
        )

    if home_lineup is None:

        raise ValueError(
            "Heim-Aufstellung konnte "
            "nicht gefunden werden."
        )

    if away_lineup is None:

        raise ValueError(
            "Auswärts-Aufstellung konnte "
            "nicht gefunden werden."
        )

    home_players = get_players(
        home_lineup
    )

    away_players = get_players(
        away_lineup
    )

    (
        home_starters,
        home_substitutes,
    ) = split_players(
        home_players
    )

    (
        away_starters,
        away_substitutes,
    ) = split_players(
        away_players
    )

    if len(
        home_starters
    ) != 11:

        raise ValueError(
            f"{home_name}: "
            f"Startelf hat "
            f"{len(home_starters)}/11 Spieler."
        )

    if len(
        away_starters
    ) != 11:

        raise ValueError(
            f"{away_name}: "
            f"Startelf hat "
            f"{len(away_starters)}/11 Spieler."
        )

    if not home_substitutes:

        raise ValueError(
            f"{home_name}: Bank fehlt."
        )

    if not away_substitutes:

        raise ValueError(
            f"{away_name}: Bank fehlt."
        )

    return MatchLineup(
        league="Premier League",

        home_team=TeamLineup(
            team_name=home_name,
            starters=home_starters,
            substitutes=home_substitutes,
        ),

        away_team=TeamLineup(
            team_name=away_name,
            starters=away_starters,
            substitutes=away_substitutes,
        ),

        match_url=create_match_url(
            match_id
        ),
    )


# ============================================================
# KICKOFF
# ============================================================

def parse_kickoff(
    value,
):

    if not value:
        return None

    if isinstance(
        value,
        dict,
    ):

        for key in [
            "datetime",
            "dateTime",
            "label",
            "date",
            "utc",
        ]:

            nested = value.get(
                key
            )

            if nested:

                return parse_kickoff(
                    nested
                )

        return None

    if not isinstance(
        value,
        str,
    ):

        return None

    value = value.strip()

    # --------------------------------------------------------
    # API liefert explizites UTC
    # --------------------------------------------------------

    if value.endswith(
        "Z"
    ):

        try:

            kickoff = datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00",
                )
            )

            kickoff = kickoff.astimezone(
                BERLIN_TIMEZONE
            )

            return kickoff.replace(
                tzinfo=None
            )

        except ValueError:

            return None

    # --------------------------------------------------------
    # ISO mit Zeitzonenoffset
    # --------------------------------------------------------

    try:

        kickoff = datetime.fromisoformat(
            value
        )

    except ValueError:

        return None

    if kickoff.tzinfo is not None:

        kickoff = kickoff.astimezone(
            BERLIN_TIMEZONE
        )

        return kickoff.replace(
            tzinfo=None
        )

    # --------------------------------------------------------
    # Falls API eine naive UK-Uhrzeit liefert
    # --------------------------------------------------------

    kickoff = kickoff.replace(
        tzinfo=LONDON_TIMEZONE
    )

    kickoff = kickoff.astimezone(
        BERLIN_TIMEZONE
    )

    return kickoff.replace(
        tzinfo=None
    )


# ============================================================
# MATCHLISTE
# ============================================================

def extract_matches(
    data,
):

    if isinstance(
        data,
        list,
    ):
        return data

    if not isinstance(
        data,
        dict,
    ):
        return []

    for key in [
        "data",
        "content",
        "matches",
        "results",
    ]:

        value = data.get(
            key
        )

        if isinstance(
            value,
            list,
        ):

            return value

    return []


def get_match_id(
    match,
):

    for key in [
        "matchId",
        "id",
    ]:

        value = match.get(
            key
        )

        if value:

            try:

                return int(
                    value
                )

            except Exception:
                pass

    return None


def get_match_kickoff(
    match,
):

    for key in [
        "kickoff",
        "kickoffTime",
        "date",
        "dateTime",
    ]:

        kickoff = parse_kickoff(
            match.get(
                key
            )
        )

        if kickoff:
            return kickoff

    return None


def get_match_teams(
    match,
):

    return (
        get_team_name(
            match.get(
                "homeTeam",
                {},
            )
        ),
        get_team_name(
            match.get(
                "awayTeam",
                {},
            )
        ),
    )


# ============================================================
# KOMMENDE SPIELE
# ============================================================

def get_premierleague_upcoming_matches(
    days_ahead: int = 2,
):

    now = datetime.now()

    start_date = (
        now.date()
        - timedelta(
            days=1
        )
    )

    end_date = (
        now.date()
        + timedelta(
            days=days_ahead + 1
        )
    )

    params = {
        "competition": COMPETITION_ID,
        "season": SEASON_ID,
        "_limit": 100,
        "_sort": "kickoff:asc",
        "kickoff>": (
            start_date.isoformat()
        ),
        "kickoff<": (
            end_date.isoformat()
        ),
    }

    data = api_get(
        "/api/v2/matches",
        params=params,
    )

    matches = extract_matches(
        data
    )

    allowed_dates = {
        (
            now
            + timedelta(
                days=offset
            )
        ).date()

        for offset in range(
            days_ahead + 1
        )
    }

    results = []

    for match in matches:

        if not isinstance(
            match,
            dict,
        ):
            continue

        match_id = get_match_id(
            match
        )

        kickoff = get_match_kickoff(
            match
        )

        if not match_id:
            continue

        if kickoff is None:
            continue

        if (
            kickoff.date()
            not in allowed_dates
        ):
            continue

        (
            home_name,
            away_name,
        ) = get_match_teams(
            match
        )

        if not home_name:
            continue

        if not away_name:
            continue

        results.append(
            {
                "kickoff": kickoff,
                "home_team": home_name,
                "away_team": away_name,
                "url": create_match_url(
                    match_id
                ),
                "match_id": match_id,
            }
        )

    results.sort(
        key=lambda item:
        item["kickoff"]
    )

    return results


# ============================================================
# TERMINAL TEST
# ============================================================

if __name__ == "__main__":

    print("")
    print(
        "============================================"
    )
    print(
        "🏴 PREMIER LEAGUE TEST"
    )
    print(
        "============================================"
    )
    print("")

    TEST_MATCH_ID = 2561895

    try:

        lineup = get_premierleague_lineup(
            create_match_url(
                TEST_MATCH_ID
            )
        )

        print(
            f"🏠 {lineup.home_team.team_name}"
        )

        print(
            f"Startelf: "
            f"{len(lineup.home_team.starters)}"
        )

        print(
            f"Bank: "
            f"{len(lineup.home_team.substitutes)}"
        )

        print("")

        print(
            f"✈️ {lineup.away_team.team_name}"
        )

        print(
            f"Startelf: "
            f"{len(lineup.away_team.starters)}"
        )

        print(
            f"Bank: "
            f"{len(lineup.away_team.substitutes)}"
        )

        print("")
        print(
            "✅ LINEUP OK"
        )

    except Exception as error:

        print(
            f"❌ LINEUP: {error}"
        )

    print("")
    print(
        "============================================"
    )
    print(
        "AKTUELLE SPIELE – DEUTSCHE ZEIT"
    )
    print(
        "============================================"
    )
    print("")

    try:

        matches = (
            get_premierleague_upcoming_matches(
                3
            )
        )

        print(
            f"✅ {len(matches)} "
            "Spiele gefunden."
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
                "   🆔 "
                f"{match['match_id']}"
            )

            print("")

    except Exception as error:

        print(
            f"❌ SPIELPLAN: {error}"
        )

    print("")