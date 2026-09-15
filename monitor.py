import os
import re
import json
import base64
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urlencode

BASE_URL = "https://www.sd.go.kr/booking/rcrtfrFcltyResveInfoWebRegistCalendarView.do"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY")

STATE_FILE = "alert_state.json"

FACILITIES = [
    "Room-1", "Room-2", "Room-3", "Room-4",
    "글램핑-1", "글램핑-2", "글램핑-3", "글램핑-4", "글램핑-5",
    "카라반-1", "카라반-2", "카라반-3", "카라반-4", "카라반-5",
    "일반데크-1", "일반데크-2", "일반데크-3", "일반데크-4", "일반데크-5"
]


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message
        },
        timeout=20
    )

    response.raise_for_status()


def get_month_url(year, month):
    params = {
        "key": "4865",
        "searchMonth": month,
        "searchYear": year,
        "siteId": "100"
    }

    return BASE_URL + "?" + urlencode(params)


def check_month(year, month):
    url = get_month_url(year, month)

    response = requests.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        },
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    results = []

    for cell in soup.find_all(["td", "div"]):

        text = cell.get_text(" ", strip=True)

        if not any(facility in text for facility in FACILITIES):
            continue

        date_match = re.search(
            r"(^|\s)([1-9]|[12][0-9]|3[01])(\s|$)",
            text
        )

        if not date_match:
            continue

        day = int(date_match.group(2))

        try:
            date_obj = datetime(year, month, day)
        except ValueError:
            continue

        # 토요일만 확인
        if date_obj.weekday() != 5:
            continue

        for link in cell.find_all("a"):

            facility_name = link.get_text(" ", strip=True)

            if facility_name not in FACILITIES:
                continue

            link_class = " ".join(link.get("class", []))
            link_text = link.get_text(" ", strip=True)

            combined = (
                link_class + " " +
                str(link.get("aria-disabled", "")) + " " +
                link_text
            ).lower()

            unavailable_words = [
                "disabled",
                "unavailable",
                "not",
                "불가",
                "마감",
                "예약불가",
                "close"
            ]

            if any(word in combined for word in unavailable_words):
                continue

            results.append(
                (date_obj.strftime("%Y-%m-%d"), facility_name)
            )

    return results


def load_previous_state():
    """
    GitHub 저장소에 저장된 이전 예약 상태를 가져온다.
    파일이 없으면 빈 상태로 시작한다.
    """

    if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
        print("GitHub 상태 저장용 환경변수가 없습니다.")
        return set(), None

    url = (
        f"https://api.github.com/repos/"
        f"{GITHUB_REPOSITORY}/contents/{STATE_FILE}"
    )

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=20
    )

    if response.status_code == 404:
        return set(), None

    response.raise_for_status()

    data = response.json()

    content = base64.b64decode(
        data["content"]
    ).decode("utf-8")

    state = json.loads(content)

    previous = set(state.get("available", []))

    return previous, data["sha"]


def save_current_state(current_results, sha=None):
    """
    현재 예약 가능 상태를 GitHub 저장소에 기록한다.
    """

    if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
        print("GitHub 상태 저장용 환경변수가 없습니다.")
        return

    url = (
        f"https://api.github.com/repos/"
        f"{GITHUB_REPOSITORY}/contents/{STATE_FILE}"
    )

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    state = {
        "available": sorted(current_results)
    }

    content = json.dumps(
        state,
        ensure_ascii=False,
        indent=2
    )

    encoded_content = base64.b64encode(
        content.encode("utf-8")
    ).decode("utf-8")

    payload = {
        "message": "예약 상태 업데이트",
        "content": encoded_content,
        "branch": "main"
    }

    if sha:
        payload["sha"] = sha

    response = requests.put(
        url,
        headers=headers,
        json=payload,
        timeout=20
    )

    response.raise_for_status()

    print("예약 상태를 GitHub에 저장했습니다.")


def main():

    today = datetime.now()

    months = []

    # 현재 월
    months.append((today.year, today.month))

    # 다음 달
    if today.month == 12:
        months.append((today.year + 1, 1))
    else:
        months.append((today.year, today.month + 1))

    all_results = []
    errors = []

    for year, month in months:

        try:
            results = check_month(year, month)
            all_results.extend(results)

        except Exception as e:
            error_message = f"{year}-{month} 확인 오류: {e}"
            print(error_message)
            errors.append(error_message)

    # 중복 제거
    current_results = set(
        f"{date}|{facility}"
        for date, facility in all_results
    )

    # 홈페이지 확인에 오류가 있으면
    # 잘못된 상태로 기존 기록을 덮어쓰지 않는다.
    if errors:
        print("일부 월 확인에 오류가 있어 예약 상태를 업데이트하지 않습니다.")
        return

    # 이전 상태 불러오기
    previous_results, state_sha = load_previous_state()

    # 새롭게 예약 가능해진 시설만 추출
    newly_available = current_results - previous_results

    if newly_available:

        sorted_results = sorted(newly_available)

        message = "🚨 영월캠프 예약 가능 알림 🚨\n\n"

        for item in sorted_results:

            date, facility = item.split("|", 1)

            message += f"📅 {date} (토)\n"
            message += f"🏕 {facility}\n\n"

        message += "영월캠프 예약 페이지를 확인하세요."

        send_telegram(message)

        print(message)

    else:

        if current_results:
            print("예약 가능한 시설은 있지만 이미 알림을 보낸 상태입니다.")
        else:
            print("현재 예약 가능한 토요일 시설이 없습니다.")

    # 현재 상태 저장
    save_current_state(
        current_results,
        state_sha
    )


if __name__ == "__main__":
    main()
