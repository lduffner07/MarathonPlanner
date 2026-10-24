"""Calendar and review helpers that reuse the planner's workout functions."""
import datetime as dt
import marathon_planner as planner


def schedule(profile):
    start = dt.date.fromisoformat(profile['start_date'])
    pace = profile['goal_minutes'] / 26.2
    result = []
    for week in planner.calculate_weekly_plan(profile['mileage'], profile['peak_mileage'], profile['weeks']):
        daily = planner.allocate_daily_mileage(week, planner.DAYS, profile['off_day'], profile['long_run_day'])
        for index, day in enumerate(planner.DAYS):
            date = start + dt.timedelta(weeks=week['week']-1, days=index)
            if day == profile['off_day']:
                workout, description = 'Rest', 'Rest day'
            else:
                workout = 'Long Run' if day == profile['long_run_day'] and week['long_run'] is not None else 'Tempo' if day == 'Tuesday' and week['label'] != 'Race Week' and daily[day] >= 3 else 'Interval' if day == 'Thursday' and week['label'] != 'Race Week' and daily[day] >= 3 else 'Easy'
                description = planner.workout_details(workout, week, daily[day], pace)
            result.append(dict(date=date, week=week['week'], miles=daily[day], workout=workout, description=description))
    return result


def review(days, logs):
    """Compare only recorded dates; absent entries are not zero-mile runs."""
    recorded = [day for day in days if day['date'].isoformat() in logs]
    entries = [logs[day['date'].isoformat()] for day in recorded]
    runs = [entry for entry in entries if entry['miles'] > 0]
    return dict(days=len(entries), planned=sum(day['miles'] for day in recorded),
                actual=sum(entry['miles'] for entry in entries),
                sleep=sum(entry['sleep'] for entry in entries)/len(entries) if entries else None,
                effort=sum(entry['effort'] for entry in runs)/len(runs) if runs else None)


def ics_escape(text):
    return str(text).replace('\\', '\\\\').replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')


def calendar(profile):
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Stride//Marathon Planner//EN', 'CALSCALE:GREGORIAN']
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    for day in schedule(profile):
        date = day['date']
        lines += ['BEGIN:VEVENT', f'UID:stride-{date:%Y%m%d}@marathon-planner.local',
                  f'DTSTAMP:{stamp}', f'DTSTART;VALUE=DATE:{date:%Y%m%d}',
                  f'DTEND;VALUE=DATE:{date+dt.timedelta(days=1):%Y%m%d}',
                  'SUMMARY:'+ics_escape(f"Week {day['week']} · {day['workout']} · {day['miles']:g} mi"),
                  'DESCRIPTION:'+ics_escape(day['description']), 'END:VEVENT']
    lines.append('END:VCALENDAR')
    # Fold at 75 bytes without splitting UTF-8 characters (RFC 5545).
    folded = []
    for line in lines:
        part = ''
        for character in line:
            if len((part+character).encode()) > 75:
                folded.append(part)
                part = ' '
            part += character
        folded.append(part)
    return ('\r\n'.join(folded)+'\r\n').encode()
