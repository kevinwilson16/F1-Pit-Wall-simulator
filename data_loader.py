# data_loader.py
# Reads the F1DB csv files and pulls out the data the simulator needs.

import csv
import os
import statistics

from tyres import FUEL_PER_LAP

# the data folder sits next to this file, so the program works from any folder
DATA_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

FIRST_YEAR = 2018         # older seasons have different rules and missing data
MIN_LAPS = 30             # skip races that were stopped very early
DEFAULT_PIT_LOSS = 23.0   # seconds, used if a race has no pit stop data
MIN_PIT_TIME = 15         # pit times outside this range (in seconds) are
MAX_PIT_TIME = 60         # ignored, for example stops during a red flag
PACE_OFFSET = 0.6         # turns a fastest lap into a normal race pace (found by testing)
PACE_SPREAD = 0.6         # fastest laps make the gaps between drivers look too big, so shrink them

# a few team names that look wrong when capitalised automatically
TEAM_NAMES = {
    "mclaren": "McLaren",
    "rb": "RB",
    "alphatauri": "AlphaTauri",
    "alfa-romeo": "Alfa Romeo",
    "kick-sauber": "Kick Sauber",
}


def read_csv(file_name):
    """Reads one csv file and returns a list of dictionaries (one per row)."""
    path = os.path.join(DATA_FOLDER, file_name)
    try:
        with open(path, newline="", encoding="utf-8") as file:
            return list(csv.DictReader(file))
    except FileNotFoundError:
        raise FileNotFoundError("Could not find " + file_name + " in the data folder.")


def load_data():
    """Loads all the csv files we need into one dictionary."""
    data = {}
    data["races"] = read_csv("f1db-races.csv")
    data["results"] = read_csv("f1db-races-race-results.csv")
    data["fastest"] = read_csv("f1db-races-fastest-laps.csv")
    data["pits"] = read_csv("f1db-races-pit-stops.csv")
    data["drivers"] = read_csv("f1db-drivers.csv")
    return data


def pretty_name(text):
    """Turns an id like 'red-bull' into 'Red Bull'."""
    if text in TEAM_NAMES:
        return TEAM_NAMES[text]
    return text.replace("-", " ").title()


def get_pit_loss(pit_times):
    """Typical time lost in a pit stop, from a list of pit stop times in seconds."""
    good_times = []
    for seconds in pit_times:
        if MIN_PIT_TIME <= seconds <= MAX_PIT_TIME:
            good_times.append(seconds)

    if len(good_times) < 5:
        return DEFAULT_PIT_LOSS
    # the median is not affected much by a few strange values
    return statistics.median(good_times)


def get_races(data):
    """Returns the races we can simulate (recent seasons with enough data)."""
    result_ids = set()
    stop_counts = {}      # race id -> list of pit stop counts for each finisher
    for row in data["results"]:
        result_ids.add(row["raceId"])
        if row["pitStops"] != "":
            stop_counts.setdefault(row["raceId"], []).append(int(row["pitStops"]))

    # count how many drivers have a fastest lap time in each race
    fastest_count = {}
    for row in data["fastest"]:
        if row["timeMillis"] != "":
            race_id = row["raceId"]
            fastest_count[race_id] = fastest_count.get(race_id, 0) + 1

    # pit stop times for each race
    pit_times = {}
    for row in data["pits"]:
        if row["timeMillis"] != "":
            pit_times.setdefault(row["raceId"], []).append(int(row["timeMillis"]) / 1000)

    races = []
    for row in data["races"]:
        if int(row["year"]) < FIRST_YEAR or row["laps"] == "":
            continue
        if int(row["laps"]) < MIN_LAPS:
            continue
        if row["id"] not in result_ids or fastest_count.get(row["id"], 0) < 10:
            continue

        # average stops drivers really made, used to guess how hard the track is on tyres
        counts = stop_counts.get(row["id"], [1])
        avg_stops = max(1.0, sum(counts) / len(counts))
        wear = 0.6 + 0.4 * avg_stops
        wear = max(0.8, min(wear, 1.8))

        race = {
            "id": row["id"],
            "year": int(row["year"]),
            "round": int(row["round"]),
            "name": pretty_name(row["grandPrixId"]) + " Grand Prix",
            "laps": int(row["laps"]),
            "pit_loss": get_pit_loss(pit_times.get(row["id"], [])),
            "avg_stops": avg_stops,
            "wear": wear,
        }
        races.append(race)
    return races


def get_seasons(races):
    """Returns the list of years that have races, in order."""
    seasons = []
    for race in races:
        if race["year"] not in seasons:
            seasons.append(race["year"])
    seasons.sort()
    return seasons


def get_grid(driver):
    return driver["grid"]


def get_field(data, race):
    """Builds the list of drivers for a race, with grid position and race pace."""
    driver_info = {}
    for row in data["drivers"]:
        driver_info[row["id"]] = row

    # fastest lap of each driver in this race
    fastest = {}
    for row in data["fastest"]:
        if row["raceId"] == race["id"] and row["timeMillis"] != "":
            fastest[row["driverId"]] = row

    field = []
    for row in data["results"]:
        if row["raceId"] != race["id"]:
            continue

        driver_id = row["driverId"]
        info = driver_info[driver_id]

        # pit lane starters have no grid number, so put them at the back
        if row["gridPositionNumber"] == "":
            grid = 100 + len(field)
        else:
            grid = int(row["gridPositionNumber"])

        driver = {
            "id": driver_id,
            "name": info["name"],
            "abbr": info["abbreviation"],
            "team": pretty_name(row["constructorId"]),
            "grid": grid,
            "real_grid": row["gridPositionText"],
            "real_finish": row["positionText"],
            "pace": None,
        }

        if driver_id in fastest:
            seconds = int(fastest[driver_id]["timeMillis"]) / 1000
            lap = fastest[driver_id]["lap"]
            if lap != "":
                # take out the time lost to the fuel that was in the car
                laps_left = race["laps"] - int(lap) + 1
                seconds = seconds - FUEL_PER_LAP * laps_left
            driver["pace"] = seconds + PACE_OFFSET

        field.append(driver)

    # number the grid 1, 2, 3... with no gaps
    field.sort(key=get_grid)
    for i in range(len(field)):
        field[i]["grid"] = i + 1

    # drivers with no fastest lap get a pace slightly slower than the slowest known
    known = []
    for driver in field:
        if driver["pace"] is not None:
            known.append(driver["pace"])
    slowest = max(known)
    for driver in field:
        if driver["pace"] is None:
            driver["pace"] = slowest + 0.5

    # pull every pace towards the middle of the field
    paces = []
    for driver in field:
        paces.append(driver["pace"])
    middle = statistics.median(paces)
    for driver in field:
        driver["pace"] = middle + PACE_SPREAD * (driver["pace"] - middle)

    return field
