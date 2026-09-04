from dataclasses import dataclass, field


@dataclass
class TeamLineup:
    team_name: str
    starters: list[str] = field(default_factory=list)
    substitutes: list[str] = field(default_factory=list)


@dataclass
class MatchLineup:
    league: str
    home_team: TeamLineup
    away_team: TeamLineup
    match_url: str = ""