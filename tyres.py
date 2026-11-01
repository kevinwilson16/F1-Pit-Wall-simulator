# tyres.py
# A simple tyre model used by the race simulator and the strategy finder.

# offset = seconds per lap compared with a medium tyre (negative is faster)
# wear   = extra seconds lost for every lap the tyre has been used
# life   = laps before the tyre drops off a cliff and gets much slower
COMPOUNDS = {
    "SOFT": {"offset": -0.5, "wear": 0.14, "life": 14},
    "MEDIUM": {"offset": 0.0, "wear": 0.075, "life": 26},
    "HARD": {"offset": 0.5, "wear": 0.045, "life": 38},
}

FUEL_PER_LAP = 0.03    # seconds the car gets quicker each lap as fuel burns off
CLIFF_PENALTY = 0.35   # extra seconds per lap once a tyre is past its life


def lap_time(base_pace, compound, tyre_age, laps_left, wear_factor=1.0):
    """Lap time in seconds for a car on a given tyre in clean air.

    wear_factor is higher at tracks that are hard on tyres.
    """
    tyre = COMPOUNDS[compound]
    time = base_pace + tyre["offset"] + tyre["wear"] * wear_factor * tyre_age

    # tyre is past its life so it loses time quickly
    life = tyre["life"] / wear_factor
    if tyre_age > life:
        time = time + CLIFF_PENALTY * (tyre_age - life)

    # more fuel on board means a slower car
    time = time + FUEL_PER_LAP * laps_left
    return time
