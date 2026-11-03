import unittest
from datetime import datetime, timedelta, timezone

from healthcheck import build_health_message


NOW = datetime(2026, 11, 3, 3, 55, tzinfo=timezone.utc)


def run(age, status, conclusion=None, event="workflow_dispatch"):
    return {
        "event": event,
        "status": status,
        "conclusion": conclusion,
        "created_at": (NOW - timedelta(minutes=age)).isoformat(),
    }


class HealthcheckTests(unittest.TestCase):
    def test_recent_inprogress_with_prior_success_is_healthy(self):
        result = build_health_message(
            [run(0, "in_progress"), run(5, "completed", "success")], NOW
        )
        self.assertIn("✅", result)
        self.assertIn("5분 전", result)
        self.assertNotIn("⚠️", result)

    def test_running_without_completed_is_not_false_warning(self):
        result = build_health_message([run(0, "in_progress")], NOW)
        self.assertIn("⏳", result)
        self.assertNotIn("⚠️", result)

    def test_queued_workflow_is_not_failure(self):
        result = build_health_message([run(1, "queued")], NOW)
        self.assertIn("⏳", result)

    def test_latest_failure_still_warns(self):
        result = build_health_message(
            [run(3, "completed", "failure"), run(8, "completed", "success")], NOW
        )
        self.assertIn("⚠️", result)
        self.assertIn("failure", result)

    def test_stale_running_warns(self):
        result = build_health_message([run(25, "in_progress")], NOW)
        self.assertIn("⚠️", result)

    def test_stale_success_warns(self):
        result = build_health_message([run(35, "completed", "success")], NOW)
        self.assertIn("⚠️", result)

    def test_fresh_success_is_healthy(self):
        result = build_health_message([run(4, "completed", "success")], NOW)
        self.assertIn("✅", result)

    def test_no_runs_warns(self):
        result = build_health_message([], NOW)
        self.assertIn("⚠️", result)

    def test_ignore_unrelated_trigger(self):
        result = build_health_message([run(2, "completed", "success", "pull_request")], NOW)
        self.assertIn("⚠️", result)


if __name__ == "__main__":
    unittest.main()
