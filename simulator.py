# simulator.py
# Runs the race one lap at a time using a loop (main.py calls run_lap for every lap).

import random

from tyres import lap_time
from strategy import make_ai_strategy

SC_CHANCE = 0.012      # chance per lap that a safety car comes out
DNF_CHANCE = 0.0008    # chance per lap that a car retires
SC_FACTOR = 1.4        # safety car laps are this much slower than a normal lap
SC_PIT_FACTOR = 0.55   # a pit stop under the safety car costs less time
SC_GAP = 1.0           # the cars bunch up to this gap (seconds) behind the safety car
NOISE = 0.25           # random lap time change (seconds)
GRID_GAP = 0.2         # seconds between each grid slot at the start
MIN_GAP = 0.5          # closest a car can follow the car in front
PASS_MARGIN = 0.7      # how much quicker a car must be to get past


def get_total(car):
    return car["total"]


def get_laps_done(car):
    return car["laps_done"]


def get_grid(driver):
    return driver["grid"]


def make_car(driver, grid_slot, strategy, is_user):
    """Creates the dictionary that tracks one car during the race."""
    car = {
        "driver": driver,
        "pace": driver["pace"],
        "strategy": strategy,
        "is_user": is_user,
        "grid": grid_slot,
        "total": (grid_slot - 1) * GRID_GAP,
        "stint": 0,           # which set of tyres the car is on
        "tyre_age": 0,
        "pits_done": 0,
        "laps_done": 0,
        "retired": False,
        "retired_lap": None,
        "best_lap": None,
        "held_up_laps": 0,
        "positions": [],
    }
    return car


def new_race(race, field, user_id, user_strategy, user_grid,
             seed=None, sc_chance=SC_CHANCE, dnf_chance=DNF_CHANCE):
    """Sets up a race and returns the state dictionary."""
    rng = random.Random(seed)

    # put the drivers in real grid order
    drivers = sorted(field, key=get_grid)

    # move the user's driver to the grid slot they chose (swap with whoever is there)
    user_index = 0
    for i in range(len(drivers)):
        if drivers[i]["id"] == user_id:
            user_index = i
    new_index = user_grid - 1
    drivers[user_index], drivers[new_index] = drivers[new_index], drivers[user_index]

    cars = []
    for i in range(len(drivers)):
        is_user = drivers[i]["id"] == user_id
        if is_user:
            strategy = user_strategy
        else:
            strategy = make_ai_strategy(race, rng)
        cars.append(make_car(drivers[i], i + 1, strategy, is_user))

    # the middle pace of the field is used to work out safety car lap times
    paces = sorted([d["pace"] for d in drivers])
    ref_pace = paces[len(paces) // 2]

    state = {
        "laps": race["laps"],
        "cars": cars,
        "pit_loss": race["pit_loss"],
        "wear": race["wear"],
        "ref_pace": ref_pace,
        "lap": 0,
        "sc_laps_left": 0,
        "sc_lap_count": 0,
        "events": [],        # list of (lap, text)
        "rng": rng,
        "sc_chance": sc_chance,
        "dnf_chance": dnf_chance,
    }
    return state


def running_cars(state):
    """Cars still in the race, in race order."""
    running = []
    for car in state["cars"]:
        if not car["retired"]:
            running.append(car)
    running.sort(key=get_total)
    return running


def get_user_car(state):
    for car in state["cars"]:
        if car["is_user"]:
            return car


def check_safety_car(state):
    """Randomly starts a safety car for the next lap. Returns True if one starts."""
    next_lap = state["lap"] + 1

    if state["sc_laps_left"] > 0:
        return False
    # no safety car on the first lap or in the last few laps
    if next_lap < 2 or next_lap > state["laps"] - 3:
        return False

    if state["rng"].random() < state["sc_chance"]:
        state["sc_laps_left"] = state["rng"].randint(3, 5)
        state["events"].append((next_lap, "Safety car deployed"))
        return True
    return False


def wants_to_pit(car, lap, under_sc, user_pits_under_sc, rng):
    """Decides if a car pits at the end of this lap."""
    pit_laps = car["strategy"]["pit_laps"]
    if car["pits_done"] >= len(pit_laps):
        return False

    # the planned pit lap has arrived
    if lap >= pit_laps[car["pits_done"]]:
        return True

    # a safety car makes a cheap stop, so take the next planned stop early
    if under_sc:
        if car["is_user"]:
            return user_pits_under_sc
        if car["tyre_age"] >= 8 and rng.random() < 0.6:
            return True
    return False


def bunch_up(order):
    """Safety car: the gaps between cars shrink to SC_GAP."""
    previous_old_total = order[0]["new_total"]
    for i in range(1, len(order)):
        old_total = order[i]["new_total"]
        gap = old_total - previous_old_total
        if gap > SC_GAP:
            gap = SC_GAP
        order[i]["new_total"] = order[i - 1]["new_total"] + gap
        previous_old_total = old_total


def apply_traffic(order):
    """Cars can't drive through each other. A car stuck behind a slower car loses time."""
    blocker = None
    for car in order:
        # a car in the pit lane is not held up by anyone
        if car["pit_cost"] > 0:
            continue

        if blocker is not None:
            too_close = car["new_total"] < blocker["new_total"] + MIN_GAP
            can_pass = car["lap_t"] < blocker["lap_t"] - PASS_MARGIN
            if too_close and not can_pass:
                car["new_total"] = blocker["new_total"] + MIN_GAP
                car["held_up"] = True
        blocker = car


def run_lap(state, user_pits_under_sc=False):
    """Simulates one lap for every car. Returns a dictionary describing the lap."""
    state["lap"] = state["lap"] + 1
    lap = state["lap"]
    rng = state["rng"]
    under_sc = state["sc_laps_left"] > 0
    laps_left = state["laps"] - (lap - 1)
    if under_sc:
        state["sc_lap_count"] = state["sc_lap_count"] + 1

    order = running_cars(state)

    # step 1: random retirements
    for car in order:
        if rng.random() < state["dnf_chance"]:
            car["retired"] = True
            car["retired_lap"] = lap
            state["events"].append((lap, car["driver"]["abbr"] + " has retired from the race"))
    order = running_cars(state)

    # step 2: work out each car's lap time and pit stop
    for car in order:
        compound = car["strategy"]["compounds"][car["stint"]]
        car["lap_compound"] = compound
        car["lap_age"] = car["tyre_age"]
        car["held_up"] = False

        if under_sc:
            car["lap_t"] = state["ref_pace"] * SC_FACTOR
        else:
            car["lap_t"] = lap_time(car["pace"], compound, car["tyre_age"], laps_left, state["wear"])
            car["lap_t"] = car["lap_t"] + rng.gauss(0, NOISE)

        car["pit_cost"] = 0
        car["pitted"] = wants_to_pit(car, lap, under_sc, user_pits_under_sc, rng)
        if car["pitted"]:
            car["pit_cost"] = state["pit_loss"]
            if under_sc:
                car["pit_cost"] = state["pit_loss"] * SC_PIT_FACTOR

        car["new_total"] = car["total"] + car["lap_t"]

    # step 3: safety car bunches the field, otherwise traffic slows cars down
    if under_sc:
        bunch_up(order)
        for car in order:
            car["new_total"] = car["new_total"] + car["pit_cost"]
    else:
        for car in order:
            car["new_total"] = car["new_total"] + car["pit_cost"]
        apply_traffic(order)

    # step 4: save the results of the lap
    for car in order:
        car["total"] = car["new_total"]
        car["laps_done"] = lap
        if car["held_up"]:
            car["held_up_laps"] = car["held_up_laps"] + 1
        if not under_sc and not car["pitted"]:
            if car["best_lap"] is None or car["lap_t"] < car["best_lap"]:
                car["best_lap"] = car["lap_t"]

        if car["pitted"]:
            car["pits_done"] = car["pits_done"] + 1
            car["stint"] = car["stint"] + 1
            car["tyre_age"] = 0
        else:
            car["tyre_age"] = car["tyre_age"] + 1

    order.sort(key=get_total)
    for i in range(len(order)):
        order[i]["positions"].append(i + 1)

    # the safety car comes in after its laps are used up
    if under_sc:
        state["sc_laps_left"] = state["sc_laps_left"] - 1
        if state["sc_laps_left"] == 0:
            state["events"].append((lap, "Safety car in, racing restarts next lap"))

    # build the information that gets shown to the user
    info = {"lap": lap, "under_sc": under_sc, "events": [], "user": None}
    for event_lap, text in state["events"]:
        if event_lap == lap:
            info["events"].append(text)

    user = get_user_car(state)
    if user["retired"] and user["retired_lap"] == lap:
        info["user"] = {"retired": True}
    elif not user["retired"]:
        position = order.index(user) + 1
        notes = []
        if user["pitted"]:
            notes.append("PIT STOP")
        if under_sc:
            notes.append("SAFETY CAR")
        if user["held_up"]:
            notes.append("stuck in traffic")
        info["user"] = {
            "retired": False,
            "position": position,
            "compound": user["lap_compound"],
            "age": user["lap_age"],
            "lap_time": user["lap_t"] + user["pit_cost"],
            "gap_to_leader": user["total"] - order[0]["total"],
            "notes": notes,
        }
    return info


def run_whole_race(state):
    """Runs every lap without stopping (used for testing)."""
    while state["lap"] < state["laps"]:
        check_safety_car(state)
        run_lap(state)


def get_classification(state):
    """Final order: finishers by race time, then retirements by laps completed."""
    finishers = running_cars(state)
    retired = []
    for car in state["cars"]:
        if car["retired"]:
            retired.append(car)
    retired.sort(key=get_laps_done, reverse=True)
    return finishers + retired
