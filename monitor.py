import os
import re
import json
import base64
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urlencode, urljoin


BASE_URL = "https://www.sd.go.kr/booking/rcrtfrFcltyResveInfoWebRegistCalendarView.do"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY")

STATE_FILE = "alert_state.json"

# 일반데크는 제외
FACILITIES = [
    "Room-1",
    "Room-2",
    "Room-3",
    "Room-4",
    "글램핑-1",
    "글램핑-2",
    "글램핑-3",
    "글램핑-4",
    "글램핑-5",
    "카라반-1",
    "카라반-2",
    "카라반-3",
    "카라반-4",
    "카라반-5",
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


def normalize(text):
    return re.sub(r"\s+", " ", text or "").strip()


def is_saturday(year, month, day):
    try:
        date_obj = datetime(year, month, day)
    except ValueError:
        return False

    return date_obj.weekday() == 5


def find_day_number(cell):
    """
    해당 달력 칸에서 날짜 숫자를 찾는다.
    시설명에 들어 있는 숫자와 날짜를 혼동하지 않도록
    첫 번째 순수 숫자를 우선적으로 사용한다.
    """

    # td/div 내부의 직접적인 텍스트를 우선 확인
    text = normalize(cell.get_text(" ", strip=True))

    # 날짜는 1~31 사이의 숫자
    numbers = re.findall(r"\b([1-9]|[12][0-9]|3[01])\b", text)

    if not numbers:
        return None

    return int(numbers[0])


def facility_is_available(link):
    """
    성동구 예약 페이지의 링크 상태를 최대한 보수적으로 판별한다.

    기존 코드처럼 'not' 같은 일반 단어를 이용하지 않는다.
    """

    classes = " ".join(link.get("class", []))
    classes_lower = classes.lower()

    aria_disabled = str(
        link.get("aria-disabled", "")
    ).lower()

    disabled = str(
        link.get("disabled", "")
    ).lower()

    href = str(
        link.get("href", "")
    ).strip()

    onclick = str(
        link.get("onclick", "")
    ).lower()

    data_values = " ".join(
        [
            str(v).lower()
            for k, v in link.attrs.items()
            if str(k).startswith("data-")
        ]
    )

    combined = " ".join(
        [
            classes_lower,
            aria_disabled,
            disabled,
            href.lower(),
            onclick,
            data_values,
        ]
    )

    # 명확하게 예약불가를 나타내는 표현만 제외
    unavailable_patterns = [
        "예약불가",
        "예약 불가",
        "예약불가능",
        "예약 불가능",
        "마감",
        "불가",
        "disabled",
        "unavailable",
        "closed",
    ]

    for word in unavailable_patterns:
        if word in combined:
            return False

    # aria-disabled="true"
    if aria_disabled == "true":
        return False

    # disabled="true"
    if disabled == "true":
        return False

    # href 자체가 없으면 클릭 가능한 예약 항목으로 보기 어렵다.
    if not href and not onclick:
        return False

    return True


def check_month(year, month):
    url = get_month_url(year, month)

    response = requests.get(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/138.0 Safari/537.36"
            )
        },
        timeout=60
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    results = []

    # 달력의 각 칸을 확인
    for cell in soup.find_all(["td", "div"]):

        text = normalize(cell.get_text(" ", strip=True))

        # 시설명이 하나도 없으면 무시
        if not any(
            facility in text
            for facility in FACILITIES
        ):
            continue

        day = find_day_number(cell)

        if day is None:
            continue

        # 토요일만
        if not is_saturday(year, month, day):
            continue

        # 해당 날짜 칸 안의 링크 확인
        for link in cell.find_all("a"):

            facility_name = normalize(
                link.get_text(" ", strip=True)
            )

            if facility_name not in FACILITIES:
                continue

            if not facility_is_available(link):
                continue

            date_string = (
                f"{year:04d}-{month:02d}-{day:02d}"
            )

            results.append(
                (
                    date_string,
                    facility_name
                )
            )

    # 중복 제거
    results = sorted(set(results))

    return results


def load_previous_state():
    """
    GitHub에 저장된 alert_state.json을 읽는다.
    """

    if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
        return []

    url = (
        "https://api.github.com/repos/"
        f"{GITHUB_REPOSITORY}/contents/{STATE_FILE}"
    )

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30
    )

    if response.status_code == 404:
        return []

    response.raise_for_status()

    data = response.json()

    content = base64.b64decode(
        data["content"]
    ).decode("utf-8")

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return []


def save_current_state(current_state):
    """
    현재 예약 상태를 GitHub의 alert_state.json에 저장한다.
    """

    if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
        return

    url = (
        "https://api.github.com/repos/"
        f"{GITHUB_REPOSITORY}/contents/{STATE_FILE}"
    )

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    # 기존 파일 SHA 확인
    get_response = requests.get(
        url,
        headers=headers,
        timeout=30
    )

    sha = None

    if get_response.status_code == 200:
        sha = get_response.json().get("sha")
    elif get_response.status_code != 404:
        get_response.raise_for_status()

    content = json.dumps(
        sorted(current_state),
        ensure_ascii=False,
        indent=2
    )

    encoded_content = base64.b64encode(
        content.encode("utf-8")
    ).decode("utf-8")

    payload = {
        "message": "Update reservation state",
        "content": encoded_content
    }

    if sha:
        payload["sha"] = sha

    response = requests.put(
        url,
        headers=headers,
        json=payload,
        timeout=30
    )

    response.raise_for_status()


def get_target_months():
    """
    현재 월 + 다음 월
    """

    now = datetime.now()

    current_year = now.year
    current_month = now.month

    if current_month == 12:
        next_year = current_year + 1
        next_month = 1
    else:
        next_year = current_year
        next_month = current_month + 1

    return [
        (current_year, current_month),
        (next_year, next_month)
    ]


def main():

    all_results = []

    errors = []

    for year, month in get_target_months():

        try:

            results = check_month(
                year,
                month
            )

            all_results.extend(results)

            print(
                f"{year}-{month:02d}: "
                f"{len(results)}개 예약가능 항목 확인"
            )

            for date_string, facility in results:
                print(
                    f"  {date_string} "
                    f"{facility}"
                )

        except Exception as e:

            errors.append(
                f"{year}-{month:02d}: {e}"
            )

            print(
                f"{year}-{month:02d} 확인 실패: {e}"
            )

    # 하나라도 조회에 실패하면 기존 상태를 덮어쓰지 않는다.
    if errors:

        print("예약 확인 중 오류가 발생했습니다.")

        for error in errors:
            print(error)

        return

    current_state = sorted(
        set(all_results)
    )

    previous_state = load_previous_state()

    previous_set = set(
        tuple(item)
        for item in previous_state
    )

    current_set = set(
        tuple(item)
        for item in current_state
    )

    # 새롭게 생긴 예약 가능 시설만 추출
    newly_available = sorted(
        current_set - previous_set
    )

    if newly_available:

        message_lines = [
            "🚨 영월캠프 예약 가능 알림",
            "",
        ]

        for date_string, facility in newly_available:

            message_lines.append(
                f"📅 {date_string}"
            )

            message_lines.append(
                f"🏕️ {facility}"
            )

            message_lines.append("")

        message_lines.append(
            "성동힐링센터 휴 영월캠프"
        )

        send_telegram(
            "\n".join(message_lines)
        )

        print(
            f"새로운 예약 가능 시설 "
            f"{len(newly_available)}개 → Telegram 전송"
        )

    else:

        print(
            "새롭게 발생한 예약 가능 시설이 없습니다."
        )

    save_current_state(
        current_state
    )

    print(
        "예약 상태를 GitHub에 저장했습니다."
    )


if __name__ == "__main__":
    main()
