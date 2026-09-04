import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from models import TeamLineup, MatchLineup


# ============================================================
# KONFIGURATION
# ============================================================

BASE_URL = "https://www.bundesliga.at"

SCHEDULE_URL = (
    "https://www.bundesliga.at/de/spielplan"
)

SEASON = "saison-2026-2027"

AUSTRIA_TIMEZONE = ZoneInfo(
    "Europe/Vienna"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/152.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": (
        "de-DE,de;q=0.9,en;q=0.8"
    ),
}


TEAM_NAMES = {
    "ASK": "LASK",
    "STU": "SK Sturm Graz",
    "RBS": "FC Red Bull Salzburg",
    "FAK": "FK Austria Wien",
    "SCR": "SK Rapid",
    "HTB": "TSV Hartberg",
    "SVR": "SV Oberbank Ried",
    "WAC": "RZ Pellets WAC",
    "ALT": "SCR Altach",
    "GAK": "Grazer AK 1902",
    "WSG": "WSG Tirol",
    "ALU": "FC Blau-Weiß Linz",
}


# ============================================================
# HTTP
# ============================================================

def _get_soup(
    url,
    params=None,
):

    response = requests.get(
        url,
        params=params,
        headers=HEADERS,
        timeout=25,
    )

    response.raise_for_status()

    return BeautifulSoup(
        response.text,
        "html.parser",
    )


# ============================================================
# TEXT
# ============================================================

def _clean_text(
    text,
):

    if not text:
        return ""

    return " ".join(
        str(text).split()
    ).strip()


# ============================================================
# MATCH-ID
# ============================================================

def _extract_match_id(
    url,
):

    match = re.search(
        r"/spielbericht/"
        r"saison-\d{4}-\d{4}/"
        r"(\d+)",
        str(url),
    )

    if not match:
        return None

    return match.group(1)


def _matchcenter_url(
    match_id,
):

    return (
        f"{BASE_URL}/de/spielbericht/"
        f"{SEASON}/"
        f"{match_id}/matchcenter"
    )


# ============================================================
# MATCH-INFOS
# ============================================================

def _get_match_info(
    match_url,
):

    soup = _get_soup(
        match_url
    )

    heading = soup.find(
        "h1"
    )

    if heading is None:

        raise ValueError(
            "Spielüberschrift nicht gefunden."
        )

    heading_text = _clean_text(
        heading.get_text(
            " ",
            strip=True,
        )
    )

    match = re.search(
        r"Runde\s+\d+\s*\|\s*"
        r".*?,\s*"
        r"(\d{2}\.\d{2}\.\d{4})"
        r"\s*\|\s*"
        r"(\d{1,2}:\d{2})",
        heading_text,
    )

    if not match:

        raise ValueError(
            "Datum oder Anstoßzeit "
            "konnte nicht gelesen werden."
        )

    kickoff = datetime.strptime(
        (
            f"{match.group(1)} "
            f"{match.group(2)}"
        ),
        "%d.%m.%Y %H:%M",
    ).replace(
        tzinfo=AUSTRIA_TIMEZONE
    )

    # --------------------------------------------------------
    # Teams direkt im oberen Spielkopf suchen
    # --------------------------------------------------------

    team_codes = []

    for element in heading.find_all_next():

        text = _clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if text in TEAM_NAMES:

            if text not in team_codes:

                team_codes.append(
                    text
                )

        if len(team_codes) >= 2:
            break

    if len(team_codes) < 2:

        raise ValueError(
            "Mannschaften konnten "
            "nicht erkannt werden."
        )

    home_code = team_codes[0]
    away_code = team_codes[1]

    match_id = _extract_match_id(
        match_url
    )

    return {
        "kickoff": kickoff,
        "home_team": TEAM_NAMES[
            home_code
        ],
        "away_team": TEAM_NAMES[
            away_code
        ],
        "home_code": home_code,
        "away_code": away_code,
        "match_id": match_id,
        "url": (
            _matchcenter_url(
                match_id
            )
        ),
    }


# ============================================================
# SPIELPLAN-LINKS
# ============================================================

def _get_match_links(
    matchday,
):

    soup = _get_soup(
        SCHEDULE_URL,
        params={
            "spieltag": matchday,
        },
    )

    matches = []
    seen = set()

    for link in soup.find_all(
        "a",
        href=True,
    ):

        href = link.get(
            "href",
            "",
        )

        if "/spielbericht/" not in href:
            continue

        if SEASON not in href:
            continue

        match_id = _extract_match_id(
            href
        )

        if not match_id:
            continue

        if match_id in seen:
            continue

        seen.add(
            match_id
        )

        matches.append(
            _matchcenter_url(
                match_id
            )
        )

    return matches


# ============================================================
# SPIELPLAN
# ============================================================

def get_austria_upcoming_matches(
    days=2,
):

    now = datetime.now(
        AUSTRIA_TIMEZONE
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

    all_urls = []

    # Grunddurchgang = 22 Spieltage

    for matchday in range(
        1,
        23,
    ):

        try:

            urls = _get_match_links(
                matchday
            )

        except Exception as error:

            print(
                f"⚠️ Österreich Spieltag "
                f"{matchday}: {error}"
            )

            continue

        for url in urls:

            if url not in all_urls:

                all_urls.append(
                    url
                )

    matches = []

    for url in all_urls:

        try:

            match = _get_match_info(
                url
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
# SPIELERLINK
# ============================================================

def _is_player_link(
    element,
):

    if element.name != "a":
        return False

    href = element.get(
        "href",
        "",
    )

    if "/spieler/" not in href:
        return False

    name = _clean_text(
        element.get_text(
            " ",
            strip=True,
        )
    )

    return bool(
        name
    )


# ============================================================
# DOPPELTE SPIELER ENTFERNEN
# ============================================================

def _unique_players(
    players,
):

    result = []

    for player in players:

        if player not in result:

            result.append(
                player
            )

    return result


# ============================================================
# AUFSTELLUNG
# ============================================================

def get_austria_lineup(
    match_url,
):

    match_id = _extract_match_id(
        match_url
    )

    if not match_id:

        if str(
            match_url
        ).isdigit():

            match_id = str(
                match_url
            )

        else:

            raise ValueError(
                "Ungültige Österreich-Match-URL."
            )

    url = _matchcenter_url(
        match_id
    )

    soup = _get_soup(
        url
    )

    match_info = _get_match_info(
        url
    )

    home_code = match_info[
        "home_code"
    ]

    away_code = match_info[
        "away_code"
    ]

    # --------------------------------------------------------
    # Überschrift "Aufstellung"
    # --------------------------------------------------------

    lineup_heading = None

    for heading in soup.find_all(
        [
            "h2",
            "h3",
        ]
    ):

        text = _clean_text(
            heading.get_text(
                " ",
                strip=True,
            )
        )

        if text == "Aufstellung":

            lineup_heading = heading
            break

    if lineup_heading is None:

        raise ValueError(
            "Offizielle Aufstellung "
            "noch nicht veröffentlicht."
        )

    # --------------------------------------------------------
    # Wir lesen ab der Überschrift die Seite der Reihe nach.
    #
    # Zustand:
    #
    # wait_home
    # home_starters
    # home_bench
    # wait_away
    # away_starters
    # away_bench
    # done
    # --------------------------------------------------------

    state = "wait_home"

    home_starters = []
    home_substitutes = []

    away_starters = []
    away_substitutes = []

    current = lineup_heading

    while True:

        current = current.find_next()

        if current is None:
            break

        # ----------------------------------------------------
        # Nur Text des aktuellen Elements.
        #
        # recursive=False verhindert, dass z.B. ein großer DIV
        # den kompletten Inhalt aller Unterelemente liefert.
        # ----------------------------------------------------

        own_text = _clean_text(
            current.get_text(
                " ",
                strip=True,
            )
            if current.name
            in [
                "h2",
                "h3",
                "h4",
                "p",
                "span",
                "div",
                "a",
            ]
            else ""
        )

        # ----------------------------------------------------
        # Heimteam erkannt
        # ----------------------------------------------------

        if state == "wait_home":

            if own_text == home_code:

                state = (
                    "home_starters"
                )

            continue

        # ----------------------------------------------------
        # Heim-Startelf -> Heim-Bank
        # ----------------------------------------------------

        if (
            state
            == "home_starters"
            and own_text
            == "Ersatzbank"
        ):

            state = (
                "home_bench"
            )

            continue

        # ----------------------------------------------------
        # Heim-Bank -> auf Auswärtsteam warten
        # ----------------------------------------------------

        if (
            state
            == "home_bench"
            and own_text
            == "Trainer"
        ):

            state = (
                "wait_away"
            )

            continue

        # ----------------------------------------------------
        # Auswärtsteam erkannt
        # ----------------------------------------------------

        if state == "wait_away":

            if own_text == away_code:

                state = (
                    "away_starters"
                )

            continue

        # ----------------------------------------------------
        # Auswärts-Startelf -> Auswärts-Bank
        # ----------------------------------------------------

        if (
            state
            == "away_starters"
            and own_text
            == "Ersatzbank"
        ):

            state = (
                "away_bench"
            )

            continue

        # ----------------------------------------------------
        # Zweiter Trainer = Ende
        # ----------------------------------------------------

        if (
            state
            == "away_bench"
            and own_text
            == "Trainer"
        ):

            state = "done"
            break

        # ----------------------------------------------------
        # Spieler
        # ----------------------------------------------------

        if not _is_player_link(
            current
        ):
            continue

        player = _clean_text(
            current.get_text(
                " ",
                strip=True,
            )
        )

        if state == "home_starters":

            home_starters.append(
                player
            )

        elif state == "home_bench":

            home_substitutes.append(
                player
            )

        elif state == "away_starters":

            away_starters.append(
                player
            )

        elif state == "away_bench":

            away_substitutes.append(
                player
            )

    # --------------------------------------------------------
    # Doppelte entfernen
    # --------------------------------------------------------

    home_starters = _unique_players(
        home_starters
    )

    home_substitutes = _unique_players(
        home_substitutes
    )

    away_starters = _unique_players(
        away_starters
    )

    away_substitutes = _unique_players(
        away_substitutes
    )

    # --------------------------------------------------------
    # Sicherheitsprüfung
    # --------------------------------------------------------

    if len(
        home_starters
    ) != 11:

        raise ValueError(
            "Heim-Startelf unvollständig: "
            f"{len(home_starters)} Spieler."
        )

    if len(
        away_starters
    ) != 11:

        raise ValueError(
            "Auswärts-Startelf unvollständig: "
            f"{len(away_starters)} Spieler."
        )

    if not home_substitutes:

        raise ValueError(
            "Heim-Bank fehlt."
        )

    if not away_substitutes:

        raise ValueError(
            "Auswärts-Bank fehlt."
        )

    # --------------------------------------------------------
    # Ergebnis
    # --------------------------------------------------------

    home_team = TeamLineup(
        team_name=match_info[
            "home_team"
        ],
        starters=home_starters,
        substitutes=home_substitutes,
    )

    away_team = TeamLineup(
        team_name=match_info[
            "away_team"
        ],
        starters=away_starters,
        substitutes=away_substitutes,
    )

    return MatchLineup(
        league=(
            "Österreich Bundesliga"
        ),
        home_team=home_team,
        away_team=away_team,
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
        "🇦🇹 ÖSTERREICH BUNDESLIGA TEST"
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
            get_austria_upcoming_matches(
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

            kickoff = match[
                "kickoff"
            ]

            print(
                f"{index}. "
                f"{match['home_team']} "
                f"vs. "
                f"{match['away_team']}"
            )

            print(
                "   🕒 "
                f"{kickoff.strftime('%d.%m.%Y %H:%M')}"
            )

            print(
                "   ID: "
                f"{match['match_id']}"
            )

            print("")

    except Exception as error:

        print(
            "❌ Spielplan-Fehler: "
            f"{error}"
        )

    # ========================================================
    # AUFSTELLUNG
    # ========================================================

    print("")
    print(
        "👕 AUFSTELLUNG TEST"
    )

    print(
        "--------------------------------------------"
    )

    TEST_URL = (
        "https://www.bundesliga.at/de/"
        "spielbericht/saison-2026-2027/"
        "56681/matchcenter"
    )

    try:

        lineup = (
            get_austria_lineup(
                TEST_URL
            )
        )

        # ----------------------------------------------------
        # HEIM
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # AUSWÄRTS
        # ----------------------------------------------------

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