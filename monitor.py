import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urlencode

BASE_URL = "https://www.sd.go.kr/booking/rcrtfrFcltyResveInfoWebRegistCalendarView.do"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

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

    # 달력의 모든 날짜 영역을 찾음
    for cell in soup.find_all(["td", "div"]):

        text = cell.get_text(" ", strip=True)

        # 시설명이 하나라도 없으면 건너뜀
        if not any(facility in text for facility in FACILITIES):
            continue

        # 날짜 찾기
        date_match = re.search(r"(^|\s)([1-9]|[12][0-9]|3[01])(\s|$)", text)

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

        # 해당 날짜 영역 안의 시설 링크 확인
        for link in cell.find_all("a"):

            facility_name = link.get_text(" ", strip=True)

            if facility_name not in FACILITIES:
                continue

            link_class = " ".join(link.get("class", []))
            link_text = link.get_text(" ", strip=True)

            # 예약불가 표시로 판단되는 경우 제외
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

    for year, month in months:
        try:
            results = check_month(year, month)
            all_results.extend(results)

        except Exception as e:
            print(f"{year}-{month} 확인 오류: {e}")

    if all_results:

        message = "🚨 영월캠프 예약 가능 알림 🚨\n\n"

        for date, facility in all_results:
            message += f"📅 {date} (토)\n"
            message += f"🏕 {facility}\n\n"

        message += "영월캠프 예약 페이지를 확인하세요."

        send_telegram(message)

        print(message)

    else:
        print("현재 예약 가능한 토요일 시설이 없습니다.")


if __name__ == "__main__":
    main()
