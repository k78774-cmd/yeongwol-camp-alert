import base64
import json
import os
import unittest
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "test_chat")
import monitor


class MonitorTests(unittest.TestCase):
    def test_room_one_detects_available_button(self):
        element = BeautifulSoup(
            '<a class="apply_btn p-on" onclick="reserve()">Room-1</a>',
            "html.parser",
        ).a
        self.assertTrue(monitor.facility_is_available(element))

    def test_room_one_detects_closed_button(self):
        element = BeautifulSoup(
            '<a class="apply_btn p-off" title="Room-1 - 예약마감">Room-1</a>',
            "html.parser",
        ).a
        self.assertFalse(monitor.facility_is_available(element))

    def test_only_saturdays(self):
        self.assertTrue(monitor.is_saturday(2026, 11, 7))
        self.assertFalse(monitor.is_saturday(2026, 11, 8))

    def test_unchanged_state_never_writes_commit(self):
        fake_get = Mock(status_code=200)
        fake_get.json.return_value = {
            "sha": "existing-sha",
            "content": base64.b64encode(b"[]").decode("utf-8"),
        }
        with patch.object(monitor, "GITHUB_TOKEN", "fake"), \
             patch.object(monitor, "GITHUB_REPOSITORY", "owner/repo"), \
             patch("monitor.requests.get", return_value=fake_get), \
             patch("monitor.requests.put") as fake_put:
            monitor.save_current_state([])
            fake_put.assert_not_called()

    def test_changed_state_commits(self):
        fake_get = Mock(status_code=200)
        fake_get.json.return_value = {
            "sha": "existing-sha",
            "content": base64.b64encode(b"[]").decode("utf-8"),
        }
        fake_put_result = Mock(status_code=200)
        with patch.object(monitor, "GITHUB_TOKEN", "fake"), \
             patch.object(monitor, "GITHUB_REPOSITORY", "owner/repo"), \
             patch("monitor.requests.get", return_value=fake_get), \
             patch("monitor.requests.put", return_value=fake_put_result) as fake_put:
            monitor.save_current_state([("2026-11-07", "Room-1")])
            fake_put.assert_called_once()
            payload = fake_put.call_args.kwargs["json"]
            decoded = json.loads(base64.b64decode(payload["content"]))
            self.assertEqual(decoded, [["2026-11-07", "Room-1"]])

    def test_failed_page_scan_marks_workflow_failed(self):
        with patch("monitor.get_target_months", return_value=[(2026, 11)]), \
             patch("monitor.check_month", side_effect=RuntimeError("site error")):
            with self.assertRaisesRegex(RuntimeError, "예약 페이지 확인 실패"):
                monitor.main()

    def test_failed_telegram_keeps_prior_state(self):
        with patch("monitor.get_target_months", return_value=[(2026, 11)]), \
             patch("monitor.check_month", return_value=[("2026-11-07", "Room-1")]), \
             patch("monitor.load_previous_state", return_value=[]), \
             patch("monitor.send_telegram", side_effect=RuntimeError("token-sensitive")), \
             patch("monitor.save_current_state") as fake_save:
            with self.assertRaisesRegex(RuntimeError, "Telegram 알림 발송 실패"):
                monitor.main()
            fake_save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
