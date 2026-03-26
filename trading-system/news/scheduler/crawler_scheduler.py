import logging
import threading
import time
from datetime import datetime
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class CrawlerScheduler:
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.interval_seconds = self.config.get("interval_seconds", 300)
        self.cron_expression = self.config.get("cron_expression")
        self.enabled = self.config.get("enabled", True)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable] = []
        self._last_run: Optional[datetime] = None
        self._next_run: Optional[datetime] = None

    def start(self) -> None:
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"Scheduler started with interval {self.interval_seconds}s")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("Scheduler stopped")

    def is_running(self) -> bool:
        return self._running

    def add_job(self, callback: Callable) -> None:
        if callback not in self._callbacks:
            self._callbacks.append(callback)
            logger.info(f"Added job: {callback.__name__}")

    def remove_job(self, callback: Callable) -> bool:
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            logger.info(f"Removed job: {callback.__name__}")
            return True
        return False

    def _run_loop(self) -> None:
        while self._running:
            self._execute_jobs()
            self._schedule_next_run()

            if self._running:
                sleep_time = self._calculate_sleep_time()
                if sleep_time > 0:
                    time.sleep(sleep_time)

    def _execute_jobs(self) -> None:
        if not self._callbacks:
            return

        logger.info(f"Executing {len(self._callbacks)} scheduled jobs")
        self._last_run = datetime.now()

        for callback in self._callbacks:
            try:
                logger.debug(f"Executing job: {callback.__name__}")
                result = callback()

                if result is not None:
                    logger.info(f"Job {callback.__name__} completed")

            except Exception as e:
                logger.error(f"Job {callback.__name__} failed: {e}")

    def _schedule_next_run(self) -> None:
        self._next_run = datetime.now().replace(
            microsecond=0
        ) + self._calculate_interval()

    def _calculate_sleep_time(self) -> float:
        if self._next_run is None:
            return self.interval_seconds

        now = datetime.now()
        delta = (self._next_run - now).total_seconds()
        return max(0, delta)

    def _calculate_interval(self):
        return self._next_run - datetime.now() if self._next_run else None

    def run_now(self) -> None:
        logger.info("Running all jobs immediately")
        self._execute_jobs()

    def get_status(self) -> Dict:
        return {
            "running": self._running,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "next_run": self._next_run.isoformat() if self._next_run else None,
            "interval_seconds": self.interval_seconds,
            "jobs_count": len(self._callbacks),
        }

    def update_interval(self, interval_seconds: int) -> None:
        if interval_seconds > 0:
            self.interval_seconds = interval_seconds
            logger.info(f"Updated interval to {interval_seconds}s")


class CronExpression:
    CRON_FIELDS = ["minute", "hour", "day", "month", "weekday"]

    @staticmethod
    def parse(cron_expr: str) -> Optional[Dict[str, List[int]]]:
        try:
            parts = cron_expr.split()
            if len(parts) != 5:
                return None

            result = {}
            for i, field_name in enumerate(CronExpression.CRON_FIELDS):
                result[field_name] = CronExpression._parse_field(parts[i], field_name)

            return result

        except (ValueError, IndexError):
            return None

    @staticmethod
    def _parse_field(field: str, field_name: str) -> List[int]:
        if field == "*":
            if field_name == "minute":
                return list(range(60))
            elif field_name == "hour":
                return list(range(24))
            elif field_name == "day":
                return list(range(31))
            elif field_name == "month":
                return list(range(12))
            elif field_name == "weekday":
                return list(range(7))
            return []

        values = []
        for part in field.split(","):
            if "-" in part:
                start, end = part.split("-")
                values.extend(range(int(start), int(end) + 1))
            elif "/" in part:
                base, step = part.split("/")
                step = int(step)
                if base == "*":
                    values.extend(range(0, 60, step))
                else:
                    base = int(base)
                    values.extend(range(base, 60, step))
            else:
                values.append(int(part))

        return sorted(list(set(values)))

    @staticmethod
    def matches(cron_parts: Dict[str, List[int]], now: datetime) -> bool:
        minute_match = now.minute in cron_parts.get("minute", [])
        hour_match = now.hour in cron_parts.get("hour", [])
        day_match = now.day in cron_parts.get("day", [])
        month_match = now.month in cron_parts.get("month", [])
        weekday_match = now.weekday() in cron_parts.get("weekday", [])

        day_asterisk = len(cron_parts.get("day", [])) == 31
        weekday_asterisk = len(cron_parts.get("weekday", [])) == 7

        if day_asterisk and weekday_asterisk:
            return minute_match and hour_match and month_match

        if day_asterisk:
            return minute_match and hour_match and month_match and weekday_match

        if weekday_asterisk:
            return minute_match and hour_match and month_match and day_match

        return (minute_match and hour_match and 
                ((day_match and month_match) or 
                 (weekday_match and month_match)))
