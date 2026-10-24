import datetime as dt
import unittest
import training_views


class TrainingViewsTest(unittest.TestCase):
    def setUp(self):
        self.profile=dict(mileage=50,peak_mileage=70,weeks=16,goal_minutes=215,start_date='2026-10-26',off_day='Monday',long_run_day='Sunday')

    def test_schedule_matches_weekly_targets(self):
        days=training_views.schedule(self.profile)
        self.assertEqual(len(days),112)
        self.assertEqual(sum(day['miles'] for day in days[:7]),50)
        self.assertEqual(days[0]['workout'],'Rest')
        self.assertEqual(days[6]['workout'],'Long Run')
        self.assertEqual(days[-1]['date'],dt.date(2027,2,14))
        self.assertNotIn('Long Run',[day['workout'] for day in days[-7:]])

    def test_review_compares_recorded_days_only(self):
        days=training_views.schedule(self.profile)[:7]
        logs={'2026-10-27':dict(miles=5,sleep=6,effort=8), '2026-10-26':dict(miles=0,sleep=8,effort=1)}
        result=training_views.review(days,logs)
        self.assertEqual(result['days'],2)
        self.assertEqual(result['planned'],days[1]['miles'])
        self.assertEqual(result['actual'],5)
        self.assertEqual(result['sleep'],7)
        self.assertEqual(result['effort'],8)
        self.assertIsNone(training_views.review(days,{})['sleep'])

    def test_calendar_escape(self):
        self.assertEqual(training_views.ics_escape('a,b;c\nd'),r'a\,b\;c\nd')
