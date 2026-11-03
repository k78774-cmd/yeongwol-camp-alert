"""Daily Telegram diagnostic of the camp monitoring workflow.

A running/queued workflow is not a failure. Only report a confirmed failure,
a stale run, or a long absence of successful monitoring as a warning.
"""
import os
from datetime import datetime, timezone

import requests


STALE_MINUTES = 20
RUNNING_GRACE_MINUTES = 12
ACTIVE_STATUSES = {"queued", "in_progress", "waiting", "pending", "requested"}


def minutes_ago(when, now):
    stamp = datetime.fromisoformat(when.replace("Z", "+00:00"))
    return max(0, int((now - stamp).total_seconds() // 60))


def build_health_message(runs, now):
    """Build an accurate status without performing API calls."""
    runs = [
        run for run in runs
        if run.get("event") in {"schedule", "workflow_dispatch", "push"}
        and run.get("created_at")
    ]
    runs.sort(key=lambda run: run["created_at"], reverse=True)

    if not runs:
        return "⚠️ 영월캠프 예약 감시 점검 필요\n실행 기록이 없습니다."

    latest = runs[0]
    age = minutes_ago(latest["created_at"], now)
    completed = next(
        (run for run in runs if run.get("status") == "completed"), None
    )
    completed_age = (
        minutes_ago(completed["created_at"], now) if completed else None
    )

    if latest.get("status") in ACTIVE_STATUSES and age <= RUNNING_GRACE_MINUTES:
        # A new run often starts exactly when the daily check is querying GitHub.
        # Use the most recent completed run, not the new one's conclusion=None.
        if (
            completed is not None
            and completed.get("conclusion") == "success"
            and completed_age <= STALE_MINUTES
        ):
            return (
                "✅ 영월캠프 예약 감시 정상 작동\n"
                f"최근 완료된 감시: {completed_age}분 전 (성공)\n"
                "새 감시 작업도 진행 중입니다.\n"
                "빈 객실 발견 알림은 별도로 전송됩니다."
            )
        return (
            "⏳ 영월캠프 예약 감시 실행 중\n"
            f"최근 시작: {age}분 전\n"
            "아직 결과가 확정되지 않았습니다. 장애 경고가 아닙니다."
        )

    if latest.get("status") == "completed":
        if latest.get("conclusion") == "success" and age <= STALE_MINUTES:
            return (
                "✅ 영월캠프 예약 감시 정상 작동\n"
                f"최근 완료된 감시: {age}분 전 (성공)\n"
                "빈 객실 발견 알림은 별도로 전송됩니다."
            )
        if latest.get("conclusion") != "success":
            return (
                "⚠️ 영월캠프 예약 감시 점검 필요\n"
                f"가장 최근 실행: {age}분 전\n"
                f"결과: {latest.get('conclusion') or 'unknown'}\n"
                "GitHub Actions 실행 기록을 확인하세요."
            )

    if latest.get("status") in ACTIVE_STATUSES:
        return (
            "⚠️ 영월캠프 예약 감시 장시간 실행 중\n"
            f"시작 후 {age}분 경과\n"
            "GitHub Actions 실행 기록을 확인하세요."
        )

    return (
        "⚠️ 영월캠프 예약 감시 점검 필요\n"
        f"가장 최근 실행: {age}분 전\n"
        "최근 성공한 감시 기록이 없습니다. GitHub Actions를 확인하세요."
    )


def main():
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    response = requests.get(
        f"https://api.github.com/repos/{repo}/actions/workflows/main.yml/runs",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        params={"per_page": 30},
        timeout=30,
    )
    response.raise_for_status()

    message = build_health_message(
        response.json().get("workflow_runs", []),
        datetime.now(timezone.utc),
    )
    print("감시 상태: " + message.splitlines()[0])

    try:
        sent = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data={"chat_id": chat_id, "text": message},
            timeout=30,
        )
        sent.raise_for_status()
    except Exception:
        # The Telegram URL contains a secret; never print request exceptions.
        raise RuntimeError("점검 메시지 전송 실패 (인증정보 숨김)") from None

    print("일일 상태 점검 메시지 전송 성공")


if __name__ == "__main__":
    main()
