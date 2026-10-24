"""Local web interface for the original marathon planner (Python standard library)."""
import csv
import io
import datetime as dt
import html
import json
import os
from pathlib import Path
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import marathon_planner as planner

DB = Path(os.environ.get('MARATHON_DB', Path(__file__).parent / '.local' / 'training.sqlite3'))


def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.executescript('''CREATE TABLE IF NOT EXISTS profile (id INTEGER PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS journal (date TEXT PRIMARY KEY, miles REAL NOT NULL, minutes REAL NOT NULL, effort INTEGER NOT NULL, sleep REAL NOT NULL, quality INTEGER NOT NULL, notes TEXT NOT NULL);''')
    return db


def esc(value):
    return html.escape(str(value), quote=True)


def number(data, key, low, high, integer=False):
    value = int(data[key]) if integer else float(data[key])
    if not low <= value <= high:
        raise ValueError(f'{key.replace("_", " ")} must be between {low} and {high}.')
    return value


def field(label, name, value='', kind='number', extra=''):
    return f'<label>{label}<input name="{name}" type="{kind}" value="{esc(value)}" {extra} required></label>'


def render(message='', selected_date=None):
    with connect() as db:
        row = db.execute('SELECT data FROM profile WHERE id=1').fetchone()
        logs = db.execute('SELECT * FROM journal ORDER BY date DESC').fetchall()
    selected_date = selected_date or dt.date.today().isoformat()
    entry = next((dict(log) for log in logs if log['date'] == selected_date), {})
    log_by_date = {log['date']: log for log in logs}
    profile = json.loads(row[0]) if row else {}
    defaults = dict(name='Runner', mileage=30, peak_mileage=50, weeks=16, goal_minutes=240,
                    start_date=(dt.date.today()-dt.timedelta(days=dt.date.today().weekday())).isoformat(), off_day='Monday', long_run_day='Sunday')
    defaults.update(profile)
    p = defaults
    choices = lambda key: '<label>'+('Rest day' if key == 'off_day' else 'Long run day')+f'<select name="{key}">'+''.join(f'<option {"selected" if d == p[key] else ""}>{d}</option>' for d in planner.DAYS)+'</select></label>'
    setup = '<details '+('' if profile else 'open')+'><summary>Your training plan</summary><form method="post" action="/profile"><div class="fields">'
    setup += field('Runner name','name',p['name'],'text','maxlength="80"')
    setup += field('Starting miles / week','mileage',p['mileage'],extra='min="1" max="300"')
    setup += field('Peak miles / week','peak_mileage',p['peak_mileage'],extra='min="1" max="300"')
    setup += field('Training weeks','weeks',p['weeks'],extra='min="4" max="104"')
    setup += field('Goal time · hours','goal_hours',p['goal_minutes']//60,extra='min="0" max="24"')
    setup += field('Goal time · minutes','goal_minute_part',p['goal_minutes']%60,extra='min="0" max="59"')
    setup += field('Plan starts on Monday','start_date',p['start_date'],'date')+choices('off_day')+choices('long_run_day')
    setup += '</div><button>Save plan</button><p class="muted">Updating these settings recalculates the plan. Your journal stays saved.</p></form></details>'
    plan_html = '<section><h2>Make a plan, then make it yours.</h2><p>Save your training settings to see your weekly schedule.</p></section>'
    if profile:
        plan = planner.calculate_weekly_plan(p['mileage'],p['peak_mileage'],p['weeks'])
        start = dt.date.fromisoformat(p['start_date'])
        pace = p['goal_minutes']/26.2
        plan_html = '<h2>Your training calendar</h2><p class="muted">Build your base. Find your peak. Arrive fresh. Taper: 70%, 45%, then 25% of peak mileage; race distance is additional.</p>'
        today = dt.date.today()
        week_index = (today-start).days // 7
        if week_index < 0:
            phase = f'Plan starts in {(start-today).days} days'
        elif week_index >= len(plan):
            phase = 'Training block complete'
        else:
            phase = f'Week {week_index+1} of {len(plan)} · {plan[week_index]["label"]}'
        plan_html = f'<section><h2>{esc(phase)}</h2><p>Race week: {(start+dt.timedelta(weeks=len(plan)-1)):%b %d, %Y}. Exact race day is not set.</p><div class="fields">'+''.join(f'<div><strong>{esc(workout)}</strong><p>{esc(planner.workout_pace(workout,pace))}</p></div>' for workout in planner.PACE_OFFSETS)+'</div></section>'+plan_html
        chart = '<section class="volume"><div class="eyebrow">THE ROAD TO RACE DAY</div><h2>Your mileage, mapped out.</h2><div class="bars" role="img" aria-label="Weekly mileage: '+esc(', '.join(f'week {w["week"]}: {w["mileage"]} miles' for w in plan))+'">'
        for w in plan:
            height = max(3, w['mileage']/max(p['peak_mileage'],1)*100)
            style = 'taper' if w['week'] > len(plan)-3 else 'peak' if w['label']=='Peak Week' else ''
            chart += f'<a class="bar {style}" href="#week-{w["week"]}" style="--height:{height}%" title="Week {w["week"]}: {w["mileage"]} miles"><b>{w["mileage"]}</b><i></i><small>{w["week"]}</small></a>'
        plan_html = chart+'</div><p class="muted">Week number below each bar · lime marks the peak · pink marks the taper</p></section>'+plan_html
        for week in plan:
            daily = planner.allocate_daily_mileage(week,planner.DAYS,p['off_day'],p['long_run_day'])
            week_start = start+dt.timedelta(weeks=week['week']-1)
            week_logs = [log for log in logs if week_start.isoformat() <= log['date'] < (week_start+dt.timedelta(days=7)).isoformat()]
            actual = sum(log['miles'] for log in week_logs)
            progress = min(actual / week['mileage'] * 100, 100) if week['mileage'] else 0
            progress_html = f'<p>{actual:g} miles logged / {week["mileage"]} planned · {len(week_logs)} days recorded (unlogged days are unknown)</p><progress max="100" value="{progress}" aria-label="Weekly mileage completed"></progress>'
            plan_html += f'<details id="week-{week["week"]}"><summary>Week {week["week"]} · {esc(week["label"])} <span>{week["mileage"]} mi · {week_start:%b %d}</span></summary>{progress_html}<div class="days">'
            for i, day in enumerate(planner.DAYS):
                date = week_start+dt.timedelta(days=i)
                if day == p['off_day']:
                    description='Rest day'
                else:
                    workout = 'Long Run' if day == p['long_run_day'] and week['long_run'] is not None else 'Tempo' if day == 'Tuesday' and week['label'] != 'Race Week' and daily[day]>=3 else 'Interval' if day == 'Thursday' and week['label'] != 'Race Week' and daily[day]>=3 else 'Easy'
                    description = planner.workout_details(workout,week,daily[day],pace)
                logged = log_by_date.get(date.isoformat())
                result = f'Logged: {logged["miles"]:g} mi · effort {logged["effort"]}/10' if logged else 'Not logged'
                plan_html += f'<article><strong>{day} · {date:%b %d}</strong><p>{esc(description)}</p><p>{result} · <a href="/?date={date.isoformat()}#journal">Log / edit this day</a></p></article>' 
            plan_html += '</div></details>'
    journal = '<section id="journal"><h2>How did today feel?</h2><p>Log a run or a rest day. Sleep refers to the night before this date. Saving the same date replaces its entry.</p><form method="post" action="/journal"><div class="fields">'
    journal += field('Date','date',selected_date,'date')
    for label,key,value,extra in [('Distance (miles)','miles',0,'min="0" max="300" step="0.01"'),('Run duration (minutes)','minutes',0,'min="0" max="3000" step="0.1"'),('Run effort (1 easy – 10 maximal)','effort',5,'min="1" max="10"'),('Sleep (hours)','sleep',8,'min="0" max="24" step="0.1"'),('Sleep quality (1 poor – 5 great)','quality',3,'min="1" max="5"')]:
        journal += field(label,key,entry.get(key,value),extra=extra)
    journal += '</div><label>Run feedback & recovery notes<textarea name="notes" maxlength="4000" placeholder="How did your legs feel? Energy, soreness, stress…">'+esc(entry.get("notes",""))+'</textarea></label><button>Save daily entry</button></form></section>'
    today = dt.date.today()
    recent = [log for log in logs if (today-dt.timedelta(days=6)).isoformat() <= log['date'] <= today.isoformat()]
    runs = [log for log in recent if log['miles'] > 0]
    trends = '<section><h2>The last 7 days</h2>'
    if recent:
        sleep = sum(log['sleep'] for log in recent)/len(recent)
        quality = sum(log['quality'] for log in recent)/len(recent)
        trends += f'<p>{len(recent)} of 7 days recorded · {sum(log["miles"] for log in recent):g} miles logged · average sleep {sleep:.1f}h · sleep quality {quality:.1f}/5</p>'
        if runs:
            effort = sum(log['effort'] for log in runs)/len(runs)
            trends += f'<p>Average run effort: {effort:.1f}/10 across {len(runs)} run days.</p>'
        trends += '<p class="muted">Averages use recorded days only. Review your notes alongside these trends before changing your training.</p>'
    else:
        trends += '<p>No entries in the last 7 days. Log sleep on rest days too for a fuller picture.</p>'
    trends += '</section>'
    history='<section><h2>Your journal</h2><p><a href="/export.csv">Export journal CSV</a> · <a href="/backup.json">Download full backup</a></p>' 
    if not logs:
        history += '<p class="muted">Your first entry starts here. Run feedback and sleep will appear together.</p>'
    for log in logs:
        pace_text = planner.format_pace(log['minutes']/log['miles'])+' / mile' if log['miles'] > 0 and log['minutes'] > 0 else 'Pace unavailable'
        history += f'<article><strong>{esc(log["date"])} · {log["miles"]:g} miles</strong><p>{log["minutes"]:g} minutes · effort {log["effort"]}/10 · sleep {log["sleep"]:g}h · quality {log["quality"]}/5</p><p>{pace_text} · <a href="/?date={log["date"]}#journal">Edit entry</a></p><p class="notes">{esc(log["notes"])}</p></article>'
    history+='</section>'
    total=sum(x['miles'] for x in logs)
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Stride · Marathon planner</title><style>
:root{{font-family:system-ui,sans-serif;color:#173b32;background:#f4f5ef}}*{{box-sizing:border-box}}body{{margin:0}}main{{max-width:1100px;margin:auto;padding:32px 20px}}header{{padding:30px 0}}small,.muted{{color:#62766b}}h1{{font-size:clamp(36px,6vw,60px);letter-spacing:-2px;margin:12px 0}}h2{{margin-top:0}}section,details{{background:white;border:1px solid #dce3d9;border-radius:16px;padding:24px;margin:18px 0}}summary{{cursor:pointer;font-weight:650}}summary span{{display:inline-block;margin-left:15px;color:#62766b;font-weight:400}}.fields{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px;margin:20px 0}}label{{display:block;font-size:14px;font-weight:550}}input,select,textarea{{display:block;width:100%;padding:12px;border:1px solid #bfcec3;border-radius:8px;background:#fff;color:#173b32;font:inherit;margin-top:7px}}textarea{{min-height:100px}}button{{background:#244e3e;color:white;border:0;border-radius:8px;padding:13px 22px;font:inherit;margin-top:18px;cursor:pointer}}article{{border-top:1px solid #e3e9df;padding:17px 0}}article:last-child{{padding-bottom:0}}p{{line-height:1.6}}.notice{{padding:16px;background:#e5eddc;border-radius:10px}}.notes{{white-space:pre-wrap}}a{{color:#245d47}}progress{{width:100%;height:14px;accent-color:#244e3e}}.stats{{display:flex;gap:28px;flex-wrap:wrap}}

:root{{color:#edf3f8;background:#0c111b}}body{{background:radial-gradient(ellipse at 90% 0%,#253443 0,transparent 45%),#0c111b}}main{{max-width:1200px}}nav{{display:flex;justify-content:space-between;align-items:center;padding:8px 0 24px;border-bottom:1px solid #34404e}}nav a{{color:#c3f954;text-decoration:none;font-size:13px;font-weight:800}}.brand{{font-size:26px;letter-spacing:3px}}.brand span{{color:#ff8068}}header{{position:relative;padding:55px 0 35px}}header small,.eyebrow{{color:#c3f954;font-size:11px;letter-spacing:3px;font-weight:800}}h1{{font-size:clamp(48px,9vw,100px);line-height:.95;letter-spacing:-4px;font-weight:900;margin:25px 0}}h1 em{{color:#c3f954;font-style:normal}}header>p{{color:#afbdcb;font-size:17px}}.stats{{margin-top:30px;gap:12px}}.stats>*{{border:1px solid #3c4857;border-radius:30px;padding:10px 18px;color:#e8eef6;background:#18222f}}section,details{{background:#161f2b;border-color:#303c4b;border-radius:18px}}h2{{font-size:26px;letter-spacing:-.6px}}.muted,small,summary span{{color:#a4b2c2}}summary{{font-size:17px}}details[open]>summary{{padding-bottom:18px;color:#c3f954}}input,select,textarea{{background:#0e1621;border-color:#435064;color:#edf3f8}}input:focus,select:focus,textarea:focus{{outline:2px solid #c3f954;outline-offset:2px}}label{{color:#b8c5d3}}button{{background:#c3f954;color:#102008;font-weight:800;border-radius:30px}}button:hover{{background:#d8ff8a}}a{{color:#c3f954}}article{{border-color:#354052}}.notice{{background:#263b24;color:#e3ffd0}}progress{{accent-color:#c3f954}}.bars{{display:flex;align-items:stretch;gap:clamp(3px,1vw,12px);height:200px;overflow-x:auto;padding-top:25px}}.bar{{display:flex;flex:1;min-width:18px;flex-direction:column;justify-content:flex-end;text-align:center;text-decoration:none;color:#b7c4d3;font-size:11px}}.bar b{{font-weight:600;margin-bottom:5px}}.bar i{{display:block;min-height:3px;height:var(--height);background:#6c91b3;border-radius:5px 5px 0 0}}.bar.peak i{{background:#c3f954}}.bar.taper i{{background:#ff8caa}}.bar small{{padding-top:8px;font-size:10px}}.bar:hover i{{filter:brightness(1.3)}}.volume{{background:linear-gradient(130deg,#202c3d,#141e2b)}}.eyebrow{{margin-bottom:10px}}footer{{padding:20px 0}}@media(min-width:800px){{.days{{display:grid;grid-template-columns:repeat(2,1fr);gap:0 28px}}}}@media(prefers-reduced-motion:no-preference){{button,a{{transition:filter .15s,background .15s}}html{{scroll-behavior:smooth}}}}@media(max-width:500px){{section,details{{padding:18px}}h1{{letter-spacing:-2px}}.bars{{gap:4px}}}}
</style><main><nav><a class="brand" href="/">STRIDE<span>↗</span></a><a href="#journal">LOG YOUR RUN ↗</a></nav><header><small>YOUR NEXT FINISH LINE STARTS HERE</small><h1>CHASE THE<br><em>FINISH LINE.</em></h1><p>Big goals. Daily effort. A training plan that moves with you.</p><div class="stats"><strong>{esc(p['name'])}</strong><span>{total:g} miles logged</span><span>{len(logs)} daily entries</span></div></header>{'<p class="notice" role="status">'+esc(message)+'</p>' if message else ''}{setup}{trends}{journal}{plan_html}{history}<footer><p class="muted">Manual logging · Stored locally on this machine · Garmin integration planned</p></footer></main></html>'''


class Handler(BaseHTTPRequestHandler):
    def page(self, message='', status=200, selected_date=None):
        content=render(message, selected_date).encode()
        self.send_response(status)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Content-Length',str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path in ('/export.csv', '/backup.json'):
            with connect() as db:
                logs = [dict(row) for row in db.execute('SELECT * FROM journal ORDER BY date')]
                profile = db.execute('SELECT data FROM profile WHERE id=1').fetchone()
            if url.path == '/backup.json':
                content = json.dumps(dict(version=1, profile=json.loads(profile[0]) if profile else None, journal=logs), indent=2).encode()
                mime, filename = 'application/json', 'marathon-backup.json'
            else:
                output = io.StringIO(newline='')
                writer = csv.writer(output)
                keys = ['date','miles','minutes','effort','sleep','quality','notes']
                writer.writerow(keys)
                for log in logs:
                    # Keep spreadsheet applications from executing journal text as formulas.
                    writer.writerow([("'"+str(log[key])) if isinstance(log[key],str) and log[key].lstrip().startswith(('=','+','-','@')) else log[key] for key in keys])
                content = output.getvalue().encode()
                mime, filename = 'text/csv; charset=utf-8', 'marathon-journal.csv'
            self.send_response(200)
            self.send_header('Content-Type',mime)
            self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
            self.send_header('Content-Length',str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        if url.path != '/':
            self.send_error(404)
            return
        try:
            selected = parse_qs(url.query).get('date',[dt.date.today().isoformat()])[0]
            selected = dt.date.fromisoformat(selected).isoformat()
            self.page(selected_date=selected)
        except ValueError:
            self.page('Choose a valid journal date.',400)

    def do_POST(self):
        # Only accept forms originating from this local app.
        origin=self.headers.get('Origin')
        if origin and origin != 'http://'+self.headers.get('Host',''):
            self.send_error(403)
            return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 32000:
                raise ValueError('Invalid form size.')
            data={k:v[0] for k,v in parse_qs(self.rfile.read(length).decode(),keep_blank_values=True).items()}
            with connect() as db:
                if self.path == '/profile':
                    p={key:number(data,key,low,high,True) for key,low,high in [('mileage',1,300),('peak_mileage',1,300),('weeks',4,104)]}
                    if 'goal_hours' in data or 'goal_minute_part' in data:
                        p['goal_minutes'] = number(data,'goal_hours',0,24,True)*60 + number(data,'goal_minute_part',0,59,True)
                        if not 60 <= p['goal_minutes'] <= 1440:
                            raise ValueError('Goal time must be between 1 and 24 hours.')
                    else:
                        # Preserve compatibility with previously saved total-minute inputs.
                        p['goal_minutes'] = number(data,'goal_minutes',60,1440,True)
                    if p['peak_mileage'] < p['mileage']:
                        raise ValueError('Peak mileage must be at least starting mileage.')
                    start=dt.date.fromisoformat(data['start_date'])
                    if start.weekday()!=0:
                        raise ValueError('Choose a Monday so your calendar matches the training weekdays.')
                    if data['off_day'] not in planner.DAYS or data['long_run_day'] not in planner.DAYS or data['off_day']==data['long_run_day']:
                        raise ValueError('Choose different valid rest and long run days.')
                    p.update({key:data[key] for key in ['name','start_date','off_day','long_run_day']})
                    p['name']=p['name'].strip()[:80]
                    if not p['name']:
                        raise ValueError('Enter a runner name.')
                    db.execute('INSERT OR REPLACE INTO profile VALUES (1,?)',(json.dumps(p),))
                elif self.path == '/journal':
                    date=dt.date.fromisoformat(data['date']).isoformat()
                    values=[number(data,key,low,high,integer) for key,low,high,integer in [('miles',0,300,False),('minutes',0,3000,False),('effort',1,10,True),('sleep',0,24,False),('quality',1,5,True)]]
                    db.execute('INSERT OR REPLACE INTO journal VALUES (?,?,?,?,?,?,?)',(date,*values,data.get('notes','')[:4000]))
                else:
                    self.send_error(404)
                    return
            self.send_response(303)
            self.send_header('Location','/')
            self.end_headers()
        except (ValueError,KeyError) as error:
            self.page('Please check your entry: '+str(error),400)


if __name__ == '__main__':
    server=ThreadingHTTPServer(('127.0.0.1',int(os.environ.get('PORT','8000'))),Handler)
    print('Marathon planner listening on port '+str(server.server_port),flush=True)
    server.serve_forever()
