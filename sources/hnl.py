import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from models import MatchLineup, TeamLineup


HNL_COMPETITION_URL = (
    "https://semafor.hns.family/"
    "natjecanja/114137140/supersport-hnl/detaljno/"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/152.0.0.0 Safari/537.36"
    )
}


# ============================================================
# Allgemeine Hilfsfunktionen
# ============================================================

def clean_text(text: str) -> str:
    return " ".join(text.split()).strip()


def clean_player_name(name: str) -> str:
    name = clean_text(name)
    name = re.sub(r"\s*\(C\)\s*$", "", name)
    return name.strip()


def parse_hns_datetime(text: str):
    """
    Erkennt z. B.:
    05.09.2026. 18:00
    """

    match = re.search(
        r"(\d{2}\.\d{2}\.\d{4}\.)\s+(\d{2}:\d{2})",
        text,
    )

    if not match:
        return None

    try:
        return datetime.strptime(
            f"{match.group(1)} {match.group(2)}",
            "%d.%m.%Y. %H:%M",
        )

    except ValueError:
        return None


def normalize_name(text: str) -> str:
    """
    Hilft später beim Vergleich von Teamnamen.
    """

    text = text.lower()

    replacements = {
        "č": "c",
        "ć": "c",
        "ž": "z",
        "š": "s",
        "đ": "d",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[^a-z0-9]+", " ", text)

    return clean_text(text)


# ============================================================
# Kommende Spiele aus dem HNL-Spielplan lesen
# ============================================================

def get_hnl_upcoming_matches(days_ahead: int = 2):
    """
    Holt kommende HNL-Spiele direkt aus dem offiziellen
    HNS-Spielplan.

    Ein Match-Link muss dabei noch NICHT existieren.

    days_ahead=2 bedeutet:
    heute + die nächsten 2 Tage.
    """

    response = requests.get(
        HNL_COMPETITION_URL,
        headers=HEADERS,
        timeout=20,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    now = datetime.now()

    allowed_dates = {
        (now + timedelta(days=offset)).date()
        for offset in range(days_ahead + 1)
    }

    results = []

    # --------------------------------------------------------
    # Alle Textzeilen sauber herausziehen
    # --------------------------------------------------------

    lines = [
        clean_text(line)
        for line in soup.get_text("\n").splitlines()
        if clean_text(line)
    ]

    date_pattern = re.compile(
        r"^\d{2}\.\d{2}\.\d{4}\.\s+\d{2}:\d{2}$"
    )

    # Typische Begriffe, die KEINE Mannschaften sind
    blocked = {
        "detaljno",
        "utakmice",
        "tablica",
        "klubovi",
        "igrači",
        "igraci",
        "raspored",
        "rezultati",
        "zapisnik",
        "stadion",
        "suci",
        "delegat",
        "superSport hnl",
    }

    for index, line in enumerate(lines):

        if not date_pattern.match(line):
            continue

        kickoff = parse_hns_datetime(line)

        if kickoff is None:
            continue

        if kickoff.date() not in allowed_dates:
            continue

        # ----------------------------------------------------
        # Nach Datum/Uhrzeit folgen auf HNS normalerweise die
        # Informationen zum jeweiligen Spiel.
        #
        # Wir nehmen einen kleinen Bereich direkt danach.
        # ----------------------------------------------------

        nearby = lines[
            index + 1:
            index + 12
        ]

        candidates = []

        for item in nearby:

            lowered = item.lower()

            # Nächstes Spiel beginnt bereits
            if date_pattern.match(item):
                break

            # Ergebnis wie 2:1 ignorieren
            if re.fullmatch(
                r"\d+\s*:\s*\d+",
                item,
            ):
                continue

            # Uhrzeit alleine ignorieren
            if re.fullmatch(
                r"\d{2}:\d{2}",
                item,
            ):
                continue

            if lowered in {
                word.lower()
                for word in blocked
            }:
                continue

            # Tabellen-/Rundeninformationen ignorieren
            if re.search(
                r"\b\d+\.\s*kolo\b",
                lowered,
            ):
                continue

            if len(item) < 3:
                continue

            if len(item) > 80:
                continue

            # Mannschaften enthalten normalerweise Buchstaben
            if not any(
                char.isalpha()
                for char in item
            ):
                continue

            if item not in candidates:
                candidates.append(item)

        # ----------------------------------------------------
        # Wir brauchen zwei Mannschaften.
        # ----------------------------------------------------

        if len(candidates) < 2:
            continue

        home_team = candidates[0]
        away_team = candidates[1]

        results.append(
            {
                "kickoff": kickoff,
                "home_team": home_team,
                "away_team": away_team,
                "url": None,
            }
        )

    # --------------------------------------------------------
    # Duplikate entfernen
    # --------------------------------------------------------

    unique_results = []

    seen = set()

    for item in results:

        key = (
            item["kickoff"],
            normalize_name(item["home_team"]),
            normalize_name(item["away_team"]),
        )

        if key in seen:
            continue

        seen.add(key)
        unique_results.append(item)

    unique_results.sort(
        key=lambda item: item["kickoff"]
    )

    return unique_results


# ============================================================
# Match-Link später automatisch suchen
# ============================================================

def find_hnl_match_url(
    home_team: str,
    away_team: str,
):
    """
    Prüft die offizielle Wettbewerbsseite darauf,
    ob für das Spiel inzwischen ein /utakmice/-Link
    vorhanden ist.

    Es wird nur ein Link akzeptiert, wenn BEIDE
    Mannschaften im unmittelbaren Spielblock vorkommen.
    """

    response = requests.get(
        HNL_COMPETITION_URL,
        headers=HEADERS,
        timeout=20,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    home_normalized = normalize_name(home_team)
    away_normalized = normalize_name(away_team)

    for link in soup.find_all(
        "a",
        href=True,
    ):

        href = link.get(
            "href",
            "",
        )

        if "/utakmice/" not in href:
            continue

        current = link

        for _ in range(8):

            current = current.parent

            if current is None:
                break

            block_text = normalize_name(
                current.get_text(
                    " ",
                    strip=True,
                )
            )

            if (
                home_normalized in block_text
                and away_normalized in block_text
            ):

                return urljoin(
                    HNL_COMPETITION_URL,
                    href,
                )

    return None


# ============================================================
# Aufstellung aus konkreter HNS-Matchseite lesen
# ============================================================

def get_hnl_lineup(
    match_url: str,
) -> MatchLineup:

    response = requests.get(
        match_url,
        headers=HEADERS,
        timeout=20,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    # --------------------------------------------------------
    # Teamnamen
    # --------------------------------------------------------

    title = soup.find("h1")

    if not title:
        raise ValueError(
            "Spielname konnte nicht gefunden werden."
        )

    match_title = title.get_text(
        " ",
        strip=True,
    )

    match_part = match_title.split(",")[0]

    match_part = re.sub(
        r"\s+\d+\s*:\s*\d+\s*$",
        "",
        match_part,
    )

    if " - " not in match_part:
        raise ValueError(
            "Die beiden Mannschaften konnten "
            "nicht erkannt werden."
        )

    home_name, away_name = match_part.split(
        " - ",
        1,
    )

    home_name = home_name.strip()
    away_name = away_name.strip()

    # --------------------------------------------------------
    # Sind beide Ersatzbänke schon veröffentlicht?
    # --------------------------------------------------------

    reserve_elements = soup.find_all(
        string=lambda text:
        text
        and "Pričuvni igrači" in text
    )

    if len(reserve_elements) < 2:
        raise ValueError(
            "Aufstellung wurde noch nicht veröffentlicht."
        )

    # --------------------------------------------------------
    # Spieler auslesen
    # --------------------------------------------------------

    all_elements = soup.find_all(
        [
            "h3",
            "li",
            "div",
            "span",
        ]
    )

    section_players = {
        0: [],  # Heim Startelf
        1: [],  # Heim Bank
        2: [],  # Auswärts Startelf
        3: [],  # Auswärts Bank
    }

    current_section = 0

    home_reserve_found = False
    away_team_found = False
    away_reserve_found = False

    seen_players = set()

    for element in all_elements:

        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if not text:
            continue

        # ----------------------------------------------------
        # Erste Ersatzbank
        # ----------------------------------------------------

        if text == "Pričuvni igrači":

            if not home_reserve_found:

                home_reserve_found = True
                current_section = 1

                continue

            # ------------------------------------------------
            # Zweite Ersatzbank
            # ------------------------------------------------

            if (
                away_team_found
                and not away_reserve_found
            ):

                away_reserve_found = True
                current_section = 3

                continue

        # ----------------------------------------------------
        # Wechsel zum Auswärtsteam
        # ----------------------------------------------------

        if (
            home_reserve_found
            and text == away_name
            and not away_team_found
        ):

            away_team_found = True
            current_section = 2

            continue

        # ----------------------------------------------------
        # Spieler stehen auf HNS in h3
        # ----------------------------------------------------

        if element.name != "h3":
            continue

        player = clean_player_name(
            text
        )

        if not player:
            continue

        parent_text = element.parent.get_text(
            " ",
            strip=True,
        )

        if (
            "Igrač" not in parent_text
            and "Vratar" not in parent_text
        ):
            continue

        key = (
            current_section,
            player,
        )

        if key in seen_players:
            continue

        seen_players.add(
            key
        )

        section_players[
            current_section
        ].append(
            player
        )

    # --------------------------------------------------------
    # Daten übernehmen
    # --------------------------------------------------------

    home_starters = section_players[0]
    home_subs = section_players[1]

    away_starters = section_players[2]
    away_subs = section_players[3]

    # --------------------------------------------------------
    # Sicherheitskontrollen
    # --------------------------------------------------------

    if len(home_starters) != 11:
        raise ValueError(
            f"Heim-Startelf hat "
            f"{len(home_starters)} statt 11 Spieler."
        )

    if len(away_starters) != 11:
        raise ValueError(
            f"Auswärts-Startelf hat "
            f"{len(away_starters)} statt 11 Spieler."
        )

    if not home_subs:
        raise ValueError(
            "Heim-Bank wurde nicht gefunden."
        )

    if not away_subs:
        raise ValueError(
            "Auswärts-Bank wurde nicht gefunden."
        )

    return MatchLineup(
        league="HNL",

        home_team=TeamLineup(
            team_name=home_name,
            starters=home_starters,
            substitutes=home_subs,
        ),

        away_team=TeamLineup(
            team_name=away_name,
            starters=away_starters,
            substitutes=away_subs,
        ),

        match_url=match_url,
    )