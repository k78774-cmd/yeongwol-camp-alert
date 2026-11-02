"""Daily diagnostic message; never changes reservation state."""
import os
from datetime import datetime, timezone

import requests


REPO = os.environ["GITHUB_REPOSITORY"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

run_url = f"https://api.github.com/repos/{REPO}/actions/workflows/main.yml/runs"
response = requests.get(
    run_url,
    headers={
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    },
    params={"per_page": 10},
    timeout=30,
)
response.raise_for_status()

runs = response.json().get("workflow_runs", [])
runs = [
    run for run in runs
    if run.get("event") in ("schedule", "workflow_dispatch", "push")
]
now = datetime.now(timezone.utc)

if not runs:
    text = "⚠️ 영월캠프 예약 감시 확인 필요: 최근 실행 기록이 없습니다."
else:
    latest = max(runs, key=lambda item: item.get("created_at", ""))
    started_at = datetime.fromisoformat(
        latest["created_at"].replace("Z", "+00:00")
    )
    age_minutes = int((now - started_at).total_seconds() / 60)
    conclusion = latest.get("conclusion")
    status = latest.get("status")

    if status == "completed" and conclusion == "success" and age_minutes <= 20:
        text = (
            "✅ 영월캠프 예약 감시 정상 작동 확인\n"
            f"최근 실행: {age_minutes}분 전\n"
            "예약 가능 여부는 별도 알림입니다."
        )
    else:
        text = (
            "⚠️ 영월캠프 예약 감시 점검 필요\n"
            f"최근 실행: {age_minutes}분 전\n"
            f"결과: {status}/{conclusion}\n"
            "GitHub Actions 실행 기록을 확인하세요."
        )

try:
    sent = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data={"chat_id": TELEGRAM_CHAT_ID, "text": text},
        timeout=30,
    )
    sent.raise_for_status()
except Exception:
    # Requests error messages can include the bot token in the URL.
    raise RuntimeError("일일 점검 메시지 전송 실패 (토큰 정보 숨김)") from None

print("일일 상태 점검 메시지 전송 성공")
