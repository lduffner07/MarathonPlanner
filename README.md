# Marathon Planner

A local web interface around the original marathon training functions, with manual run feedback and sleep tracking.

Requires Python 3.10 or newer; no extra packages.

From the project folder, choose either interface:

```sh
./marathon terminal       # Original terminal planner
./marathon web            # Web interface; opens your browser
./marathon                # Interactive mode picker
./marathon web --no-open  # Server only, for environments without a browser
```

Optional: add the project folder to your shell's PATH to use `marathon` from any directory:

```sh
export PATH="/path/to/MarathonPlanner:$PATH"
```

Replace the path with your checkout location. Add that export to your shell configuration if you want it to persist. No installation or extra packages are required. Use `./marathon --help` for options, and `./marathon web --port 8001` if port 8000 is busy. Ctrl+C stops either interface.

Direct startup with `python3 web_app.py` still works.

Open the app on port 8000 in your local browser. Save your plan settings, expand weeks to see daily workouts, and record daily mileage, duration, effort, sleep and recovery notes. Choose a Monday as your plan start date. Saving a journal entry on an existing date replaces that entry. Plans and journals persist in `.local/training.sqlite3`; back up this file to preserve your data. `MARATHON_DB` can point to another database path; `PORT` changes the listening port.

The server binds to loopback and has no user authentication: this version is for personal use on your machine, not public hosting. Garmin integration is not implemented. Logs do not automatically change the generated training schedule. The original CLI and its check-in adjustments are still available with `python3 marathon_planner.py`.

The original `marathon_planner.py` functions remain unchanged. This interface calls them for weekly mileage, daily allocation, workout descriptions and pace calculations. Web journal storage is separate from the original CLI's session-only check-ins.

Run integration checks:

```sh
python3 -m unittest discover -s tests -v
```

Additional features:

- Weekly completion bars compare logged mileage with the original plan. Unlogged days remain unknown rather than being marked missed.
- Calendar days and journal entries link to a prefilled edit form.
- Each run shows its actual average pace when distance and duration are available.
- The last-seven-days summary shows mileage, sleep and effort trends, using only recorded entries and excluding rest days from run-effort averages.
- Download journal CSV for spreadsheets, or a full JSON backup containing plan settings and journal entries. JSON import is not implemented; retain the SQLite file for direct restoration.
- A training-phase summary and pace reference support day-to-day planning. Race week is shown without inventing an exact race date.
