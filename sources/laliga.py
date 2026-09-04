import json
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

from models import MatchLineup, TeamLineup


# ============================================================
# LALIGA
# ============================================================

LALIGA_HOME_URL = (
    "https://www.laliga.com/en-GB/laliga-easports"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/152.0.0.0 Safari/537.36"
    ),
    "Accept-Language": (
        "en-GB,en;q=0.9"
    ),
}


# ============================================================
# TESTSPIEL
# ============================================================

TEST_URL = (
    "https://www.laliga.com/en-GB/match/"
    "temporada-2025-2026-laliga-ea-sports-"
    "real-betis-real-madrid-32"
)


# ============================================================
# DOWNLOAD
# ============================================================

def download_page(
    url,
):

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=20,
    )

    response.raise_for_status()

    return response.text


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
# NEXT DATA
# ============================================================

def get_next_data_from_html(
    html,
):

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    script = soup.find(
        "script",
        id="__NEXT_DATA__",
    )

    if script is None:

        raise ValueError(
            "__NEXT_DATA__ wurde "
            "nicht gefunden."
        )

    text = (
        script.string
        or script.get_text()
        or ""
    ).strip()

    if not text:

        raise ValueError(
            "__NEXT_DATA__ ist leer."
        )

    return json.loads(
        text
    )


def get_next_data(
    url,
):

    html = download_page(
        url
    )

    return get_next_data_from_html(
        html
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
        "nickname",
        "boundname",
        "name",
        "shortname",
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
# SPIELERNAME
# ============================================================

def get_player_name(
    entry,
):

    if not isinstance(
        entry,
        dict,
    ):

        return ""

    person = entry.get(
        "person",
        {},
    )

    if not isinstance(
        person,
        dict,
    ):

        return ""

    # --------------------------------------------------------
    # Bevorzugt den offiziellen Kurznamen
    # --------------------------------------------------------

    nickname = clean_text(
        person.get(
            "nickname"
        )
    )

    if nickname:
        return nickname

    # --------------------------------------------------------
    # Vollständiger Name
    # --------------------------------------------------------

    name = clean_text(
        person.get(
            "name"
        )
    )

    if name:
        return name

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    firstname = clean_text(
        person.get(
            "firstname"
        )
    )

    lastname = clean_text(
        person.get(
            "lastname"
        )
    )

    return clean_text(
        f"{firstname} {lastname}"
    )


# ============================================================
# SPIELERLISTE
# ============================================================

def parse_player_list(
    entries,
):

    players = []

    if not isinstance(
        entries,
        list,
    ):

        return players

    for entry in entries:

        name = get_player_name(
            entry
        )

        if not name:
            continue

        if name not in players:

            players.append(
                name
            )

    return players


# ============================================================
# MATCHDATEN
# ============================================================

def get_match_data(
    data,
):

    try:

        return (
            data[
                "props"
            ][
                "pageProps"
            ][
                "match"
            ]
        )

    except Exception:

        raise ValueError(
            "LaLiga-Matchdaten konnten "
            "nicht gefunden werden."
        )


# ============================================================
# LINEUPS
# ============================================================

def get_lineups_data(
    data,
):

    try:

        return (
            data[
                "props"
            ][
                "pageProps"
            ][
                "data"
            ][
                "lineups"
            ]
        )

    except Exception:

        raise ValueError(
            "Die offizielle LaLiga-"
            "Aufstellung wurde noch "
            "nicht veröffentlicht."
        )


# ============================================================
# AUFSTELLUNG
# ============================================================

def get_laliga_lineup(
    match_url: str,
) -> MatchLineup:

    data = get_next_data(
        match_url
    )

    match_data = get_match_data(
        data
    )

    # --------------------------------------------------------
    # Teams
    # --------------------------------------------------------

    home_name = get_team_name(
        match_data.get(
            "home_team",
            {},
        )
    )

    away_name = get_team_name(
        match_data.get(
            "away_team",
            {},
        )
    )

    if not home_name:

        raise ValueError(
            "LaLiga-Heimteam konnte "
            "nicht gelesen werden."
        )

    if not away_name:

        raise ValueError(
            "LaLiga-Auswärtsteam konnte "
            "nicht gelesen werden."
        )

    # --------------------------------------------------------
    # Lineups
    # --------------------------------------------------------

    lineups = get_lineups_data(
        data
    )

    home_data = lineups.get(
        "home",
        {},
    )

    away_data = lineups.get(
        "away",
        {},
    )

    if not isinstance(
        home_data,
        dict,
    ):

        raise ValueError(
            "Heim-Aufstellung fehlt."
        )

    if not isinstance(
        away_data,
        dict,
    ):

        raise ValueError(
            "Auswärts-Aufstellung fehlt."
        )

    # --------------------------------------------------------
    # Starter
    # --------------------------------------------------------

    home_starters = parse_player_list(
        home_data.get(
            "starts",
            [],
        )
    )

    away_starters = parse_player_list(
        away_data.get(
            "starts",
            [],
        )
    )

    # --------------------------------------------------------
    # Bank
    # --------------------------------------------------------

    home_substitutes = parse_player_list(
        home_data.get(
            "subs",
            [],
        )
    )

    away_substitutes = parse_player_list(
        away_data.get(
            "subs",
            [],
        )
    )

    # --------------------------------------------------------
    # Prüfung
    # --------------------------------------------------------

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
            f"{home_name}: "
            "Bank wurde noch nicht "
            "veröffentlicht."
        )

    if not away_substitutes:

        raise ValueError(
            f"{away_name}: "
            "Bank wurde noch nicht "
            "veröffentlicht."
        )

    # --------------------------------------------------------
    # Ergebnis
    # --------------------------------------------------------

    return MatchLineup(
        league="La Liga",

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

        match_url=match_url,
    )


# ============================================================
# MATCH-LINKS DER LALIGA-SEITE
# ============================================================

def get_laliga_match_links():

    html = download_page(
        LALIGA_HOME_URL
    )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    links = []

    for anchor in soup.find_all(
        "a",
        href=True,
    ):

        href = clean_text(
            anchor.get(
                "href"
            )
        )

        if not href:
            continue

        if "/match/" not in href:
            continue

        if (
            "laliga-ea-sports"
            not in href.lower()
        ):
            continue

        if href.startswith(
            "/"
        ):

            href = (
                "https://www.laliga.com"
                + href
            )

        if not href.startswith(
            "http"
        ):
            continue

        if href not in links:

            links.append(
                href
            )

    return links


# ============================================================
# KICKOFF EINES MATCHES
# ============================================================

def parse_match_kickoff(
    match_data,
):

    if not isinstance(
        match_data,
        dict,
    ):

        return None

    # --------------------------------------------------------
    # Mögliche Felder durchsuchen
    # --------------------------------------------------------

    possible_keys = [
        "date",
        "datetime",
        "date_time",
        "kickoff",
        "kickoff_time",
        "start_date",
        "startDate",
        "timestamp",
    ]

    for key in possible_keys:

        value = match_data.get(
            key
        )

        kickoff = parse_datetime_value(
            value
        )

        if kickoff:

            return kickoff

    # --------------------------------------------------------
    # Rekursiv eine Ebene tiefer
    # --------------------------------------------------------

    for value in match_data.values():

        if not isinstance(
            value,
            dict,
        ):
            continue

        for key in possible_keys:

            kickoff = parse_datetime_value(
                value.get(
                    key
                )
            )

            if kickoff:

                return kickoff

    return None


# ============================================================
# DATUM PARSEN
# ============================================================

def parse_datetime_value(
    value,
):

    if value is None:

        return None

    if isinstance(
        value,
        dict,
    ):

        for key in [
            "datetime",
            "date",
            "value",
        ]:

            if key in value:

                result = parse_datetime_value(
                    value[
                        key
                    ]
                )

                if result:

                    return result

        return None

    if isinstance(
        value,
        (
            int,
            float,
        ),
    ):

        try:

            # Millisekunden
            if value > 10_000_000_000:

                value = value / 1000

            return datetime.fromtimestamp(
                value
            )

        except Exception:

            return None

    if not isinstance(
        value,
        str,
    ):

        return None

    value = value.strip()

    if not value:

        return None

    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d.%m.%Y %H:%M",
        "%d/%m/%Y %H:%M",
    ]

    # --------------------------------------------------------
    # ISO
    # --------------------------------------------------------

    try:

        parsed = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )

        if parsed.tzinfo:

            parsed = parsed.astimezone()

            parsed = parsed.replace(
                tzinfo=None
            )

        return parsed

    except Exception:

        pass

    # --------------------------------------------------------
    # Andere Formate
    # --------------------------------------------------------

    for date_format in formats:

        try:

            return datetime.strptime(
                value,
                date_format,
            )

        except ValueError:

            continue

    return None


# ============================================================
# SPIELINFOS AUS MATCHSEITE
# ============================================================

def get_match_info_from_url(
    match_url,
):

    data = get_next_data(
        match_url
    )

    match_data = get_match_data(
        data
    )

    home_name = get_team_name(
        match_data.get(
            "home_team",
            {},
        )
    )

    away_name = get_team_name(
        match_data.get(
            "away_team",
            {},
        )
    )

    kickoff = parse_match_kickoff(
        match_data
    )

    return {
        "kickoff": kickoff,
        "home_team": home_name,
        "away_team": away_name,
        "url": match_url,
    }


# ============================================================
# KOMMENDE SPIELE
# ============================================================

def get_laliga_upcoming_matches(
    days_ahead: int = 2,
):

    now = datetime.now()

    links = get_laliga_match_links()

    results = []

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

    for match_url in links:

        try:

            match = get_match_info_from_url(
                match_url
            )

        except Exception:

            continue

        kickoff = match[
            "kickoff"
        ]

        if kickoff is None:

            continue

        if (
            kickoff.date()
            not in allowed_dates
        ):

            continue

        if not match[
            "home_team"
        ]:

            continue

        if not match[
            "away_team"
        ]:

            continue

        results.append(
            match
        )

    # --------------------------------------------------------
    # Duplikate entfernen
    # --------------------------------------------------------

    unique = {}

    for match in results:

        unique[
            match[
                "url"
            ]
        ] = match

    results = list(
        unique.values()
    )

    results.sort(
        key=lambda item:
        item[
            "kickoff"
        ]
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
        "🇪🇸 LA LIGA TEST"
    )
    print(
        "============================================"
    )
    print("")

    # ========================================================
    # LINEUP TEST
    # ========================================================

    try:

        lineup = get_laliga_lineup(
            TEST_URL
        )

        print(
            "✅ AUFSTELLUNG"
        )

        print("")

        print(
            f"🏠 "
            f"{lineup.home_team.team_name}"
        )

        print(
            f"   Startelf: "
            f"{len(lineup.home_team.starters)}"
        )

        print(
            f"   Bank: "
            f"{len(lineup.home_team.substitutes)}"
        )

        print("")

        for index, player in enumerate(
            lineup.home_team.starters,
            start=1,
        ):

            print(
                f"   {index}. {player}"
            )

        print("")
        print(
            f"✈️ "
            f"{lineup.away_team.team_name}"
        )

        print(
            f"   Startelf: "
            f"{len(lineup.away_team.starters)}"
        )

        print(
            f"   Bank: "
            f"{len(lineup.away_team.substitutes)}"
        )

        print("")

        for index, player in enumerate(
            lineup.away_team.starters,
            start=1,
        ):

            print(
                f"   {index}. {player}"
            )

        print("")
        print(
            "✅ LINEUP TEST ERFOLGREICH"
        )

    except Exception as error:

        print(
            f"❌ LINEUP: {error}"
        )

    # ========================================================
    # SPIELPLAN
    # ========================================================

    print("")
    print(
        "============================================"
    )
    print(
        "AKTUELLE LA-LIGA-SPIELE"
    )
    print(
        "============================================"
    )
    print("")

    try:

        links = get_laliga_match_links()

        print(
            f"Match-Links gefunden: "
            f"{len(links)}"
        )

        print("")

        matches = get_laliga_upcoming_matches(
            3
        )

        print(
            f"Spiele mit Anstoßzeit: "
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
                "   🔗 "
                f"{match['url']}"
            )

            print("")

    except Exception as error:

        print(
            f"❌ SPIELPLAN: {error}"
        )

    print("")
    print(
        "============================================"
    )
    print(
        "🏁 TEST BEENDET"
    )
    print(
        "============================================"
    )
    print("")