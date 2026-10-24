import math


PACE_OFFSETS = {
    "Marathon": 0,
    "Recovery": (1.85, 2.15),
    "Easy": (1.5, 1.75),
    "Long Run": (1, 1.3),
    "Tempo": (-.35, -.3),
    "Interval": (-1.05, -.95)
}

WORKOUT_BANK = {
    "Easy": [
        "{miles} miles easy at a conversational effort",
        "{miles} miles easy, finishing with 4 x 20-second strides",
        "{miles} relaxed easy miles"
    ],
    "Tempo": {
        "short": [
            "2 x 4 minutes at tempo pace with 2-minute easy jogs",
            "8 minutes continuous at tempo pace",
            "4 x 2 minutes at tempo pace with 1-minute easy jogs"
        ],
        "medium": [
            "3 x 5 minutes at tempo pace with 2-minute easy jogs",
            "2 x 8 minutes at tempo pace with 3-minute easy jogs",
            "15 minutes continuous at tempo pace"
        ],
        "long": [
            "3 x 8 minutes at tempo pace with 2-minute easy jogs",
            "20 minutes continuous at tempo pace",
            "2 x 12 minutes at tempo pace with 3-minute easy jogs"
        ]
    },
    "Interval": {
        "short": [
            "4 x 200m at interval pace with 200m easy jogs",
            "6 x 1 minute at interval pace with 90-second easy jogs",
            "6 x 200m at interval pace with 200m easy jogs"
        ],
        "medium": [
            "6 x 400m at interval pace with 200m easy jogs",
            "4 x 600m at interval pace with 300m easy jogs",
            "8 x 400m at interval pace with 200m easy jogs"
        ],
        "long": [
            "5 x 800m at interval pace with 400m easy jogs",
            "4 x 1km at interval pace with 2-minute easy jogs",
            "6 x 800m at interval pace with 400m easy jogs"
        ]
    },
    "Long Run": [
        "{miles} miles at long-run pace",
        "{miles} miles at an even, conversational effort",
        "{miles} relaxed miles; keep the effort easy throughout"
    ]
}

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def format_pace(pace):
    minutes = math.floor(pace)
    seconds = round((pace - minutes) * 60)
    if seconds == 60:
        minutes += 1
        seconds = 0
    return f"{minutes}:{seconds:02d}"


def workout_pace(workout, marathon_pace):
    offset = PACE_OFFSETS[workout]
    if isinstance(offset, tuple):
        fast_pace = marathon_pace + offset[0]
        slow_pace = marathon_pace + offset[1]
        return f"{format_pace(fast_pace)} - {format_pace(slow_pace)} / mile"
    return f"{format_pace(marathon_pace + offset)} / mile"


def workout_details(workout, week_info, daily_miles, marathon_pace):
    if workout in ("Tempo", "Interval"):
        if daily_miles < 3:
            return f"{daily_miles:g} miles easy; too short for a quality session"
        warmup_cooldown_miles = 1 if daily_miles >= 5 else .5
        workout_miles = min(3, daily_miles - 2 * warmup_cooldown_miles)
        if workout_miles <= 1:
            level = "short"
        elif workout_miles <= 2:
            level = "medium"
        else:
            level = "long"
        options = WORKOUT_BANK[workout][level]
        prescription = options[(week_info["week"] - 1) % len(options)]
        easy_miles = daily_miles - workout_miles - 2 * warmup_cooldown_miles
        warmup_miles = warmup_cooldown_miles + easy_miles / 2
        cooldown_miles = warmup_cooldown_miles + easy_miles / 2
        details = (
            f"{warmup_miles:g}-mile easy warm-up, "
            f"{workout_miles:g} miles of {workout.lower()} work ({prescription}), "
            f"{cooldown_miles:g}-mile easy cool-down"
        )
        return f"{details}; {daily_miles:g} miles total ({workout_pace(workout, marathon_pace)})"

    options = WORKOUT_BANK[workout]
    details = options[(week_info["week"] - 1) % len(options)]
    details = details.format(miles=daily_miles)
    return f"{details} ({workout_pace(workout, marathon_pace)})"


def calculate_weekly_plan(mileage, peak_mileage, weeks):
    plan = []
    current = mileage
    highest = mileage
    max_long_run = 22
    starting_long_run = min(round(current * .30), max_long_run)
    peak_long_run = max(starting_long_run, min(round(peak_mileage * .40), max_long_run))
    long_run = starting_long_run
    peak_week = weeks - 3
    # Only build weeks advance the mileage baseline. Recovery weeks reduce
    # volume without making later weeks restart from the reduced baseline.
    build_weeks = [week for week in range(2, peak_week + 1)
                   if week % 4 != 0 or week == peak_week]
    build_step = 0

    for week in range(1, weeks + 1):
        if week == weeks - 3:
            current = peak_mileage
            label = "Peak Week"
        elif week == weeks - 2:
            current = math.floor(peak_mileage * .70)
            label = "Taper Week 1"
            long_run = round(peak_long_run * .50)
        elif week == weeks - 1:
            current = math.floor(peak_mileage * .45)
            label = "Taper Week 2"
            long_run = round(current * .18)
        elif week == weeks:
            current = math.floor(peak_mileage * .25)
            label = "Race Week"
            long_run = None
        elif week == 1:
            current = mileage
            label = "Starting Mileage"
        else:
            label = "Build Week"
            if week % 4 == 0:
                label = "Down Week"
                current = math.floor(highest * .9)
            else:
                build_step += 1
                target = round(mileage + (peak_mileage - mileage)
                               * build_step / len(build_weeks))
                # Retain the original growth guard, measured from the last
                # build high so the down week does not erase build progress.
                increase_limit = highest + max(1, math.floor(highest * .1))
                current = min(target, increase_limit, peak_mileage)
            highest = max(highest, current)

        if week <= peak_week:
            if week == peak_week:
                long_run = peak_long_run
            elif week == 1:
                long_run = starting_long_run
            elif label == "Down Week":
                long_run = max(starting_long_run, long_run - 1)
            elif peak_week > 1:
                weeks_to_peak = peak_week - week + 1
                miles_to_peak = peak_long_run - long_run
                increase = min(2, max(1, round(miles_to_peak / weeks_to_peak)))
                long_run += min(increase, miles_to_peak)

        if long_run is not None:
            long_run = min(long_run, current)

        plan.append({
            "week": week,
            "label": label,
            "mileage": current,
            "long_run": long_run
        })
    return plan


def allocate_daily_mileage(week_info, days, off_day, long_run_day):
    daily_mileage = {day: 0 for day in days}
    running_days = [day for day in days if day != off_day]
    long_run_miles = week_info["long_run"]
    if isinstance(long_run_miles, int):
        daily_mileage[long_run_day] = long_run_miles
        running_days.remove(long_run_day)

    miles_left = week_info["mileage"] - sum(daily_mileage.values())
    base_mileage, extra_miles = divmod(miles_left, len(running_days))
    for index, day in enumerate(running_days):
        daily_mileage[day] = base_mileage + (index < extra_miles)
    return daily_mileage


def read_integer(prompt, minimum=None, maximum=None):
    while True:
        try:
            value = int(input(prompt))
        except ValueError:
            print("Please enter a whole number.")
            continue
        if minimum is not None and value < minimum:
            print(f"Enter a number no smaller than {minimum}.")
            continue
        if maximum is not None and value > maximum:
            print(f"Enter a number no larger than {maximum}.")
            continue
        return value


def build_current_plan(mileage, peak_mileage, weeks, weekly_overrides):
    plan = calculate_weekly_plan(mileage, peak_mileage, weeks)
    for week_number, target_mileage in weekly_overrides.items():
        plan[week_number - 1]["mileage"] = target_mileage
    return plan


def show_pace_chart(marathon_pace):
    print("\n" + "=" * 40)
    print("Pace Chart")
    print("=" * 40)
    for workout in PACE_OFFSETS:
        print(f"{workout}: {workout_pace(workout, marathon_pace)}")


def show_weekly_plan(plan, weeks):
    for week_info in plan:
        print(f"\nWeek {week_info['week']}: {week_info['label']}")
        print(f"Target mileage: {week_info['mileage']} miles")
        if week_info["long_run"] is None:
            print("Suggested Long Run: No long run this week!")
        else:
            print(f"Suggested Long Run: {week_info['long_run']} miles")


def show_daily_plan(plan, weeks, marathon_pace):
    week_number = read_integer(f"What week of training are you on (1-{weeks})? ", 1, weeks)
    off_day = input("What day is your rest day? ").strip().capitalize()
    long_run_day = input("What day would you like to do your long run? ").strip().capitalize()
    while off_day not in DAYS:
        off_day = input("Enter a weekday for your rest day: ").strip().capitalize()
    while long_run_day not in DAYS or long_run_day == off_day:
        long_run_day = input("Choose a valid long-run day different from your rest day: ").strip().capitalize()

    week_info = plan[week_number - 1]
    print(f"\nWeek {week_info['week']}: {week_info['label']}")
    print(f"Target mileage: {week_info['mileage']} miles")
    long_run_scheduled = week_info["long_run"] is not None
    if long_run_scheduled:
        print(f"Suggested Long Run: {week_info['long_run']} miles")
    else:
        print("Suggested Long Run: No long run this week!")

    daily_mileage = allocate_daily_mileage(week_info, DAYS, off_day, long_run_day)
    labels = {"Easy": "Easy Run", "Tempo": "Tempo Run", "Interval": "Interval Run", "Long Run": "Long Run"}
    for day in DAYS:
        if day == off_day:
            print(f"{day}: Rest Day (0 miles)")
            continue
        if day == long_run_day and long_run_scheduled:
            workout = "Long Run"
        elif day == "Tuesday" and week_info["label"] != "Race Week" and daily_mileage[day] >= 3:
            workout = "Tempo"
        elif day == "Thursday" and week_info["label"] != "Race Week" and daily_mileage[day] >= 3:
            workout = "Interval"
        else:
            workout = "Easy"
        print(
            f"{day}: {labels[workout]} - "
            f"{workout_details(workout, week_info, daily_mileage[day], marathon_pace)}"
        )


def record_training_checkin(plan, weeks, peak_mileage, weekly_overrides, checkins):
    completed_week = read_integer(f"Which week did you complete (1-{weeks})? ", 1, weeks)
    actual_mileage = read_integer("How many miles did you complete? ", 0)
    print("How did the week feel?\n1. Manageable\n2. Too difficult\n3. Easier than expected")
    effort_choice = read_integer("Select 1, 2, or 3: ", 1, 3)
    effort = {1: "manageable", 2: "too difficult", 3: "easier than expected"}[effort_choice]
    completed_info = plan[completed_week - 1]
    checkins.append({
        "week": completed_week,
        "planned_mileage": completed_info["mileage"],
        "actual_mileage": actual_mileage,
        "effort": effort
    })
    print(
        f"Logged week {completed_week}: {actual_mileage} of "
        f"{completed_info['mileage']} planned miles; felt {effort}."
    )
    if completed_week == weeks:
        print("There is no following training week to adjust.")
        return

    next_week = plan[completed_week]
    current_target = next_week["mileage"]
    next_long_run = next_week["long_run"]
    minimum_target = next_long_run if isinstance(next_long_run, int) else 0
    if effort == "too difficult":
        suggested_target = max(
            minimum_target,
            min(current_target, math.floor(current_target * .90), math.ceil(actual_mileage * 1.1))
        )
    elif effort == "easier than expected" and next_week["label"] == "Build Week":
        suggested_target = min(peak_mileage, current_target + max(1, math.ceil(current_target * .05)))
    else:
        suggested_target = current_target

    print(
        f"Week {completed_week + 1} is currently planned for {current_target} miles. "
        f"Suggested target: {suggested_target} miles."
    )
    choice = input("Apply suggestion, edit target, or keep plan? [A/E/K]: ").strip().upper()
    if choice == "A":
        weekly_overrides[completed_week + 1] = suggested_target
        print("Next week's target updated for this session.")
    elif choice == "E":
        edited_target = read_integer("Enter the new weekly target: ", minimum_target, peak_mileage)
        weekly_overrides[completed_week + 1] = edited_target
        print("Next week's target updated for this session.")
    else:
        print("Plan unchanged.")


def show_checkin_history(checkins):
    print("\nTraining Check-In History")
    if not checkins:
        print("No check-ins recorded this session.")
        return
    for checkin in checkins:
        print(
            f"Week {checkin['week']}: {checkin['actual_mileage']} of "
            f"{checkin['planned_mileage']} miles; felt {checkin['effort']}"
        )


def main():
    print("=" * 40)
    print("Welcome to Lindsey's Marathon Planner!")
    print("=" * 40)
    name = input("Please enter your name: ").strip()
    mileage = read_integer("Current weekly mileage: ", 1)
    peak_mileage = read_integer("Goal peak mileage? ", mileage)
    weeks = read_integer("How many weeks until the race? ", 4)
    print("Enter goal time.")
    goal_hours = read_integer("Hours: ", 0)
    goal_minutes = read_integer("Minutes: ", 0, 59)
    goal_minutes_total = goal_hours * 60 + goal_minutes
    while goal_minutes_total <= 0:
        print("Goal time must be greater than zero.")
        goal_hours = read_integer("Hours: ", 0)
        goal_minutes = read_integer("Minutes: ", 0, 59)
        goal_minutes_total = goal_hours * 60 + goal_minutes

    marathon_pace = goal_minutes_total / 26.2
    weekly_overrides = {}
    checkins = []
    print(f"\nRunner: {name}")
    print(f"Starting weekly mileage: {mileage}")

    while True:
        print("\nMenu\n1. Pace Chart\n2. Weekly Mileage Plan")
        print("3. Create This Week's Training Plan\n4. Training Check-In")
        print("5. View Check-In History\n0. Quit")
        option = read_integer("Select an option: ", 0, 5)
        if option == 0:
            print("Training session ended.")
            break

        plan = build_current_plan(mileage, peak_mileage, weeks, weekly_overrides)
        if option == 1:
            show_pace_chart(marathon_pace)
        elif option == 2:
            show_weekly_plan(plan, weeks)
        elif option == 3:
            show_daily_plan(plan, weeks, marathon_pace)
        elif option == 4:
            record_training_checkin(plan, weeks, peak_mileage, weekly_overrides, checkins)
        else:
            show_checkin_history(checkins)


if __name__ == "__main__":
    main()