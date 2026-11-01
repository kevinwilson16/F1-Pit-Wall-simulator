# main.py
# F1 Pit Wall Strategy Simulator

import time

from data_loader import load_data, get_races, get_seasons, get_field
from strategy import validate_strategy, find_best_strategies, MIN_STINT
from tyres import COMPOUNDS
from simulator import new_race, check_safety_car, run_lap, get_user_car
from report import (format_lap_time, format_gap, strategy_text, build_summary,
                    save_report, add_to_history, load_history)

LAP_DELAY = 0.05   # small pause between laps so the race feels live (0 turns it off)


#getting input from the user

def ask_int(prompt, low, high, default=None):
    """Keeps asking until the user types a whole number between low and high."""
    while True:
        text = input(prompt).strip()
        if text == "" and default is not None:
            return default
        try:
            number = int(text)
        except ValueError:
            print("Please type a whole number.")
            continue

        if number < low or number > high:
            print("Please choose a number from " + str(low) + " to " + str(high) + ".")
            continue
        return number


def ask_yes_no(prompt):
    while True:
        text = input(prompt + " (y/n): ").strip().lower()
        if text == "y" or text == "yes":
            return True
        if text == "n" or text == "no":
            return False
        print("Please type y or n.")


def ask_compound(prompt):
    while True:
        text = input(prompt + " (S = soft, M = medium, H = hard): ").strip().upper()
        for name in COMPOUNDS:
            if text == name or text == name[0]:
                return name
        print("Please type S, M or H.")


def ask_seed():
    """Optional seed so the same race can be run again with the same random events."""
    while True:
        text = input("Random seed (press Enter for a different race every time): ").strip()
        if text == "":
            return None
        try:
            return int(text)
        except ValueError:
            print("The seed must be a whole number.")


def ask_strategy(total_laps):
    """Asks the user for their tyre strategy and checks that it is allowed."""
    while True:
        stops = ask_int("How many pit stops (1-3)? ", 1, 3)
        compounds = [ask_compound("Starting tyre")]
        pit_laps = []

        for stop in range(1, stops + 1):
            earliest = MIN_STINT
            if len(pit_laps) > 0:
                earliest = pit_laps[-1] + MIN_STINT
            # leave enough laps for the stints that still have to come
            latest = total_laps - MIN_STINT * (stops - stop + 1)

            lap = ask_int("Pit stop " + str(stop) + " at the end of which lap? ("
                          + str(earliest) + "-" + str(latest) + "): ", earliest, latest)
            pit_laps.append(lap)
            compounds.append(ask_compound("Tyre to put on at stop " + str(stop)))

        strategy = {"compounds": compounds, "pit_laps": pit_laps}
        try:
            validate_strategy(strategy, total_laps)
        except ValueError as error:
            print("That strategy is not allowed: " + str(error))
            print("Let's try again.")
        else:
            return strategy


#choosing the race, driver and strategy

def choose_race(races):
    seasons = get_seasons(races)
    print("\nSeasons available: " + str(seasons[0]) + " to " + str(seasons[-1]))
    season = ask_int("Which season? ", seasons[0], seasons[-1])

    season_races = []
    for race in races:
        if race["year"] == season:
            season_races.append(race)

    print("\nRaces in " + str(season) + ":")
    for i in range(len(season_races)):
        race = season_races[i]
        print("  " + format(i + 1, ">2") + ". " + race["name"] + " (" + str(race["laps"]) + " laps)")
    number = ask_int("Which race? ", 1, len(season_races))
    return season_races[number - 1]


def show_briefing(race):
    if race["wear"] < 1.15:
        wear_text = "low"
    elif race["wear"] < 1.45:
        wear_text = "medium"
    else:
        wear_text = "high"

    print("\n--- " + str(race["year"]) + " " + race["name"] + " ---")
    print("Distance:      " + str(race["laps"]) + " laps")
    print("Pit stop loss: " + format(race["pit_loss"], ".1f") + " seconds")
    print("Tyre wear:     " + wear_text + " (drivers averaged "
          + format(race["avg_stops"], ".1f") + " stops here)")
    print("Tyre life:     ", end="")
    for name in COMPOUNDS:
        life = COMPOUNDS[name]["life"] / race["wear"]
        print(name + " ~" + str(round(life)) + " laps   ", end="")
    print()


def choose_driver(field):
    print("\nDrivers on the grid:")
    print("  No  Driver                Team              Grid")
    for i in range(len(field)):
        driver = field[i]
        print("  " + format(i + 1, ">2") + "  " + format(driver["name"], "<20") + "  "
              + format(driver["team"], "<16") + "  P" + str(driver["grid"]))
    number = ask_int("Pick your driver (number): ", 1, len(field))
    return field[number - 1]


def choose_strategy(driver, race, suggest):
    if not suggest:
        return ask_strategy(race["laps"])

    print("\nSearching for good strategies...")
    plans = find_best_strategies(driver["pace"], race)
    print("Fastest plans for " + driver["name"] + " on a clear track:")
    for i in range(len(plans)):
        print("  " + str(i + 1) + ". " + strategy_text(plans[i][1]))

    choice = ask_int("Pick a plan (1-" + str(len(plans)) + ") or 0 to enter your own: ", 0, len(plans))
    if choice == 0:
        return ask_strategy(race["laps"])
    return plans[choice - 1][1]


#running the race

def print_lap(info, show_every, total_laps):
    """Prints the events and the user's line for one lap."""
    for text in info["events"]:
        print("   >> Lap " + str(info["lap"]) + ": " + text)

    user = info["user"]
    if user is None:
        return
    if user["retired"]:
        print("   >> Your car is out of the race.")
        return

    lap = info["lap"]
    # only a pit stop forces a line to be shown, other notes only show on normal update laps
    important = "PIT STOP" in user["notes"]
    if lap % show_every != 0 and lap != 1 and lap != total_laps and not important:
        return

    if user["gap_to_leader"] < 0.001:
        gap_text = "Leader"
    else:
        gap_text = format_gap(user["gap_to_leader"])

    line = "Lap " + format(lap, ">2") + "/" + str(total_laps)
    line = line + "  P" + format(user["position"], "<2")
    line = line + "  " + format(user["compound"], "<6") + " (" + format(user["age"], ">2") + " laps old)"
    line = line + "  " + format_lap_time(user["lap_time"])
    line = line + "  " + format(gap_text, ">8")
    if len(user["notes"]) > 0:
        line = line + "  " + ", ".join(user["notes"])
    print(line)


def run_race(state, show_every):
    """The main race loop: one pass of the loop is one lap."""
    user = get_user_car(state)
    print("\nLights out!\n")

    while state["lap"] < state["laps"]:
        safety_car_out = check_safety_car(state)

        # the user decides if they want to use the safety car to pit
        pit_now = False
        stops_left = len(user["strategy"]["pit_laps"]) - user["pits_done"]
        if safety_car_out and not user["retired"] and stops_left > 0:
            print("\n!! Safety car on lap " + str(state["lap"] + 1) + ". Your "
                  + user["strategy"]["compounds"][user["stint"]] + " tyres are "
                  + str(user["tyre_age"]) + " laps old.")
            pit_now = ask_yes_no("Pit now? (uses up your next planned stop)")

        info = run_lap(state, pit_now)
        print_lap(info, show_every, state["laps"])
        time.sleep(LAP_DELAY)

    print("\nChequered flag!\n")


def play_race(races, data, suggest):
    race = choose_race(races)
    field = get_field(data, race)
    show_briefing(race)

    driver = choose_driver(field)
    grid = ask_int("Starting grid position (1-" + str(len(field)) + ", Enter to keep P"
                   + str(driver["grid"]) + "): ", 1, len(field), driver["grid"])

    strategy = choose_strategy(driver, race, suggest)
    print("\nYour strategy: " + strategy_text(strategy))

    seed = ask_seed()
    show_every = ask_int("Show an update every how many laps? (1-10, Enter for 5): ", 1, 10, 5)

    state = new_race(race, field, driver["id"], strategy, grid, seed=seed)
    run_race(state, show_every)

    user = get_user_car(state)
    lines = build_summary(race, user, state)
    for line in lines:
        print(line)

    # work out the finishing position for the history file
    finish_text = "DNF"
    if not user["retired"]:
        finish_text = str(user["positions"][-1])
    try:
        add_to_history(race, user, finish_text)
    except OSError:
        print("(Could not save to the history file.)")

    if ask_yes_no("\nSave this summary to a text file?"):
        file_name = (str(race["year"]) + "_" + race["name"].replace(" ", "_")
                     + "_" + driver["abbr"] + ".txt")
        try:
            path = save_report(lines, file_name)
            print("Saved to " + path)
        except OSError:
            print("Sorry, the file could not be saved.")


def show_history():
    try:
        rows = load_history()
    except FileNotFoundError:
        print("\nNo saved races yet. Simulate a race first.")
        return

    print("\nYour past races:")
    for row in rows:
        print("  " + format(row[0], "<12") + format(row[1], "<8") + format(row[2], "<28")
              + format(row[3], "<20") + format(row[4], "<6") + format(row[5], "<8")
              + format(row[6], "<7") + row[7])


def main():
    print("=" * 50)
    print("   F1 PIT WALL STRATEGY SIMULATOR")
    print("=" * 50)

    print("Loading race data...")
    try:
        data = load_data()
    except FileNotFoundError as error:
        print("Problem loading the data: " + str(error))
        print("Make sure the 'data' folder is in the same folder as main.py.")
        return
    races = get_races(data)

    while True:
        print("\nMAIN MENU")
        print("  1. Simulate a race with my own strategy")
        print("  2. Simulate a race with strategy suggestions")
        print("  3. View my past results")
        print("  4. Quit")
        choice = ask_int("Choose an option (1-4): ", 1, 4)

        if choice == 1:
            play_race(races, data, False)
        elif choice == 2:
            play_race(races, data, True)
        elif choice == 3:
            show_history()
        else:
            break

    print("Thanks for playing!")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye!")