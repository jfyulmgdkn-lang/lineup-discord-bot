import os
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from sources.hnl import (
    get_hnl_upcoming_matches,
    find_hnl_match_url,
    get_hnl_lineup,
)

from sources.bundesliga import (
    get_bundesliga_upcoming_matches,
    get_bundesliga_lineup,
)

from sources.bundesliga2 import (
    get_bundesliga2_upcoming_matches,
    get_bundesliga2_lineup,
)

from sources.premierleague import (
    get_premierleague_upcoming_matches,
    get_premierleague_lineup,
)

from sources.laliga import (
    get_laliga_upcoming_matches,
    get_laliga_lineup,
)

from sources.mls import (
    get_mls_upcoming_matches,
    get_mls_lineup,
)

from sources.austria import (
    get_austria_upcoming_matches,
    get_austria_lineup,
)

from sources.portugal import (
    get_portugal_upcoming_matches,
    get_portugal_lineup,
)

from sources.belgium import (
    get_belgium_upcoming_matches,
    get_belgium_lineup,
)

from sources.uefa import (
    get_uefa_cl_upcoming_matches,
    get_uefa_cl_lineup,
    get_uefa_el_upcoming_matches,
    get_uefa_el_lineup,
    get_uefa_ecl_upcoming_matches,
    get_uefa_ecl_lineup,
)

from sources.france import (
    get_ligue1_upcoming_matches,
    get_ligue1_lineup,
    get_ligue2_upcoming_matches,
    get_ligue2_lineup,
)


# ============================================================
# ZEITZONE
# ============================================================

BERLIN_TIMEZONE = ZoneInfo("Europe/Berlin")


def normalize_datetime(value):

    if value.tzinfo is None:
        return value.replace(
            tzinfo=BERLIN_TIMEZONE
        )

    return value.astimezone(
        BERLIN_TIMEZONE
    )


# ============================================================
# ENV
# ============================================================

load_dotenv()

TOKEN = os.getenv(
    "DISCORD_TOKEN"
)

LINEUP_CHANNEL_ID = os.getenv(
    "LINEUP_CHANNEL_ID"
)

if not TOKEN:
    raise ValueError(
        "DISCORD_TOKEN wurde nicht in der .env gefunden."
    )

if not LINEUP_CHANNEL_ID:
    raise ValueError(
        "LINEUP_CHANNEL_ID wurde nicht in der .env gefunden."
    )

LINEUP_CHANNEL_ID = int(
    LINEUP_CHANNEL_ID
)


# ============================================================
# DISCORD
# ============================================================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
)


# ============================================================
# POSTED MATCHES
# ============================================================

POSTED_FILE = Path(
    "posted_matches.json"
)


def load_posted_matches():

    if not POSTED_FILE.exists():
        return set()

    try:
        with open(
            POSTED_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            return set(
                json.load(file)
            )

    except Exception:
        return set()


def save_posted_matches(matches):

    with open(
        POSTED_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            sorted(matches),
            file,
            indent=4,
            ensure_ascii=False,
        )


posted_matches = load_posted_matches()


# ============================================================
# EMBED
# ============================================================

def create_team_text(team):

    starters = "\n".join(
        f"{index}. {player}"
        for index, player in enumerate(
            team.starters,
            start=1,
        )
    )

    substitutes = "\n".join(
        f"• {player}"
        for player in team.substitutes
    )

    return (
        "**👕 Startelf**\n"
        f"{starters}\n\n"
        "**🪑 Bank**\n"
        f"{substitutes}"
    )


def create_lineup_embed(lineup):

    sources = {
        "HNL": (
            "🇭🇷",
            "Quelle: HNS Semafor • SuperSport HNL",
        ),
        "Bundesliga": (
            "🇩🇪",
            "Quelle: Bundesliga.com",
        ),
        "2. Bundesliga": (
            "🇩🇪",
            "Quelle: Bundesliga.com • 2. Bundesliga",
        ),
        "Premier League": (
            "🏴",
            "Quelle: PremierLeague.com",
        ),
        "La Liga": (
            "🇪🇸",
            "Quelle: LaLiga.com",
        ),
        "MLS": (
            "🇺🇸",
            "Quelle: MLSsoccer.com",
        ),
        "Österreich Bundesliga": (
            "🇦🇹",
            "Quelle: Bundesliga.at",
        ),
        "Primeira Liga": (
            "🇵🇹",
            "Quelle: ESPN • Primeira Liga",
        ),
        "Jupiler Pro League": (
            "🇧🇪",
            "Quelle: ESPN • Jupiler Pro League",
        ),
        "Champions League": (
            "🏆",
            "Quelle: ESPN • UEFA Champions League",
        ),
        "Europa League": (
            "🏆",
            "Quelle: ESPN • UEFA Europa League",
        ),
        "Conference League": (
            "🏆",
            "Quelle: ESPN • UEFA Conference League",
        ),
        "Ligue 1": (
            "🇫🇷",
            "Quelle: ESPN • Ligue 1",
        ),
        "Ligue 2": (
            "🇫🇷",
            "Quelle: ESPN • Ligue 2",
        ),
    }

    flag, source_text = sources.get(
        lineup.league,
        (
            "⚽",
            "Aufstellungsdaten",
        ),
    )

    embed = discord.Embed(
        title=(
            f"{flag} "
            f"{lineup.league} – "
            f"{lineup.home_team.team_name} "
            f"vs. "
            f"{lineup.away_team.team_name}"
        ),
        description="**Offizielle Aufstellung**",
    )

    embed.add_field(
        name=(
            f"🏠 {lineup.home_team.team_name}"
        ),
        value=create_team_text(
            lineup.home_team
        ),
        inline=True,
    )

    embed.add_field(
        name=(
            f"✈️ {lineup.away_team.team_name}"
        ),
        value=create_team_text(
            lineup.away_team
        ),
        inline=True,
    )

    if lineup.match_url:
        embed.url = lineup.match_url

    embed.set_footer(
        text=source_text
    )

    return embed


# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():

    print("")
    print(
        "============================================"
    )

    print(
        f"🟢 Bot ist online: {bot.user}"
    )

    print(
        f"📢 Lineup-Channel: {LINEUP_CHANNEL_ID}"
    )

    print("")
    print(
        "AKTIVE WETTBEWERBE:"
    )

    print("🇭🇷 HNL")
    print("🇩🇪 Bundesliga")
    print("🇩🇪 2. Bundesliga")
    print("🏴 Premier League")
    print("🇪🇸 La Liga")
    print("🇺🇸 MLS")
    print("🇦🇹 Österreich Bundesliga")
    print("🇵🇹 Primeira Liga")
    print("🇧🇪 Jupiler Pro League")
    print("🏆 Champions League")
    print("🏆 Europa League")
    print("🏆 Conference League")
    print("🇫🇷 Ligue 1")
    print("🇫🇷 Ligue 2")

    print("")
    print(
        "⏱️ Prüfung alle 2 Minuten"
    )

    print(
        "============================================"
    )
    print("")

    if not automatic_lineup_check.is_running():
        automatic_lineup_check.start()


# ============================================================
# MANUELLE TESTBEFEHLE
# ============================================================

@bot.command()
async def ping(ctx):

    await ctx.send(
        "Pong! 🟢 Lineup Bot läuft."
    )


@bot.command()
async def hnl(ctx, match_url: str):

    try:
        lineup = await asyncio.to_thread(
            get_hnl_lineup,
            match_url,
        )

        await ctx.send(
            embed=create_lineup_embed(
                lineup
            )
        )

    except Exception as error:
        await ctx.send(
            f"❌ Fehler: `{error}`"
        )


@bot.command()
async def buli(ctx, match_url: str):

    try:
        lineup = await asyncio.to_thread(
            get_bundesliga_lineup,
            match_url,
        )

        await ctx.send(
            embed=create_lineup_embed(
                lineup
            )
        )

    except Exception as error:
        await ctx.send(
            f"❌ Fehler: `{error}`"
        )


@bot.command()
async def buli2(ctx, match_url: str):

    try:
        lineup = await asyncio.to_thread(
            get_bundesliga2_lineup,
            match_url,
        )

        await ctx.send(
            embed=create_lineup_embed(
                lineup
            )
        )

    except Exception as error:
        await ctx.send(
            f"❌ Fehler: `{error}`"
        )


@bot.command()
async def pl(ctx, match_url: str):

    try:
        lineup = await asyncio.to_thread(
            get_premierleague_lineup,
            match_url,
        )

        await ctx.send(
            embed=create_lineup_embed(
                lineup
            )
        )

    except Exception as error:
        await ctx.send(
            f"❌ Fehler: `{error}`"
        )


@bot.command()
async def laliga(ctx, match_url: str):

    try:
        lineup = await asyncio.to_thread(
            get_laliga_lineup,
            match_url,
        )

        await ctx.send(
            embed=create_lineup_embed(
                lineup
            )
        )

    except Exception as error:
        await ctx.send(
            f"❌ Fehler: `{error}`"
        )


@bot.command()
async def mls(ctx, match_id: str):

    try:
        lineup = await asyncio.to_thread(
            get_mls_lineup,
            match_id,
        )

        if lineup is None:
            await ctx.send(
                "⏳ Noch keine vollständige MLS-Aufstellung verfügbar."
            )
            return

        await ctx.send(
            embed=create_lineup_embed(
                lineup
            )
        )

    except Exception as error:
        await ctx.send(
            f"❌ Fehler: `{error}`"
        )


@bot.command()
async def austria(ctx, match_url: str):

    try:
        lineup = await asyncio.to_thread(
            get_austria_lineup,
            match_url,
        )

        await ctx.send(
            embed=create_lineup_embed(
                lineup
            )
        )

    except Exception as error:
        await ctx.send(
            f"❌ Fehler: `{error}`"
        )


@bot.command()
async def portugal(ctx, match_id: str):

    try:
        lineup = await asyncio.to_thread(
            get_portugal_lineup,
            match_id,
        )

        await ctx.send(
            embed=create_lineup_embed(
                lineup
            )
        )

    except Exception as error:
        await ctx.send(
            f"❌ Fehler: `{error}`"
        )


@bot.command()
async def belgium(ctx, match_id: str):

    try:
        lineup = await asyncio.to_thread(
            get_belgium_lineup,
            match_id,
        )

        await ctx.send(
            embed=create_lineup_embed(
                lineup
            )
        )

    except Exception as error:
        await ctx.send(
            f"❌ Fehler: `{error}`"
        )


@bot.command()
async def cl(ctx, match_id: str):

    try:
        lineup = await asyncio.to_thread(
            get_uefa_cl_lineup,
            match_id,
        )

        await ctx.send(
            embed=create_lineup_embed(
                lineup
            )
        )

    except Exception as error:
        await ctx.send(
            f"❌ Fehler: `{error}`"
        )


@bot.command()
async def el(ctx, match_id: str):

    try:
        lineup = await asyncio.to_thread(
            get_uefa_el_lineup,
            match_id,
        )

        await ctx.send(
            embed=create_lineup_embed(
                lineup
            )
        )

    except Exception as error:
        await ctx.send(
            f"❌ Fehler: `{error}`"
        )


@bot.command()
async def ecl(ctx, match_id: str):

    try:
        lineup = await asyncio.to_thread(
            get_uefa_ecl_lineup,
            match_id,
        )

        await ctx.send(
            embed=create_lineup_embed(
                lineup
            )
        )

    except Exception as error:
        await ctx.send(
            f"❌ Fehler: `{error}`"
        )


@bot.command()
async def ligue1(ctx, match_id: str):

    try:
        lineup = await asyncio.to_thread(
            get_ligue1_lineup,
            match_id,
        )

        await ctx.send(
            embed=create_lineup_embed(
                lineup
            )
        )

    except Exception as error:
        await ctx.send(
            f"❌ Fehler: `{error}`"
        )


@bot.command()
async def ligue2(ctx, match_id: str):

    try:
        lineup = await asyncio.to_thread(
            get_ligue2_lineup,
            match_id,
        )

        await ctx.send(
            embed=create_lineup_embed(
                lineup
            )
        )

    except Exception as error:
        await ctx.send(
            f"❌ Fehler: `{error}`"
        )


# ============================================================
# GENERISCHE LIGA-PRÜFUNG
# ============================================================

async def check_standard_league(
    channel,
    now,
    league_name,
    key_prefix,
    flag,
    get_matches,
    get_lineup,
):

    try:
        matches = await asyncio.to_thread(
            get_matches,
            2,
        )

    except Exception as error:
        print(
            f"❌ {league_name}-Spielplan: {error}"
        )
        return

    for match in matches:

        try:
            kickoff = normalize_datetime(
                match["kickoff"]
            )

            home_team = match[
                "home_team"
            ]

            away_team = match[
                "away_team"
            ]

            match_reference = match[
                "url"
            ]

        except Exception as error:
            print(
                f"⚠️ {league_name}: Ungültige Matchdaten: {error}"
            )
            continue

        match_key = (
            f"{key_prefix}_"
            f"{kickoff.strftime('%Y-%m-%d_%H-%M')}_"
            f"{home_team}_"
            f"{away_team}"
        )

        if match_key in posted_matches:
            continue

        check_start = (
            kickoff
            - timedelta(minutes=90)
        )

        check_end = (
            kickoff
            + timedelta(minutes=30)
        )

        if now < check_start:
            continue

        if now > check_end:
            continue

        print(
            f"{flag} {league_name}: "
            f"{home_team} vs. {away_team} "
            f"({kickoff.strftime('%d.%m. %H:%M')})"
        )

        try:
            lineup = await asyncio.to_thread(
                get_lineup,
                match_reference,
            )

        except ValueError as error:
            print(
                f"⏳ {league_name}: {error}"
            )
            continue

        except Exception as error:
            print(
                f"⚠️ {league_name}: {error}"
            )
            continue

        if lineup is None:
            print(
                f"⏳ {league_name}: Aufstellung noch nicht verfügbar."
            )
            continue

        if len(
            lineup.home_team.starters
        ) != 11:
            continue

        if len(
            lineup.away_team.starters
        ) != 11:
            continue

        if not lineup.home_team.substitutes:
            continue

        if not lineup.away_team.substitutes:
            continue

        try:
            await channel.send(
                embed=create_lineup_embed(
                    lineup
                )
            )

        except Exception as error:
            print(
                f"❌ Discord: {error}"
            )
            continue

        posted_matches.add(
            match_key
        )

        save_posted_matches(
            posted_matches
        )

        print(
            f"✅ {league_name} gepostet: "
            f"{home_team} vs. {away_team}"
        )


# ============================================================
# HNL
# ============================================================

async def check_hnl(
    channel,
    now,
):

    try:
        matches = await asyncio.to_thread(
            get_hnl_upcoming_matches,
            2,
        )

    except Exception as error:
        print(
            f"❌ HNL-Spielplan: {error}"
        )
        return

    for match in matches:

        kickoff = normalize_datetime(
            match["kickoff"]
        )

        home_team = match[
            "home_team"
        ]

        away_team = match[
            "away_team"
        ]

        match_key = (
            f"HNL_"
            f"{kickoff.strftime('%Y-%m-%d_%H-%M')}_"
            f"{home_team}_"
            f"{away_team}"
        )

        if match_key in posted_matches:
            continue

        if now < (
            kickoff
            - timedelta(minutes=90)
        ):
            continue

        if now > (
            kickoff
            + timedelta(minutes=30)
        ):
            continue

        try:
            match_url = await asyncio.to_thread(
                find_hnl_match_url,
                home_team,
                away_team,
            )

            if not match_url:
                continue

            lineup = await asyncio.to_thread(
                get_hnl_lineup,
                match_url,
            )

        except Exception as error:
            print(
                f"⏳ HNL: {error}"
            )
            continue

        if lineup is None:
            continue

        if len(
            lineup.home_team.starters
        ) != 11:
            continue

        if len(
            lineup.away_team.starters
        ) != 11:
            continue

        if not lineup.home_team.substitutes:
            continue

        if not lineup.away_team.substitutes:
            continue

        try:
            await channel.send(
                embed=create_lineup_embed(
                    lineup
                )
            )

        except Exception as error:
            print(
                f"❌ Discord: {error}"
            )
            continue

        posted_matches.add(
            match_key
        )

        save_posted_matches(
            posted_matches
        )


# ============================================================
# MLS
# ============================================================

async def check_mls(
    channel,
    now,
):

    try:
        matches = await asyncio.to_thread(
            get_mls_upcoming_matches,
            2,
        )

    except Exception as error:
        print(
            f"❌ MLS-Spielplan: {error}"
        )
        return

    for match in matches:

        kickoff = normalize_datetime(
            match["kickoff"]
        )

        home_team = match[
            "home_team"
        ]

        away_team = match[
            "away_team"
        ]

        match_id = match[
            "match_id"
        ]

        match_key = (
            f"MLS_{match_id}"
        )

        if match_key in posted_matches:
            continue

        if now < (
            kickoff
            - timedelta(minutes=90)
        ):
            continue

        if now > (
            kickoff
            + timedelta(minutes=30)
        ):
            continue

        try:
            lineup = await asyncio.to_thread(
                get_mls_lineup,
                match_id,
            )

        except Exception as error:
            print(
                f"⚠️ MLS: {error}"
            )
            continue

        if lineup is None:
            continue

        if len(
            lineup.home_team.starters
        ) != 11:
            continue

        if len(
            lineup.away_team.starters
        ) != 11:
            continue

        if not lineup.home_team.substitutes:
            continue

        if not lineup.away_team.substitutes:
            continue

        try:
            await channel.send(
                embed=create_lineup_embed(
                    lineup
                )
            )

        except Exception as error:
            print(
                f"❌ Discord: {error}"
            )
            continue

        posted_matches.add(
            match_key
        )

        save_posted_matches(
            posted_matches
        )


# ============================================================
# PORTUGAL
# ============================================================

async def check_portugal(
    channel,
    now,
):

    try:
        matches = await asyncio.to_thread(
            get_portugal_upcoming_matches,
            2,
        )

    except Exception as error:
        print(
            f"❌ Primeira-Liga-Spielplan: {error}"
        )
        return

    for match in matches:

        kickoff = normalize_datetime(
            match["kickoff"]
        )

        home_team = match[
            "home_team"
        ]

        away_team = match[
            "away_team"
        ]

        event_id = match[
            "event_id"
        ]

        match_key = (
            f"PORTUGAL_{event_id}"
        )

        if match_key in posted_matches:
            continue

        if now < (
            kickoff
            - timedelta(minutes=90)
        ):
            continue

        if now > (
            kickoff
            + timedelta(minutes=30)
        ):
            continue

        try:
            lineup = await asyncio.to_thread(
                get_portugal_lineup,
                event_id,
            )

        except Exception as error:
            print(
                f"⏳ Primeira Liga: {error}"
            )
            continue

        if lineup is None:
            continue

        if len(
            lineup.home_team.starters
        ) != 11:
            continue

        if len(
            lineup.away_team.starters
        ) != 11:
            continue

        if not lineup.home_team.substitutes:
            continue

        if not lineup.away_team.substitutes:
            continue

        try:
            await channel.send(
                embed=create_lineup_embed(
                    lineup
                )
            )

        except Exception as error:
            print(
                f"❌ Discord: {error}"
            )
            continue

        posted_matches.add(
            match_key
        )

        save_posted_matches(
            posted_matches
        )


# ============================================================
# AUTOMATISCHE PRÜFUNG
# ============================================================

@tasks.loop(
    minutes=2
)
async def automatic_lineup_check():

    now = datetime.now(
        BERLIN_TIMEZONE
    )

    print(
        f"[{now.strftime('%H:%M:%S')}] "
        "🔎 Prüfe Aufstellungen..."
    )

    channel = bot.get_channel(
        LINEUP_CHANNEL_ID
    )

    if channel is None:

        try:
            channel = await bot.fetch_channel(
                LINEUP_CHANNEL_ID
            )

        except Exception as error:
            print(
                f"❌ Discord-Channel: {error}"
            )
            return

    await check_hnl(
        channel,
        now,
    )

    await check_standard_league(
        channel,
        now,
        "Bundesliga",
        "BUNDESLIGA",
        "🇩🇪",
        get_bundesliga_upcoming_matches,
        get_bundesliga_lineup,
    )

    await check_standard_league(
        channel,
        now,
        "2. Bundesliga",
        "BUNDESLIGA2",
        "🇩🇪",
        get_bundesliga2_upcoming_matches,
        get_bundesliga2_lineup,
    )

    await check_standard_league(
        channel,
        now,
        "Premier League",
        "PREMIERLEAGUE",
        "🏴",
        get_premierleague_upcoming_matches,
        get_premierleague_lineup,
    )

    await check_standard_league(
        channel,
        now,
        "La Liga",
        "LALIGA",
        "🇪🇸",
        get_laliga_upcoming_matches,
        get_laliga_lineup,
    )

    await check_mls(
        channel,
        now,
    )

    await check_standard_league(
        channel,
        now,
        "Österreich Bundesliga",
        "AUSTRIA",
        "🇦🇹",
        get_austria_upcoming_matches,
        get_austria_lineup,
    )

    await check_portugal(
        channel,
        now,
    )

    await check_standard_league(
        channel,
        now,
        "Jupiler Pro League",
        "BELGIUM",
        "🇧🇪",
        get_belgium_upcoming_matches,
        get_belgium_lineup,
    )

    await check_standard_league(
        channel,
        now,
        "Champions League",
        "UEFA_CL",
        "🏆",
        get_uefa_cl_upcoming_matches,
        get_uefa_cl_lineup,
    )

    await check_standard_league(
        channel,
        now,
        "Europa League",
        "UEFA_EL",
        "🏆",
        get_uefa_el_upcoming_matches,
        get_uefa_el_lineup,
    )

    await check_standard_league(
        channel,
        now,
        "Conference League",
        "UEFA_ECL",
        "🏆",
        get_uefa_ecl_upcoming_matches,
        get_uefa_ecl_lineup,
    )

    await check_standard_league(
        channel,
        now,
        "Ligue 1",
        "LIGUE1",
        "🇫🇷",
        get_ligue1_upcoming_matches,
        get_ligue1_lineup,
    )

    await check_standard_league(
        channel,
        now,
        "Ligue 2",
        "LIGUE2",
        "🇫🇷",
        get_ligue2_upcoming_matches,
        get_ligue2_lineup,
    )


@automatic_lineup_check.before_loop
async def before_automatic_lineup_check():

    await bot.wait_until_ready()


# ============================================================
# START
# ============================================================

bot.run(
    TOKEN
)