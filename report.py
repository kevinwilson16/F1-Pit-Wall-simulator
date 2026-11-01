# report.py
# Formats times, builds the race summary, and saves/loads the results history.

import csv
import datetime
import os

from simulator import get_classification
from strategy import find_best_strategies, clean_air_race_time

RESULTS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
HISTORY_FILE = os.path.join(RESULTS_FOLDER, "history.csv")
HISTORY_HEADER = ["date", "season", "race", "driver", "grid", "finish", "stops", "strategy"]


def format_lap_time(seconds):
    """92.608 -> 1:32.608"""
    minutes = int(seconds // 60)
    rest = seconds - minutes * 60
    return str(minutes) + ":" + format(rest, "06.3f")


def format_race_time(seconds):
    """5504.742 -> 1:31:44.742"""
    hours = int(seconds // 3600)
    minutes = int((seconds - hours * 3600) // 60)
    rest = seconds - hours * 3600 - minutes * 60
    return str(hours) + ":" + format(minutes, "02d") + ":" + format(rest, "06.3f")


def format_gap(seconds):
    return "+" + format(seconds, ".3f")


def strategy_text(strategy):
    """Example: MEDIUM > HARD (pit on lap 22)"""
    pit_laps = []
    for lap in strategy["pit_laps"]:
        pit_laps.append(str(lap))
    return " > ".join(strategy["compounds"]) + " (pit on lap " + ", ".join(pit_laps) + ")"


def short_strategy(strategy):
    """Example: M>H"""
    letters = []
    for compound in strategy["compounds"]:
        letters.append(compound[0])
    return ">".join(letters)


def place_text(text):
    """'3' -> 'P3', but 'DNF' stays as 'DNF'."""
    if text.isdigit():
        return "P" + text
    return text


def build_summary(race, user_car, state):
    """Returns the race summary as a list of text lines."""
    classification = get_classification(state)
    driver = user_car["driver"]

    lines = []
    lines.append("=" * 64)
    lines.append("RACE SUMMARY - " + str(race["year"]) + " " + race["name"])
    lines.append("=" * 64)

    finishers = []
    for car in classification:
        if not car["retired"]:
            finishers.append(car)
    if len(finishers) == 0:
        lines.append("Nobody finished the race.")
        return lines

    leader = finishers[0]
    leader_lap = leader["total"] / state["laps"]

    #the user's result
    user_position = classification.index(user_car) + 1
    lines.append("Driver:   " + driver["name"] + " (" + driver["team"] + ")")
    lines.append("Strategy: " + strategy_text(user_car["strategy"]))
    if user_car["retired"]:
        lines.append("Result:   RETIRED on lap " + str(user_car["retired_lap"]))
    else:
        change = user_car["grid"] - user_position
        if change > 0:
            change_text = "gained " + str(change) + " places"
        elif change < 0:
            change_text = "lost " + str(-change) + " places"
        else:
            change_text = "same position"
        lines.append("Result:   started P" + str(user_car["grid"]) + ", finished P"
                     + str(user_position) + " (" + change_text + ")")
        lines.append("Pit stops made: " + str(user_car["pits_done"]))
        lines.append("Laps stuck behind slower cars: " + str(user_car["held_up_laps"]))
    if user_car["best_lap"] is not None:
        lines.append("Your best lap: " + format_lap_time(user_car["best_lap"]))
    lines.append("Safety car laps in this race: " + str(state["sc_lap_count"]))
    lines.append("In the real race " + driver["abbr"] + " started " + place_text(driver["real_grid"])
                 + " and finished " + place_text(driver["real_finish"]) + ".")
    lines.append("")

    #the final order (top 10, plus the user's car if they are lower down)
    lines.append("Final classification")
    lines.append("-" * 64)
    for i in range(len(classification)):
        car = classification[i]
        if i >= 10 and car is not user_car:
            continue

        if car["retired"]:
            time_text = "DNF (lap " + str(car["retired_lap"]) + ")"
        elif i == 0:
            time_text = format_race_time(car["total"])
        else:
            gap = car["total"] - leader["total"]
            laps_down = int(gap // leader_lap)
            if laps_down >= 1:
                time_text = "+" + str(laps_down) + " lap(s)"
            else:
                time_text = format_gap(gap)

        marker = ""
        if car is user_car:
            marker = "  <-- you"
        row = "P" + format(i + 1, "<3") + " " + format(car["driver"]["abbr"], "<4")
        row = row + format(car["driver"]["team"], "<16") + format(time_text, ">13")
        row = row + "  " + format(short_strategy(car["strategy"]), "<6") + marker
        lines.append(row)
    lines.append("")

    #how the user's number of stops did compared with the field
    lines.append("How different strategies did")
    lines.append("-" * 64)
    positions_by_stops = {}
    for i in range(len(finishers)):
        stops = finishers[i]["pits_done"]
        if stops not in positions_by_stops:
            positions_by_stops[stops] = []
        positions_by_stops[stops].append(i + 1)

    for stops in sorted(positions_by_stops):
        positions = positions_by_stops[stops]
        average = sum(positions) / len(positions)
        lines.append(str(stops) + "-stop cars: " + str(len(positions))
                     + " finishers, average finish P" + format(average, ".1f"))
    lines.append("Winner's strategy: " + strategy_text(leader["strategy"]))

    #compare with the best plan from the strategy search
    best = find_best_strategies(user_car["pace"], race, how_many=1)
    best_time, best_strategy = best[0]
    your_time = clean_air_race_time(user_car["pace"], user_car["strategy"], race)
    difference = your_time - best_time
    lines.append("")
    lines.append("Strategy check (clear track, no safety car)")
    lines.append("-" * 64)
    lines.append("Fastest plan found: " + strategy_text(best_strategy))
    if difference < 0.5:
        lines.append("Your plan was about as fast as the best plan. Nice work.")
    else:
        lines.append("Your plan was about " + format(difference, ".1f")
                     + " seconds slower than that in a perfect race.")
    return lines


def save_report(lines, file_name):
    """Writes the summary to a text file in the results folder. Returns the path."""
    os.makedirs(RESULTS_FOLDER, exist_ok=True)
    path = os.path.join(RESULTS_FOLDER, file_name)
    with open(path, "w", encoding="utf-8") as file:
        for line in lines:
            file.write(line + "\n")
    return path


def add_to_history(race, user_car, finish_text, path=HISTORY_FILE):
    """Adds one line to the history csv file (creates the file the first time)."""
    folder = os.path.dirname(path)
    if folder != "":
        os.makedirs(folder, exist_ok=True)
    is_new_file = not os.path.exists(path)

    with open(path, "a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if is_new_file:
            writer.writerow(HISTORY_HEADER)
        writer.writerow([
            datetime.date.today().isoformat(),
            race["year"],
            race["name"],
            user_car["driver"]["name"],
            user_car["grid"],
            finish_text,
            user_car["pits_done"],
            short_strategy(user_car["strategy"]),
        ])


def load_history(path=HISTORY_FILE):
    """Returns the saved history as a list of rows. Raises FileNotFoundError if there is none."""
    with open(path, newline="", encoding="utf-8") as file:
        rows = list(csv.reader(file))
    return rows
