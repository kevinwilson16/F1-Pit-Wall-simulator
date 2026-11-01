# test_f1.py
# Run them with:   python test_f1.py

import os
import tempfile
import unittest

import data_loader
import report
import simulator
import strategy
import tyres


# a small made up race and field so the tests don't depend on the real data
TEST_RACE = {
    "id": "test", "year": 2024, "round": 1, "name": "Test Grand Prix",
    "laps": 30, "pit_loss": 22.0, "avg_stops": 1.2, "wear": 1.0,
}
TEST_STRATEGY = {"compounds": ["MEDIUM", "HARD"], "pit_laps": [15]}


def make_field(count, pace_gap):
    """Driver 0 is the fastest, and each driver after is pace_gap seconds slower."""
    field = []
    for i in range(count):
        driver = {
            "id": "driver" + str(i),
            "name": "Driver " + str(i),
            "abbr": "D" + str(i),
            "team": "Team",
            "grid": i + 1,
            "real_grid": str(i + 1),
            "real_finish": str(i + 1),
            "pace": 90.0 + i * pace_gap,
        }
        field.append(driver)
    return field


class TestTyres(unittest.TestCase):

    def test_soft_is_faster_than_hard_when_new(self):
        soft = tyres.lap_time(90, "SOFT", 0, 30)
        hard = tyres.lap_time(90, "HARD", 0, 30)
        self.assertLess(soft, hard)

    def test_older_tyre_is_slower(self):
        new = tyres.lap_time(90, "MEDIUM", 2, 30)
        old = tyres.lap_time(90, "MEDIUM", 12, 30)
        self.assertGreater(old, new)

    def test_tyre_cliff(self):
        # the lap time should jump faster after the tyre's life is used up
        life = tyres.COMPOUNDS["SOFT"]["life"]
        before = tyres.lap_time(90, "SOFT", life, 30)
        after = tyres.lap_time(90, "SOFT", life + 4, 30)
        normal_wear = 4 * tyres.COMPOUNDS["SOFT"]["wear"]
        self.assertGreater(after - before, normal_wear + 1.0)

    def test_more_fuel_is_slower(self):
        self.assertGreater(tyres.lap_time(90, "HARD", 5, 50), tyres.lap_time(90, "HARD", 5, 10))

    def test_harsh_track_is_slower(self):
        normal = tyres.lap_time(90, "MEDIUM", 10, 30, 1.0)
        harsh = tyres.lap_time(90, "MEDIUM", 10, 30, 1.5)
        self.assertGreater(harsh, normal)


class TestStrategy(unittest.TestCase):

    def test_valid_strategy(self):
        # should not raise anything
        strategy.validate_strategy(TEST_STRATEGY, 30)

    def test_one_compound_is_rejected(self):
        bad = {"compounds": ["HARD", "HARD"], "pit_laps": [15]}
        with self.assertRaises(ValueError):
            strategy.validate_strategy(bad, 30)

    def test_short_stint_is_rejected(self):
        bad = {"compounds": ["SOFT", "MEDIUM", "HARD"], "pit_laps": [10, 12]}
        with self.assertRaises(ValueError):
            strategy.validate_strategy(bad, 30)

    def test_last_stint_too_short(self):
        bad = {"compounds": ["SOFT", "HARD"], "pit_laps": [28]}
        with self.assertRaises(ValueError):
            strategy.validate_strategy(bad, 30)

    def test_wrong_number_of_compounds(self):
        bad = {"compounds": ["SOFT"], "pit_laps": [15]}
        with self.assertRaises(ValueError):
            strategy.validate_strategy(bad, 30)

    def test_unknown_compound(self):
        bad = {"compounds": ["SOFT", "WET"], "pit_laps": [15]}
        with self.assertRaises(ValueError):
            strategy.validate_strategy(bad, 30)

    def test_pit_lap_options_one_stop(self):
        plans = strategy.pit_lap_options(5, 20, 1, 5, 5)
        self.assertEqual(plans, [[5], [10], [15], [20]])

    def test_pit_lap_options_two_stops(self):
        plans = strategy.pit_lap_options(5, 20, 2, 5, 5)
        expected = [[5, 10], [5, 15], [5, 20], [10, 15], [10, 20], [15, 20]]
        self.assertEqual(plans, expected)

    def test_pit_lap_options_no_stops(self):
        self.assertEqual(strategy.pit_lap_options(5, 20, 0, 5, 5), [[]])

    def test_compound_options(self):
        self.assertEqual(strategy.compound_options(0), [[]])
        self.assertEqual(len(strategy.compound_options(1)), 3)
        self.assertEqual(len(strategy.compound_options(3)), 27)

    def test_pit_loss_is_counted(self):
        cheap = dict(TEST_RACE)
        cheap["pit_loss"] = 0.0
        slow = strategy.clean_air_race_time(90, TEST_STRATEGY, TEST_RACE)
        fast = strategy.clean_air_race_time(90, TEST_STRATEGY, cheap)
        self.assertAlmostEqual(slow - fast, 22.0)

    def test_find_best_strategies(self):
        best = strategy.find_best_strategies(90, TEST_RACE, how_many=3)
        self.assertEqual(len(best), 3)
        self.assertLessEqual(best[0][0], best[1][0])
        self.assertLessEqual(best[1][0], best[2][0])
        for time, plan in best:
            strategy.validate_strategy(plan, 30)

    def test_ai_strategies_are_always_legal(self):
        import random
        for seed in range(200):
            rng = random.Random(seed)
            plan = strategy.make_ai_strategy(TEST_RACE, rng)
            strategy.validate_strategy(plan, TEST_RACE["laps"])


class TestSimulator(unittest.TestCase):

    def test_same_seed_gives_same_result(self):
        results = []
        for attempt in range(2):
            state = simulator.new_race(TEST_RACE, make_field(8, 0.3), "driver3",
                                       TEST_STRATEGY, 3, seed=5)
            simulator.run_whole_race(state)
            order = []
            for car in simulator.get_classification(state):
                order.append(car["driver"]["id"])
            results.append(order)
        self.assertEqual(results[0], results[1])

    def test_fastest_car_wins_without_events(self):
        # the fastest car starts last but is 3 seconds a lap quicker
        field = make_field(5, 3.0)
        state = simulator.new_race(TEST_RACE, field, "driver0", TEST_STRATEGY, 5,
                                   seed=1, sc_chance=0, dnf_chance=0)
        simulator.run_whole_race(state)
        winner = simulator.get_classification(state)[0]
        self.assertEqual(winner["driver"]["id"], "driver0")

    def test_user_can_choose_grid_position(self):
        state = simulator.new_race(TEST_RACE, make_field(6, 0.5), "driver0", TEST_STRATEGY, 4, seed=1)
        user = simulator.get_user_car(state)
        self.assertEqual(user["grid"], 4)
        # the driver who was on P4 moves to the user's old slot (P1)
        first_car = state["cars"][0]
        self.assertEqual(first_car["driver"]["id"], "driver3")

    def test_every_finisher_has_a_position_for_every_lap(self):
        state = simulator.new_race(TEST_RACE, make_field(6, 0.5), "driver2", TEST_STRATEGY, 3,
                                   seed=2, sc_chance=0, dnf_chance=0)
        simulator.run_whole_race(state)
        for car in state["cars"]:
            self.assertEqual(len(car["positions"]), TEST_RACE["laps"])

    def test_user_makes_the_planned_pit_stop(self):
        state = simulator.new_race(TEST_RACE, make_field(6, 0.5), "driver2", TEST_STRATEGY, 3,
                                   seed=2, sc_chance=0, dnf_chance=0)
        simulator.run_whole_race(state)
        self.assertEqual(simulator.get_user_car(state)["pits_done"], 1)

    def test_retirements(self):
        state = simulator.new_race(TEST_RACE, make_field(4, 0.5), "driver1", TEST_STRATEGY, 2,
                                   seed=3, sc_chance=0, dnf_chance=1.0)
        simulator.run_whole_race(state)
        for car in simulator.get_classification(state):
            self.assertTrue(car["retired"])

    def test_safety_car_starts_and_ends(self):
        state = simulator.new_race(TEST_RACE, make_field(6, 0.5), "driver1", TEST_STRATEGY, 2,
                                   seed=4, sc_chance=1.0, dnf_chance=0)
        simulator.run_whole_race(state)
        texts = []
        for lap, text in state["events"]:
            texts.append(text)
        self.assertIn("Safety car deployed", texts)
        self.assertGreater(state["sc_lap_count"], 0)

    def test_bunch_up(self):
        cars = []
        for total in [0.0, 5.0, 12.0, 12.5]:
            cars.append({"new_total": total})
        simulator.bunch_up(cars)
        self.assertEqual([c["new_total"] for c in cars], [0.0, 1.0, 2.0, 2.5])

    def test_traffic_holds_up_a_similar_pace_car(self):
        front = {"new_total": 100.0, "lap_t": 90.0, "pit_cost": 0}
        back = {"new_total": 99.9, "lap_t": 89.9, "pit_cost": 0}
        simulator.apply_traffic([front, back])
        self.assertGreaterEqual(back["new_total"], 100.0 + simulator.MIN_GAP)
        self.assertTrue(back["held_up"])

    def test_much_faster_car_can_pass(self):
        front = {"new_total": 100.0, "lap_t": 91.0, "pit_cost": 0}
        back = {"new_total": 99.9, "lap_t": 89.0, "pit_cost": 0}
        simulator.apply_traffic([front, back])
        self.assertEqual(back["new_total"], 99.9)


class TestReport(unittest.TestCase):

    def test_format_lap_time(self):
        self.assertEqual(report.format_lap_time(92.608), "1:32.608")
        self.assertEqual(report.format_lap_time(59.5), "0:59.500")

    def test_format_race_time(self):
        self.assertEqual(report.format_race_time(5504.742), "1:31:44.742")

    def test_format_gap(self):
        self.assertEqual(report.format_gap(2.6), "+2.600")

    def test_place_text(self):
        self.assertEqual(report.place_text("3"), "P3")
        self.assertEqual(report.place_text("DNF"), "DNF")

    def test_strategy_text(self):
        text = report.strategy_text(TEST_STRATEGY)
        self.assertEqual(text, "MEDIUM > HARD (pit on lap 15)")
        self.assertEqual(report.short_strategy(TEST_STRATEGY), "M>H")

    def test_history_file(self):
        fake_car = {
            "driver": {"name": "Test Driver"},
            "grid": 3,
            "pits_done": 1,
            "strategy": TEST_STRATEGY,
        }
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "history.csv")
            report.add_to_history(TEST_RACE, fake_car, "2", path)
            report.add_to_history(TEST_RACE, fake_car, "DNF", path)
            rows = report.load_history(path)

        self.assertEqual(len(rows), 3)                  # header and two races
        self.assertEqual(rows[0], report.HISTORY_HEADER)
        self.assertEqual(rows[1][5], "2")
        self.assertEqual(rows[2][5], "DNF")

    def test_missing_history_file(self):
        with self.assertRaises(FileNotFoundError):
            report.load_history("this_file_does_not_exist.csv")

    def test_summary_has_the_main_sections(self):
        state = simulator.new_race(TEST_RACE, make_field(6, 0.5), "driver2", TEST_STRATEGY, 3,
                                   seed=2, sc_chance=0, dnf_chance=0)
        simulator.run_whole_race(state)
        user = simulator.get_user_car(state)
        text = "\n".join(report.build_summary(TEST_RACE, user, state))
        self.assertIn("RACE SUMMARY", text)
        self.assertIn("Final classification", text)
        self.assertIn("<-- you", text)
        self.assertIn("Strategy check", text)


class TestDataLoader(unittest.TestCase):

    def test_pit_loss_ignores_red_flag_stops(self):
        times = [2369.0, 2400.0, 22.0, 23.0, 24.0, 25.0, 26.0]
        self.assertEqual(data_loader.get_pit_loss(times), 24.0)

    def test_pit_loss_default_when_not_enough_data(self):
        self.assertEqual(data_loader.get_pit_loss([22.0, 23.0]), data_loader.DEFAULT_PIT_LOSS)

    def test_pretty_name(self):
        self.assertEqual(data_loader.pretty_name("red-bull"), "Red Bull")
        self.assertEqual(data_loader.pretty_name("mclaren"), "McLaren")

    def test_missing_file_gives_clear_error(self):
        with self.assertRaises(FileNotFoundError):
            data_loader.read_csv("not-a-real-file.csv")

    def test_real_data(self):
        try:
            data = data_loader.load_data()
        except FileNotFoundError:
            self.skipTest("data folder not found")

        races = data_loader.get_races(data)
        self.assertGreater(len(races), 100)
        for race in races:
            self.assertGreaterEqual(race["year"], data_loader.FIRST_YEAR)

        # check one full race: grid numbers go 1..n and every driver has a pace
        field = data_loader.get_field(data, races[0])
        grids = []
        for driver in field:
            grids.append(driver["grid"])
            self.assertIsInstance(driver["pace"], float)
        self.assertEqual(sorted(grids), list(range(1, len(field) + 1)))


if __name__ == "__main__":
    unittest.main()
