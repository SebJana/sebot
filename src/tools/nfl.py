import requests
from datetime import datetime, date

SEASON_TYPES = {
    1: "Pre Season",
    2: "Regular Season",
    3: "Post Season",
    4: "Off Season",
}

ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

def parse_date_only(dt_str: str) -> date:
    """Parse an ISO-8601 date/time string and return a date object.

    The function accepts an ISO-8601 date or datetime string. If the
    string ends with a Z (UTC), it is converted to a +00:00 offset so
    that `datetime.fromisoformat` can parse it. The returned value is a
    `datetime.date` representing the calendar date (time portion is
    discarded).

    Args:
        dt_str: ISO-8601 formatted date or datetime string, e.g.
            "2025-12-14T15:30:00Z" or "2025-12-14".

    Returns:
        A `datetime.date` instance representing the parsed date.

    Raises:
        ValueError: If `dt_str` is not a valid ISO-8601 date/time string.
    """
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).date()

# TODO cache the calendar 
def get_nfl_season_and_week(input_date: str):
    """Return the NFL season type and week for a given date.

    This function accepts a date in several forms: an ISO-8601 string,
    a `datetime.datetime`, or a `datetime.date`. It queries the ESPN
    scoreboard API to fetch the league calendar and finds the season
    entry and week that contains the provided date.

    Args:
        input_date: A date string (ISO-8601), `datetime.datetime`, or
            `datetime.date` to look up.

    Returns:
        A dict with keys:
            - "season_type": human-readable season label (e.g. "Regular Season")
            - "season_type_id": integer season type id (1=Pre,2=Regular,3=Post,4=Off)
            - "week": integer week number if the date falls inside a specific week,
              or `None` if the date is within the season but not within a week.
        Returns `None` if the date does not fall inside any season in the
        ESPN calendar.

    Raises:
        TypeError: If `input_date` is not a str, datetime, or date.
    """
    # Normalize input to a date object
    input_date = _normalize_input_date(input_date)

    calendar = _fetch_calendar()

    # Find the season that contains the date
    season = _find_season_for_date(calendar, input_date)
    if season is None:
        return None

    # Try to find a specific week within the season
    week_entry = _find_week_in_season(season, input_date)
    if week_entry is not None:
        return {
            "season_type": season.get("label"),
            "season_type_id": int(season.get("value")) if season.get("value") is not None else None,
            "week": int(week_entry.get("value")) if week_entry.get("value") is not None else None,
        }

    # Date is inside season but not inside a specific week
    return {
        "season_type": season.get("label"),
        "season_type_id": int(season.get("value")) if season.get("value") is not None else None,
        "week": None,
    }


def _normalize_input_date(input_date):
    """Normalize input to a `datetime.date`.

    Accepts an ISO-8601 string, `datetime.datetime`, or `datetime.date`.
    Raises TypeError for other types.
    """
    if isinstance(input_date, str):
        return parse_date_only(input_date)
    if isinstance(input_date, datetime):
        return input_date.date()
    if isinstance(input_date, date):
        return input_date
    raise TypeError("input_date must be a str, datetime or date")


def _fetch_calendar():
    """Fetch and return the league calendar from ESPN API.

    Returns an empty list if the expected structure is missing.
    """
    data = requests.get(ESPN_URL).json()
    leagues = data.get("leagues") or []
    if not leagues:
        return []
    league = leagues[0]
    return league.get("calendar", []) or []


def _find_season_for_date(calendar, input_date):
    """Return the season dict from calendar that contains input_date, or None."""
    for season in calendar:
        season_start = parse_date_only(season["startDate"])
        season_end = parse_date_only(season["endDate"])
        if season_start <= input_date <= season_end:
            return season
    return None


def _find_week_in_season(season, input_date):
    """Return the week entry dict inside season that contains input_date, or None."""
    for entry in season.get("entries", []):
        week_start = parse_date_only(entry["startDate"])
        week_end = parse_date_only(entry["endDate"])
        if week_start <= input_date <= week_end:
            return entry
    return None

def get_games_and_scores_week(week: int, season_type: int):
    """Fetch games and basic scores for a specific NFL week and season type.

    This function queries the ESPN scoreboard API for the provided
    `season_type` (numeric code) and `week`. It returns a list of game
    summaries with the game's name, status, scheduled date/time (ISO
    8601 string), and a list of competitors with team name and score.

    Args:
        week: The NFL week number to query (integer).
        season_type: Numeric season type (1=Preseason, 2=Regular, 3=Postseason, 4=Offseason).

    Returns:
        A list of dicts, each with keys:
            - "name": Event name (string)
            - "status": Human-readable game status (string, may be None)
            - "date": ISO-8601 date/time string for the event
            - "competitors": List of competitor dicts with keys "team" and "score".

    Notes:
        - This performs a network request and will raise requests exceptions
          if the network call fails. The function does not retry or cache.
    """
    params = {"seasontype": season_type, "week": week}
    response = requests.get(ESPN_URL, params=params).json()
    games = []

    for event in response.get("events", []):
        game_info = {
            "name": event.get("name"),
            "status": event.get("status", {}).get("type", {}).get("description"),
            "date": event.get("date"),  # ISO 8601 date/time
            "competitors": []
        }

        # Extract team names and scores
        competitions = event.get("competitions", [])
        if competitions:
            for competitor in competitions[0].get("competitors", []):
                team = competitor.get("team")
                game_info["competitors"].append({
                    "team": team.get("displayName"),
                    "score": competitor.get("score")
                })

        games.append(game_info)
    return games

def get_games_and_scores_from_date(date: str):
    """Get games and scores for the NFL week that contains `date`.

    This convenience wrapper determines the season type and week for the
    provided date (using `get_nfl_season_and_week`) and then fetches the
    games for that week using `get_games_and_scores_week`. The given date
    is assigned the week of NFL it falls into.

    Args:
        date: A date string (ISO-8601), `datetime.datetime`, or
            `datetime.date` accepted by `get_nfl_season_and_week`.

    Returns:
        A list of game summary dicts (same format as
        `get_games_and_scores_week`). If the date cannot be mapped to a
        season/week or the season information is missing, an empty list
        is returned.
    """

    season_and_week = get_nfl_season_and_week(date)

    season = season_and_week.get("season_type_id")
    week = season_and_week.get("week")

    if not season_and_week or (week is None or season is None):
        return []

    return get_games_and_scores_week(week=week, season_type=season)

print(get_games_and_scores_from_date("2025-12-14"))
print(get_games_and_scores_week(14, 2))