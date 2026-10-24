import http.client
import datetime as dt
import json
import csv
import io
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

import web_app


class AppTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.old_db=web_app.DB
        web_app.DB=Path(cls.temp.name)/'training.db'
        cls.server=web_app.ThreadingHTTPServer(('127.0.0.1',0),web_app.Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        web_app.DB=cls.old_db
        cls.temp.cleanup()

    def setUp(self):
        with web_app.connect() as db:
            db.execute('DELETE FROM profile')
            db.execute('DELETE FROM journal')

    def request(self, path='/', data=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        connection.request('POST' if data is not None else 'GET',path,urlencode(data) if data is not None else None,{'Content-Type':'application/x-www-form-urlencoded'})
        response=connection.getresponse()
        status,body=response.status,response.read().decode()
        connection.close()
        return status,body

    def test_plan_and_persistent_journal(self):
        profile=dict(name='Runner',mileage=30,peak_mileage=50,weeks=16,goal_minutes=240,start_date='2026-10-26',off_day='Monday',long_run_day='Sunday')
        self.assertEqual(self.request('/profile',profile)[0],303)
        status,body=self.request()
        self.assertEqual(status,200)
        self.assertIn('Week 13 · Peak Week',body)
        self.assertIn('Week 16 · Race Week',body)
        self.assertIn('Rest day',body)
        self.assertIn('long-run pace',body)
        entry=dict(date='2026-10-27',miles=5,minutes=48,effort=6,sleep=7.5,quality=4,notes='<script>tired</script>')
        self.assertEqual(self.request('/journal',entry)[0],303)
        body=self.request()[1]
        self.assertIn('5 miles logged',body)
        self.assertIn('&lt;script&gt;tired&lt;/script&gt;',body)
        self.assertIn('sleep 7.5h',body)
        entry['miles']=6
        self.assertEqual(self.request('/journal',entry)[0],303)
        with web_app.connect() as db:
            self.assertEqual(db.execute('SELECT count(*),miles FROM journal').fetchone()[:],(1,6.0))
        entry['sleep']='nan'
        self.assertEqual(self.request('/journal',entry)[0],400)
        profile['long_run_day']='Monday'
        self.assertEqual(self.request('/profile',profile)[0],400)
        profile['long_run_day']='Sunday'
        profile['start_date']='2026-10-27'
        self.assertEqual(self.request('/profile',profile)[0],400)

    def test_weekly_progress_and_edit_prefill(self):
        profile=dict(name='Runner',mileage=30,peak_mileage=50,weeks=16,goal_minutes=240,start_date='2026-10-26',off_day='Monday',long_run_day='Sunday')
        self.assertEqual(self.request('/profile',profile)[0],303)
        entry=dict(date='2026-10-27',miles=5,minutes=45,effort=6,sleep=7,quality=4,notes='Steady effort')
        self.assertEqual(self.request('/journal',entry)[0],303)
        status,body=self.request('/?date=2026-10-27')
        self.assertEqual(status,200)
        self.assertIn('5 miles logged / 30 planned',body)
        self.assertIn('Logged: 5 mi · effort 6/10',body)
        self.assertIn('name="miles" type="number" value="5.0"',body)
        self.assertIn('>Steady effort</textarea>',body)
        self.assertIn('9:00 / mile',body)
        self.assertEqual(self.request('/?date=bad')[0],400)

    def test_recovery_trends_and_rest_days(self):
        today=dt.date.today()
        for date,miles,effort,sleep in [(today,4,8,6),(today-dt.timedelta(days=1),0,1,8),(today-dt.timedelta(days=7),20,10,2)]:
            self.assertEqual(self.request('/journal',dict(date=date.isoformat(),miles=miles,minutes=40 if miles else 0,effort=effort,sleep=sleep,quality=3,notes=''))[0],303)
        body=self.request()[1]
        self.assertIn('2 of 7 days recorded · 4 miles logged · average sleep 7.0h',body)
        self.assertIn('Average run effort: 8.0/10 across 1 run days.',body)

    def test_goal_hours_and_minutes_round_trip(self):
        profile=dict(name='Runner',mileage=50,peak_mileage=70,weeks=16,goal_hours=3,goal_minute_part=35,start_date='2026-10-26',off_day='Monday',long_run_day='Sunday')
        self.assertEqual(self.request('/profile',profile)[0],303)
        with web_app.connect() as db:
            saved=json.loads(db.execute('SELECT data FROM profile').fetchone()[0])
        self.assertEqual(saved['goal_minutes'],215)
        body=self.request()[1]
        self.assertIn('name="goal_hours" type="number" value="3"',body)
        self.assertIn('name="goal_minute_part" type="number" value="35"',body)
        self.assertIn('Your mileage, mapped out.',body)
        self.assertIn('Week 7: 61 miles',body)
        profile['goal_minute_part']=60
        self.assertEqual(self.request('/profile',profile)[0],400)
        profile.update(goal_hours=0,goal_minute_part=0)
        self.assertEqual(self.request('/profile',profile)[0],400)

    def test_exports_preserve_data_and_escape_spreadsheet_formulas(self):
        self.assertEqual(self.request('/journal',dict(date='2026-10-27',miles=5,minutes=45,effort=6,sleep=7,quality=4,notes='=1+1'))[0],303)
        status,body=self.request('/export.csv')
        self.assertEqual(status,200)
        records=list(csv.DictReader(io.StringIO(body)))
        self.assertEqual(records[0]['notes'],"'=1+1")
        backup=json.loads(self.request('/backup.json')[1])
        self.assertEqual(backup['version'],1)
        self.assertEqual(backup['journal'][0]['notes'],'=1+1')
        self.assertIsNone(backup['profile'])


if __name__=='__main__':
    unittest.main()
