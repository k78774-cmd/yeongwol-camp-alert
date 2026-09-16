import os
import re
import json
import base64
import requests

from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urlencode


# ============================================================
# 기본 설정
# ============================================================

BASE_URL = (
    "https://www.sd.go.kr/booking/"
    "rcrtfrFcltyResveInfoWebRegistCalendarView.do"
)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY")

STATE_FILE = "alert_state.json"


# ============================================================
# 확인할 시설
#
# Room 1~4
# 글램핑 1~5
# 카라반 1~5
#
# 일반데크는 제외
# ============================================================

FACILITIES = {
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
}


# ============================================================
# Telegram 메시지 보내기
# ============================================================

def send_telegram(message):

    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message
        },
        timeout=30
    )

    response.raise_for_status()


# ============================================================
# 월별 예약 페이지 URL
# ============================================================

def get_month_url(year, month):

    params = {
        "key": "4865",
        "searchMonth": month,
        "searchYear": year,
        "searchSiteId": "100",
        "siteId": "100"
    }

    return BASE_URL + "?" + urlencode(params)


# ============================================================
# 문자열 정리
# ============================================================

def normalize(text):

    return re.sub(
        r"\s+",
        " ",
        text or ""
    ).strip()


# ============================================================
# 토요일인지 확인
# ============================================================

def is_saturday(year, month, day):

    try:
        date_obj = datetime(
            year,
            month,
            day
        )

    except ValueError:
        return False

    # 월요일 = 0
    # 화요일 = 1
    # ...
    # 토요일 = 5
    return date_obj.weekday() == 5


# ============================================================
# 달력 칸에서 날짜 찾기
# ============================================================

def find_day_number(cell):

    # 날짜를 나타내는 숫자를 찾는다.
    text = normalize(
        cell.get_text(
            " ",
            strip=True
        )
    )

    numbers = re.findall(
        r"\b([1-9]|[12][0-9]|3[01])\b",
        text
    )

    if not numbers:
        return None

    return int(numbers[0])


# ============================================================
# 예약 가능 여부 확인
# ============================================================

def facility_is_available(element):

    classes = " ".join(
        element.get(
            "class",
            []
        )
    ).lower()

    aria_disabled = str(
        element.get(
            "aria-disabled",
            ""
        )
    ).lower()

    disabled = str(
        element.get(
            "disabled",
            ""
        )
    ).lower()

    title = str(
        element.get(
            "title",
            ""
        )
    ).lower()

    onclick = str(
        element.get(
            "onclick",
            ""
        )
    ).lower()

    combined = " ".join(
        [
            classes,
            aria_disabled,
            disabled,
            title,
            onclick
        ]
    )

    # --------------------------------------------------------
    # 예약 불가 상태
    # --------------------------------------------------------

    unavailable_patterns = [
        "예약마감",
        "예약 마감",
        "예약불가",
        "예약 불가",
        "예약불가능",
        "예약 불가능",
        "마감",
        "disabled",
        "unavailable",
        "closed"
    ]

    for word in unavailable_patterns:

        if word in combined:
            return False

    # --------------------------------------------------------
    # 명확한 disabled 처리
    # --------------------------------------------------------

    if aria_disabled == "true":
        return False

    if disabled == "true":
        return False

    # --------------------------------------------------------
    # p-on이면 예약 가능
    # --------------------------------------------------------

    if "p-on" in classes:
        return True

    # --------------------------------------------------------
    # onclick이 있으면 예약 가능한 버튼일 가능성이 높음
    # --------------------------------------------------------

    if onclick:
        return True

    return False


# ============================================================
# 특정 월 예약 확인
# ============================================================

def check_month(year, month):

    url = get_month_url(
        year,
        month
    )

    print()
    print("=" * 70)
    print(
        f"{year}-{month:02d} 예약 확인 시작"
    )
    print("=" * 70)

    print(
        f"URL : {url}"
    )

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

    print(
        f"HTTP 상태 : {response.status_code}"
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    results = []

    # ========================================================
    # 실제 달력은 td 단위로 확인
    # ========================================================

    for cell in soup.find_all("td"):

        text = normalize(
            cell.get_text(
                " ",
                strip=True
            )
        )

        # 시설명이 하나라도 들어있는 달력 칸인지 확인
        if not any(
            facility in text
            for facility in FACILITIES
        ):
            continue

        # 날짜 찾기
        day = find_day_number(cell)

        if day is None:
            continue

        # 토요일만 확인
        if not is_saturday(
            year,
            month,
            day
        ):
            continue

        date_string = (
            f"{year:04d}-"
            f"{month:02d}-"
            f"{day:02d}"
        )

        print(
            f"토요일 발견 : {date_string}"
        )

        # ====================================================
        # 핵심
        #
        # 기존 코드는 a 태그만 확인했음.
        #
        # 실제 사이트는 예약 시설을 button으로 표시하기
        # 때문에 button + a 둘 다 확인한다.
        # ====================================================

        elements = cell.find_all(
            ["button", "a"]
        )

        for element in elements:

            facility_name = normalize(
                element.get_text(
                    " ",
                    strip=True
                )
            )

            # 대상 시설이 아니면 무시
            if facility_name not in FACILITIES:
                continue

            # 예약 가능하지 않으면 무시
            if not facility_is_available(
                element
            ):
                continue

            result = (
                date_string,
                facility_name
            )

            if result not in results:

                results.append(result)

                print(
                    f"  [예약 가능] "
                    f"{date_string} "
                    f"{facility_name}"
                )

    # 중복 제거 + 날짜/시설명 정렬
    results = sorted(
        set(results)
    )

    print()
    print(
        f"{year}-{month:02d} "
        f"토요일 예약 가능 시설 : "
        f"{len(results)}개"
    )

    return results


# ============================================================
# GitHub에 저장된 이전 예약 상태 불러오기
# ============================================================

def load_previous_state():

    if not GITHUB_TOKEN:
        print(
            "GITHUB_TOKEN 없음"
        )
        return []

    if not GITHUB_REPOSITORY:
        print(
            "GITHUB_REPOSITORY 없음"
        )
        return []

    url = (
        "https://api.github.com/repos/"
        f"{GITHUB_REPOSITORY}/contents/"
        f"{STATE_FILE}"
    )

    headers = {
        "Authorization":
            f"Bearer {GITHUB_TOKEN}",

        "Accept":
            "application/vnd.github+json"
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30
    )

    # 파일이 아직 없으면 빈 상태
    if response.status_code == 404:
        print(
            "기존 예약 상태 파일 없음"
        )
        return []

    response.raise_for_status()

    data = response.json()

    content = base64.b64decode(
        data["content"]
    ).decode("utf-8")

    try:

        return json.loads(
            content
        )

    except json.JSONDecodeError:

        print(
            "예약 상태 파일 JSON 오류"
        )

        return []


# ============================================================
# 현재 예약 상태를 GitHub에 저장
# ============================================================

def save_current_state(
    current_state
):

    if not GITHUB_TOKEN:
        print(
            "GITHUB_TOKEN 없음 → 상태 저장 생략"
        )
        return

    if not GITHUB_REPOSITORY:
        print(
            "GITHUB_REPOSITORY 없음 → 상태 저장 생략"
        )
        return

    url = (
        "https://api.github.com/repos/"
        f"{GITHUB_REPOSITORY}/contents/"
        f"{STATE_FILE}"
    )

    headers = {
        "Authorization":
            f"Bearer {GITHUB_TOKEN}",

        "Accept":
            "application/vnd.github+json"
    }

    # --------------------------------------------------------
    # 기존 파일 SHA 확인
    # --------------------------------------------------------

    get_response = requests.get(
        url,
        headers=headers,
        timeout=30
    )

    sha = None

    if get_response.status_code == 200:

        sha = get_response.json().get(
            "sha"
        )

    elif get_response.status_code != 404:

        get_response.raise_for_status()

    # --------------------------------------------------------
    # 저장할 내용
    # --------------------------------------------------------

    content = json.dumps(
        sorted(current_state),
        ensure_ascii=False,
        indent=2
    )

    encoded_content = base64.b64encode(
        content.encode("utf-8")
    ).decode("utf-8")

    payload = {
        "message":
            "Update reservation state",

        "content":
            encoded_content
    }

    if sha:

        payload["sha"] = sha

    # --------------------------------------------------------
    # GitHub에 저장
    # --------------------------------------------------------

    response = requests.put(
        url,
        headers=headers,
        json=payload,
        timeout=30
    )

    response.raise_for_status()

    print(
        "GitHub에 예약 상태 저장 완료"
    )


# ============================================================
# 확인할 월
#
# 현재 월 + 다음 월
# ============================================================

def get_target_months():

    now = datetime.now()

    current_year = now.year
    current_month = now.month

    if current_month == 12:

        next_year = (
            current_year + 1
        )

        next_month = 1

    else:

        next_year = current_year
        next_month = (
            current_month + 1
        )

    return [
        (
            current_year,
            current_month
        ),
        (
            next_year,
            next_month
        )
    ]


# ============================================================
# 메인
# ============================================================

def main():

    print()
    print("=" * 70)
    print(
        "영월캠프 예약 알림 프로그램"
    )
    print("=" * 70)

    print(
        "조건 : 토요일만"
    )

    print(
        "대상 : "
        "Room-1 ~ Room-4 / "
        "글램핑-1 ~ 글램핑-5 / "
        "카라반-1 ~ 카라반-5"
    )

    print(
        "제외 : 일반데크"
    )

    print(
        "상태 : 예약 가능한 시설만"
    )

    print(
        "기간 : 현재 월 + 다음 월"
    )

    print("=" * 70)

    # --------------------------------------------------------
    # 확인할 월
    # --------------------------------------------------------

    target_months = get_target_months()

    print(
        f"검사 대상 월 : {target_months}"
    )

    # --------------------------------------------------------
    # 전체 예약 가능 목록
    # --------------------------------------------------------

    all_results = []

    errors = []

    # --------------------------------------------------------
    # 월별 확인
    # --------------------------------------------------------

    for year, month in target_months:

        try:

            results = check_month(
                year,
                month
            )

            all_results.extend(
                results
            )

        except Exception as e:

            errors.append(
                f"{year}-{month:02d}: {e}"
            )

            print(
                f"{year}-{month:02d} "
                f"확인 실패 : {e}"
            )

    # --------------------------------------------------------
    # 하나라도 오류가 있으면
    # 기존 상태를 덮어쓰지 않는다.
    # --------------------------------------------------------

    if errors:

        print()
        print(
            "예약 확인 중 오류가 발생했습니다."
        )

        for error in errors:

            print(
                error
            )

        print(
            "기존 예약 상태는 "
            "그대로 유지합니다."
        )

        return

    # --------------------------------------------------------
    # 현재 상태
    # --------------------------------------------------------

    current_state = sorted(
        set(all_results)
    )

    print()
    print("=" * 70)
    print(
        "현재 예약 가능 상태"
    )
    print("=" * 70)

    if current_state:

        for date_string, facility in current_state:

            print(
                f"{date_string} "
                f"{facility}"
            )

    else:

        print(
            "현재 예약 가능한 시설 없음"
        )

    # --------------------------------------------------------
    # 이전 상태
    # --------------------------------------------------------

    previous_state = (
        load_previous_state()
    )

    previous_set = set(
        tuple(item)
        for item in previous_state
    )

    current_set = set(
        tuple(item)
        for item in current_state
    )

    # --------------------------------------------------------
    # 새롭게 예약 가능해진 시설
    # --------------------------------------------------------

    newly_available = sorted(
        current_set - previous_set
    )

    print()
    print("=" * 70)
    print(
        "새롭게 예약 가능해진 시설"
    )
    print("=" * 70)

    if newly_available:

        for date_string, facility in newly_available:

            print(
                f"{date_string} "
                f"{facility}"
            )

    else:

        print(
            "새롭게 예약 가능해진 시설 없음"
        )

    # --------------------------------------------------------
    # Telegram 알림
    # --------------------------------------------------------

    if newly_available:

        message_lines = [
            "🚨 영월캠프 예약 가능 알림",
            ""
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
            "토요일만 확인"
        )

        message_lines.append(
            "성동힐링센터 휴 영월캠프"
        )

        message = "\n".join(
            message_lines
        )

        try:

            send_telegram(
                message
            )

            print()
            print(
                "Telegram 알림 전송 완료"
            )

        except Exception as e:

            print()
            print(
                f"Telegram 전송 실패 : {e}"
            )

            # Telegram 실패 시에는 상태를
            # 저장하지 않는다.
            # 다음 실행 때 다시 알림을 받을 수 있게 한다.
            return

    else:

        print()
        print(
            "Telegram 알림 없음"
        )

    # --------------------------------------------------------
    # 현재 상태 저장
    # --------------------------------------------------------

    save_current_state(
        current_state
    )

    print()
    print("=" * 70)
    print(
        "예약 확인 완료"
    )
    print("=" * 70)


# ============================================================
# 프로그램 시작
# ============================================================

if __name__ == "__main__":

    main()
