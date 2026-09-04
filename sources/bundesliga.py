import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from models import MatchLineup, TeamLineup


# ============================================================
# EINSTELLUNGEN
# ============================================================

BUNDESLIGA_MATCHDAY_URL = (
    "https://www.bundesliga.com/en/bundesliga/matchday"
)

BERLIN_TIMEZONE = ZoneInfo(
    "Europe/Berlin"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/152.0.0.0 Safari/537.36"
    )
}


TEAM_SLUG_NAMES = {
    "1-fc-heidenheim-1846": "1. FC Heidenheim 1846",
    "1-fc-koeln": "1. FC Köln",
    "1-fc-union-berlin": "1. FC Union Berlin",
    "1-fsv-mainz-05": "1. FSV Mainz 05",
    "bayer-04-leverkusen": "Bayer 04 Leverkusen",
    "borussia-dortmund": "Borussia Dortmund",
    "borussia-moenchengladbach": "Borussia Mönchengladbach",
    "eintracht-frankfurt": "Eintracht Frankfurt",
    "fc-augsburg": "FC Augsburg",
    "fc-bayern-muenchen": "FC Bayern München",
    "fc-schalke-04": "FC Schalke 04",
    "hamburger-sv": "Hamburger SV",
    "rb-leipzig": "RB Leipzig",
    "sc-freiburg": "SC Freiburg",
    "sport-club-freiburg": "SC Freiburg",
    "sc-paderborn-07": "SC Paderborn 07",
    "sv-elversberg": "SV Elversberg",
    "sv-werder-bremen": "SV Werder Bremen",
    "tsg-hoffenheim": "TSG Hoffenheim",
    "vfb-stuttgart": "VfB Stuttgart",
}


# ============================================================
# ALLGEMEINE HILFSFUNKTIONEN
# ============================================================

def clean_text(text: str) -> str:
    return " ".join(
        str(text).split()
    ).strip()


def prepare_match_url(
    url: str,
) -> str:

    url = url.strip().rstrip("/")

    if url.endswith("/liveticker"):
        url = (
            url[:-11]
            + "/lineup"
        )

    if url.endswith("/accessibility"):
        url = (
            url[:-14]
            + "/lineup"
        )

    return url


def accessibility_url(
    match_url: str,
) -> str:

    match_url = (
        prepare_match_url(
            match_url
        )
        .rstrip("/")
    )

    if match_url.endswith("/lineup"):

        return (
            match_url[:-7]
            + "/accessibility"
        )

    return (
        match_url
        + "/accessibility"
    )


def download_match_page(
    match_url: str,
):

    match_url = prepare_match_url(
        match_url
    )

    response = requests.get(
        match_url,
        headers=HEADERS,
        timeout=20,
    )

    response.raise_for_status()

    return (
        match_url,
        response.text,
    )


# ============================================================
# JSON-HILFSFUNKTIONEN
# ============================================================

def read_json_object_after_key(
    html: str,
    key: str,
    start_position: int = 0,
):

    variants = [
        f'"{key}":',
        f'\\"{key}\\":',
    ]

    found = []

    for variant in variants:

        position = html.find(
            variant,
            start_position,
        )

        if position != -1:

            found.append(
                (
                    position,
                    variant,
                )
            )

    if not found:
        return None, -1

    position, variant = min(
        found,
        key=lambda item: item[0],
    )

    object_start = html.find(
        "{",
        position + len(variant),
    )

    if object_start == -1:
        return None, -1

    decoder = json.JSONDecoder()

    try:

        data, length = decoder.raw_decode(
            html[object_start:]
        )

        return (
            data,
            object_start + length,
        )

    except json.JSONDecodeError:
        pass

    chunk = html[
        object_start:
        object_start + 500000
    ]

    unescaped = (
        chunk
        .replace('\\"', '"')
        .replace("\\u002F", "/")
        .replace("\\u003A", ":")
        .replace("\\u0026", "&")
    )

    try:

        data, length = decoder.raw_decode(
            unescaped
        )

        return (
            data,
            object_start
            + max(
                length,
                1,
            ),
        )

    except json.JSONDecodeError:

        return None, -1


def find_all_json_objects(
    html: str,
    key: str,
):

    objects = []

    position = 0

    while position < len(html):

        data, next_position = (
            read_json_object_after_key(
                html,
                key,
                position,
            )
        )

        if data is None:
            break

        objects.append(
            data
        )

        if next_position <= position:
            position += 1

        else:
            position = next_position

    return objects


# ============================================================
# SPIELER
# ============================================================

def extract_person_names(
    data,
):

    if not isinstance(
        data,
        dict,
    ):
        return []

    persons = data.get(
        "persons",
        [],
    )

    if not isinstance(
        persons,
        list,
    ):
        return []

    players = []

    ignored_roles = {
        "HEADCOACH",
        "COACH",
        "ASSISTANT_COACH",
        "MANAGER",
    }

    for person in persons:

        if not isinstance(
            person,
            dict,
        ):
            continue

        name = clean_text(
            person.get(
                "name",
                "",
            )
        )

        role = clean_text(
            person.get(
                "role",
                "",
            )
        ).upper()

        if not name:
            continue

        if role in ignored_roles:
            continue

        if name not in players:

            players.append(
                name
            )

    return players


# ============================================================
# HOME / AWAY
# ============================================================

def find_team_side_object(
    html: str,
    side: str,
):

    objects = find_all_json_objects(
        html,
        side,
    )

    best = None
    best_score = -1

    for data in objects:

        if not isinstance(
            data,
            dict,
        ):
            continue

        score = 0

        starting = data.get(
            "startingEleven"
        )

        bench = data.get(
            "bench"
        )

        if isinstance(
            starting,
            dict,
        ):

            players = extract_person_names(
                starting
            )

            if len(players) == 11:
                score += 10

            elif players:
                score += 3

        if isinstance(
            bench,
            dict,
        ):

            players = extract_person_names(
                bench
            )

            if players:
                score += 5

        if score > best_score:

            best_score = score
            best = data

    if best_score <= 0:
        return None

    return best


def extract_home_away_players(
    html: str,
):

    home_data = find_team_side_object(
        html,
        "home",
    )

    away_data = find_team_side_object(
        html,
        "away",
    )

    if not home_data:

        raise ValueError(
            "Home-Daten konnten nicht gefunden werden."
        )

    if not away_data:

        raise ValueError(
            "Away-Daten konnten nicht gefunden werden."
        )

    home_starters = extract_person_names(
        home_data.get(
            "startingEleven",
            {},
        )
    )

    home_subs = extract_person_names(
        home_data.get(
            "bench",
            {},
        )
    )

    away_starters = extract_person_names(
        away_data.get(
            "startingEleven",
            {},
        )
    )

    away_subs = extract_person_names(
        away_data.get(
            "bench",
            {},
        )
    )

    return (
        home_starters,
        home_subs,
        away_starters,
        away_subs,
    )


# ============================================================
# TEAMNAMEN
# ============================================================

def slug_to_team_name(
    slug: str,
) -> str:

    slug = slug.strip(
        "/"
    ).lower()

    if slug in TEAM_SLUG_NAMES:

        return TEAM_SLUG_NAMES[
            slug
        ]

    return " ".join(
        word.capitalize()
        for word in slug.split("-")
    )


def get_team_names_from_url(
    match_url: str,
):

    path = urlparse(
        match_url
    ).path

    for part in path.split(
        "/"
    ):

        if "-vs-" not in part:
            continue

        home_slug, away_slug = (
            part.split(
                "-vs-",
                1,
            )
        )

        return (
            slug_to_team_name(
                home_slug
            ),
            slug_to_team_name(
                away_slug
            ),
        )

    return (
        "Heimteam",
        "Auswärtsteam",
    )


# ============================================================
# OFFIZIELLE AUFSTELLUNG?
# ============================================================

def check_official_lineup(
    text: str,
):

    lower_text = text.lower()

    predicted = (
        "predicted line-up"
        in lower_text
        or
        "predicted lineup"
        in lower_text
    )

    official = (
        "starting line-up"
        in lower_text
        or
        "starting lineup"
        in lower_text
    )

    if (
        predicted
        and not official
    ):

        raise ValueError(
            "Die Aufstellung ist aktuell "
            "nur prognostiziert."
        )

    if not official:

        raise ValueError(
            "Die offizielle Aufstellung wurde "
            "noch nicht veröffentlicht."
        )


# ============================================================
# AUFSTELLUNG LADEN
# ============================================================

def get_bundesliga_lineup(
    match_url: str,
) -> MatchLineup:

    (
        final_url,
        html,
    ) = download_match_page(
        match_url
    )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    text = soup.get_text(
        "\n",
        strip=True,
    )

    check_official_lineup(
        text
    )

    (
        home_name,
        away_name,
    ) = get_team_names_from_url(
        final_url
    )

    (
        home_starters,
        home_subs,
        away_starters,
        away_subs,
    ) = extract_home_away_players(
        html
    )

    if len(home_starters) != 11:

        raise ValueError(
            f"{home_name}: "
            f"Startelf hat "
            f"{len(home_starters)}/11 Spieler."
        )

    if len(away_starters) != 11:

        raise ValueError(
            f"{away_name}: "
            f"Startelf hat "
            f"{len(away_starters)}/11 Spieler."
        )

    if not home_subs:

        raise ValueError(
            f"{home_name}: Bank ist leer."
        )

    if not away_subs:

        raise ValueError(
            f"{away_name}: Bank ist leer."
        )

    return MatchLineup(
        league="Bundesliga",

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

        match_url=final_url,
    )


# ============================================================
# MATCH-LINKS
# ============================================================

def extract_match_links(
    html: str,
):

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    links = []

    seen = set()

    for link in soup.find_all(
        "a",
        href=True,
    ):

        href = link.get(
            "href",
            "",
        )

        if (
            "/en/bundesliga/matchday/"
            not in href
        ):
            continue

        if "-vs-" not in href:
            continue

        if (
            "/liveticker" not in href
            and
            "/lineup" not in href
            and
            "/accessibility" not in href
        ):
            continue

        absolute_url = urljoin(
            BUNDESLIGA_MATCHDAY_URL,
            href,
        )

        lineup_url = prepare_match_url(
            absolute_url
        )

        if lineup_url in seen:
            continue

        seen.add(
            lineup_url
        )

        links.append(
            lineup_url
        )

    return links


# ============================================================
# ANSTOSSZEIT PRO SPIEL
# ============================================================

def get_match_kickoff(
    match_url: str,
):
    """
    Holt die offizielle Zeit aus der
    Accessibility-Seite.

    Bundesliga.com zeigt dort die Zeit aktuell
    in UTC. Danach Umrechnung auf Europe/Berlin.
    """

    url = accessibility_url(
        match_url
    )

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=20,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    text = soup.get_text(
        " ",
        strip=True,
    )

    # Beispiel:
    # Fri, 04.09.2026 18:30 PM
    #
    # Wir ignorieren "PM", weil 18:30 bereits
    # im 24-Stunden-Format steht.

    patterns = [
        (
            r"\b"
            r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)"
            r"[a-z]*,\s*"
            r"(\d{2}\.\d{2}\.\d{4})"
            r"\s+"
            r"(\d{2}:\d{2})"
        ),
        (
            r"\b"
            r"(\d{2}\.\d{2}\.\d{4})"
            r"\s+"
            r"(\d{2}:\d{2})"
        ),
    ]

    match = None

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if match:
            break

    if not match:

        raise ValueError(
            "Anstoßzeit konnte auf der "
            "Accessibility-Seite nicht gefunden werden."
        )

    date_text = match.group(
        1
    )

    time_text = match.group(
        2
    )

    utc_naive = datetime.strptime(
        f"{date_text} {time_text}",
        "%d.%m.%Y %H:%M",
    )

    utc_dt = utc_naive.replace(
        tzinfo=timezone.utc
    )

    berlin_dt = utc_dt.astimezone(
        BERLIN_TIMEZONE
    )

    return berlin_dt.replace(
        tzinfo=None
    )


# ============================================================
# SPIELPLAN
# ============================================================

def get_bundesliga_upcoming_matches(
    days_ahead: int = 2,
):

    response = requests.get(
        BUNDESLIGA_MATCHDAY_URL,
        headers=HEADERS,
        timeout=20,
    )

    response.raise_for_status()

    links = extract_match_links(
        response.text
    )

    if not links:

        raise ValueError(
            "Keine Bundesliga-Match-Links gefunden."
        )

    now = datetime.now(
        BERLIN_TIMEZONE
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

    for match_url in links:

        (
            home_name,
            away_name,
        ) = get_team_names_from_url(
            match_url
        )

        try:

            kickoff = get_match_kickoff(
                match_url
            )

        except Exception as error:

            print(
                "⚠️ Uhrzeit nicht lesbar: "
                f"{home_name} vs. {away_name}: "
                f"{error}"
            )

            continue

        if kickoff.date() not in allowed_dates:
            continue

        results.append(
            {
                "kickoff": kickoff,
                "home_team": home_name,
                "away_team": away_name,
                "url": match_url,
            }
        )

    results.sort(
        key=lambda item:
        item["kickoff"]
    )

    return results


# ============================================================
# TERMINAL-TEST
# ============================================================

if __name__ == "__main__":

    print("")
    print(
        "============================================"
    )
    print(
        "🇩🇪 BUNDESLIGA AUTOMATIK TEST"
    )
    print(
        "============================================"
    )
    print("")

    try:

        response = requests.get(
            BUNDESLIGA_MATCHDAY_URL,
            headers=HEADERS,
            timeout=20,
        )

        response.raise_for_status()

        links = extract_match_links(
            response.text
        )

        print(
            f"🔗 Match-Links gefunden: "
            f"{len(links)}"
        )

        print("")

        for index, link in enumerate(
            links,
            start=1,
        ):

            (
                home_name,
                away_name,
            ) = get_team_names_from_url(
                link
            )

            print(
                f"{index}. "
                f"{home_name} vs. {away_name}"
            )

            try:

                kickoff = get_match_kickoff(
                    link
                )

                print(
                    "   🕒 "
                    f"{kickoff.strftime('%d.%m.%Y %H:%M')}"
                )

            except Exception as error:

                print(
                    f"   ❌ {error}"
                )

        print("")
        print(
            "--------------------------------------------"
        )
        print("")

        matches = (
            get_bundesliga_upcoming_matches(
                2
            )
        )

        print(
            f"✅ {len(matches)} Spiele gefunden:"
        )

        print("")

        for match in matches:

            kickoff = match[
                "kickoff"
            ]

            print(
                "⚽ "
                f"{match['home_team']} "
                "vs. "
                f"{match['away_team']}"
            )

            print(
                "   🕒 "
                f"{kickoff.strftime('%d.%m.%Y %H:%M')}"
            )

            print(
                "   🔗 "
                f"{match['url']}"
            )

            print("")

    except Exception as error:

        print(
            "❌ TEST FEHLGESCHLAGEN"
        )

        print(
            f"Fehler: {error}"
        )

    print(
        "============================================"
    )
    print("")