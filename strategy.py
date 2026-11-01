# strategy.py
# Everything to do with tyre strategies and searching for the best one.
# A strategy is a dictionary like this:
#   {"compounds": ["MEDIUM", "HARD"], "pit_laps": [22]}
# which means start on mediums, pit at the end of lap 22, then run hards.

from tyres import COMPOUNDS, lap_time

MIN_STINT = 5   # shortest allowed stint in laps


def validate_strategy(strategy, total_laps):
    """Raises a ValueError if the strategy breaks the rules."""
    compounds = strategy["compounds"]
    pit_laps = strategy["pit_laps"]

    if len(compounds) != len(pit_laps) + 1:
        raise ValueError("Every stint needs a tyre compound.")

    for compound in compounds:
        if compound not in COMPOUNDS:
            raise ValueError(compound + " is not a valid tyre.")

    # real F1 rule: two different dry compounds must be used
    if len(set(compounds)) < 2:
        raise ValueError("You must use at least two different tyre compounds.")

    previous = 0
    for lap in pit_laps:
        if lap - previous < MIN_STINT:
            raise ValueError("Each stint must be at least " + str(MIN_STINT) + " laps.")
        previous = lap

    if total_laps - previous < MIN_STINT:
        raise ValueError("Your last stint is too short. Pit earlier.")


def make_ai_strategy(race, rng):
    """Makes a random but sensible strategy for a computer driver."""
    total_laps = race["laps"]

    # use the number of stops drivers really made at this race (a decimal like 1.7)
    stops = int(race["avg_stops"])
    if rng.random() < race["avg_stops"] - stops:
        stops = stops + 1
    stops = max(1, min(stops, 3))

    stint_length = total_laps / (stops + 1)

    pit_laps = []
    for number in range(1, stops + 1):
        lap = round(stint_length * number) + rng.randint(-3, 3)
        pit_laps.append(lap)

    # the random change must not make a stint too short
    previous = 0
    for i in range(len(pit_laps)):
        earliest = previous + MIN_STINT
        latest = total_laps - MIN_STINT * (len(pit_laps) - i)
        pit_laps[i] = max(earliest, min(pit_laps[i], latest))
        previous = pit_laps[i]

    # only use tyres that can last close to a full stint
    usable = []
    for name in COMPOUNDS:
        if COMPOUNDS[name]["life"] / race["wear"] >= stint_length * 0.8:
            usable.append(name)

    # on very harsh tracks nothing lasts long, so just use the hard tyre
    if len(usable) == 0:
        usable = ["HARD"]

    compounds = []
    for stint in range(stops + 1):
        compounds.append(rng.choice(usable))

    # make sure two different compounds are used
    if len(set(compounds)) < 2:
        others = []
        for name in COMPOUNDS:
            if name != compounds[0]:
                others.append(name)
        compounds[-1] = rng.choice(others)

    return {"compounds": compounds, "pit_laps": pit_laps}


def pit_lap_options(earliest, latest, stops_left, step, min_stint):
    """Returns every possible list of pit laps (uses recursion).

    earliest   - first lap the next stop is allowed on
    latest     - last lap any stop is allowed on
    stops_left - how many stops still have to be placed
    """
    # base case: nothing left to place, so there is one empty plan
    if stops_left == 0:
        return [[]]

    plans = []
    for lap in range(earliest, latest + 1, step):
        # place the remaining stops after this one
        later_plans = pit_lap_options(lap + min_stint, latest, stops_left - 1, step, min_stint)
        for rest in later_plans:
            plans.append([lap] + rest)
    return plans


def compound_options(stints):
    """Returns every possible list of tyre compounds for a number of stints (uses recursion)."""
    if stints == 0:
        return [[]]

    options = []
    for compound in COMPOUNDS:
        for rest in compound_options(stints - 1):
            options.append([compound] + rest)
    return options


def clean_air_race_time(base_pace, strategy, race):
    """Total race time in seconds if the car had a clear track the whole way."""
    total_laps = race["laps"]
    total = 0.0
    laps_done = 0
    pit_laps = strategy["pit_laps"]

    for stint in range(len(strategy["compounds"])):
        compound = strategy["compounds"][stint]
        if stint < len(pit_laps):
            end_lap = pit_laps[stint]
        else:
            end_lap = total_laps

        tyre_age = 0
        while laps_done < end_lap:
            total = total + lap_time(base_pace, compound, tyre_age, total_laps - laps_done, race["wear"])
            laps_done = laps_done + 1
            tyre_age = tyre_age + 1

        if stint < len(pit_laps):
            total = total + race["pit_loss"]

    return total


def get_time(candidate):
    return candidate[0]


def find_best_strategies(base_pace, race, how_many=5, max_stops=3, step=4):
    """Tries lots of strategies and returns the fastest ones as (time, strategy) pairs."""
    total_laps = race["laps"]
    candidates = []

    for stops in range(1, max_stops + 1):
        all_pit_laps = pit_lap_options(MIN_STINT, total_laps - MIN_STINT, stops, step, MIN_STINT)
        all_compounds = compound_options(stops + 1)

        for pit_laps in all_pit_laps:
            for compounds in all_compounds:
                if len(set(compounds)) < 2:
                    continue
                strategy = {"compounds": compounds, "pit_laps": pit_laps}
                time = clean_air_race_time(base_pace, strategy, race)
                candidates.append((time, strategy))

    candidates.sort(key=get_time)
    return candidates[:how_many]
