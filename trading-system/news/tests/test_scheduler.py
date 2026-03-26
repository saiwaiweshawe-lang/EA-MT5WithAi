import unittest
import time
from news.scheduler.crawler_scheduler import CrawlerScheduler, CronExpression


class TestCrawlerScheduler(unittest.TestCase):
    def test_scheduler_creation(self):
        scheduler = CrawlerScheduler({"interval_seconds": 60})
        self.assertFalse(scheduler.is_running())
        self.assertEqual(scheduler.interval_seconds, 60)

    def test_add_remove_job(self):
        scheduler = CrawlerScheduler()

        def dummy_job():
            pass

        scheduler.add_job(dummy_job)
        self.assertEqual(len(scheduler._callbacks), 1)

        result = scheduler.remove_job(dummy_job)
        self.assertTrue(result)
        self.assertEqual(len(scheduler._callbacks), 0)

    def test_get_status(self):
        scheduler = CrawlerScheduler({"interval_seconds": 60})
        status = scheduler.get_status()
        self.assertFalse(status["running"])
        self.assertEqual(status["interval_seconds"], 60)
        self.assertEqual(status["jobs_count"], 0)

    def test_run_now(self):
        scheduler = CrawlerScheduler()
        results = []

        def test_job():
            results.append(1)

        scheduler.add_job(test_job)
        scheduler.run_now()
        self.assertEqual(len(results), 1)


class TestCronExpression(unittest.TestCase):
    def test_parse_simple(self):
        result = CronExpression.parse("0 * * * *")
        self.assertIsNotNone(result)
        self.assertIn("minute", result)

    def test_parse_wildcard(self):
        result = CronExpression.parse("* * * * *")
        self.assertIsNotNone(result)
        self.assertEqual(len(result["minute"]), 60)

    def test_parse_range(self):
        result = CronExpression.parse("0 9-17 * * *")
        self.assertIsNotNone(result)
        self.assertIn(9, result["hour"])
        self.assertIn(17, result["hour"])

    def test_parse_step(self):
        result = CronExpression.parse("*/5 * * * *")
        self.assertIsNotNone(result)
        self.assertIn(0, result["minute"])
        self.assertIn(5, result["minute"])
        self.assertIn(10, result["minute"])

    def test_parse_invalid(self):
        result = CronExpression.parse("invalid")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
