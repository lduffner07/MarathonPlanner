import unittest
import marathon_planner as planner


class PlanningTest(unittest.TestCase):
    def test_fifty_to_seventy_build_and_taper(self):
        plan=planner.calculate_weekly_plan(50,70,16)
        self.assertEqual(plan[0]['mileage'],50)
        self.assertEqual([w['mileage'] for w in plan],
                         [50,52,54,48,57,59,61,54,63,66,68,61,70,49,31,17])
        self.assertEqual(plan[3]['label'],'Down Week')
        self.assertLess(plan[3]['mileage'],plan[2]['mileage'])
        self.assertEqual(plan[12]['mileage'],70)
        self.assertEqual([w['mileage'] for w in plan[-3:]],[49,31,17])
        self.assertIsNone(plan[-1]['long_run'])

    def test_three_build_one_down_across_plan_lengths(self):
        for weeks in (12,16,20,24):
            plan=planner.calculate_weekly_plan(30,60,weeks)
            peak_week=weeks-3
            high=30
            for week in plan[1:peak_week-1]:
                if week['week'] % 4 == 0:
                    self.assertEqual(week['label'],'Down Week')
                    self.assertEqual(week['mileage'],int(high*.9))
                else:
                    self.assertGreater(week['mileage'],high)
                    self.assertLess(week['mileage'],60)
                    high=week['mileage']
            self.assertEqual(plan[peak_week-1]['mileage'],60)

    def test_daily_totals_and_nonnegative_distances(self):
        for start,peak,weeks in [(50,70,16),(30,50,16),(50,50,12),(1,5,8),(30,50,4)]:
            for week in planner.calculate_weekly_plan(start,peak,weeks):
                daily=planner.allocate_daily_mileage(week,planner.DAYS,'Monday','Sunday')
                self.assertEqual(sum(daily.values()),week['mileage'])
                self.assertGreaterEqual(min(daily.values()),0)
                self.assertEqual(daily['Monday'],0)
