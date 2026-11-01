F1 PIT WALL STRATEGY SIMULATOR
==============================

A terminal program where you act as the strategist for an F1 driver. You pick a
real race from 2018 onwards, a driver, a starting grid position, and a tyre
strategy. The program then simulates the race lap by lap, with tyre wear, pit
stops, traffic, random safety cars and random retirements. At the end it shows
how your strategy did compared with the rest of the field.


HOW TO RUN
----------
1. You need Python 3.8 or newer. No libraries need to be installed.
2. Open a terminal in this folder (the one that contains main.py).
3. Run:

       python main.py

   (On Mac/Linux you may need to type  python3 main.py  instead.)

The program loads the data from the "data" folder, so keep that folder next to
main.py. It does not need an internet connection.

To run the tests:

       python test_f1.py


USING THE PROGRAM
-----------------
Main menu:
  1. Simulate a race with my own strategy
  2. Simulate a race with strategy suggestions (the program searches lots of
     strategies and shows the five fastest, then you can pick one)
  3. View my past results (reads results/history.csv)
  4. Quit

When you set up a race you choose:
  - Season and race
  - Your driver (the field comes from the real race)
  - Starting grid position (press Enter to keep the real one; if you pick a
    different slot you swap places with the driver who was there)
  - Strategy: number of stops, starting tyre, the lap you pit on, and the tyre
    you fit at each stop (S = soft, M = medium, H = hard)
  - An optional random seed (use the same number to replay the same race)
  - How often you want a lap update (pit stops and events always show)

Rules for a strategy (the program checks these and asks again if you break them):
  - Use at least two different tyre compounds
  - Every stint must be at least 5 laps long

During the race:
  - If a safety car comes out, you are asked if you want to pit. A stop under
    the safety car costs much less time, but it uses up your next planned stop.
  - Computer drivers each get their own strategy. The number of stops they
    make follows what drivers really did at that race.

At the end you get a summary (finishing order, your result, how 1-stop and
2-stop cars did, and how your plan compares with the best plan the program can
find). You can also save the summary to a text file in the "results" folder.


HOW THE SIMULATION WORKS (simplified)
-------------------------------------
- Driver pace: taken from each driver's fastest lap in the real race, after
  taking out the effect of the fuel load. The gaps between drivers are shrunk
  a bit because one fastest lap makes the gaps look bigger than they really
  were. The constants were tuned by comparing the simulation with the real
  race times in the data.
- Tyres: each compound has a speed offset, a wear rate per lap, and a "life".
  After its life a tyre falls off a cliff and loses time quickly. Tracks where
  drivers made more stops in the real race wear tyres faster.
- Fuel: the car gets a little faster every lap.
- Pit stops: the time lost is the median real pit lane time for that race.
- Traffic: a car cannot drive through the car in front. It is held up unless
  it is much faster, so the starting position matters.
- Safety car: a random chance each lap. The field bunches up behind it, lap
  times are slow, and pit stops cost less.
- Retirements: a small random chance for every car on every lap.
- The race itself is a loop that runs one lap at a time.


FILES
-----
  main.py          menu, user input and the race loop
  data_loader.py   reads the csv data and builds the races and drivers
  tyres.py         tyre and lap time model
  strategy.py      strategy checking, computer strategies, strategy search
  simulator.py     the lap by lap race simulation
  report.py        time formatting, race summary, saving results and history
  test_f1.py       unit tests
  data/            the F1DB csv files used (see below)
  results/         created by the program (history.csv and saved summaries)


DATA
----
The data comes from F1DB (https://github.com/f1db/f1db), an open source
Formula 1 database licensed under Creative Commons Attribution 4.0.

  f1db-races.csv
  f1db-races-race-results.csv
  f1db-races-fastest-laps.csv
  f1db-races-pit-stops.csv
  f1db-drivers.csv
