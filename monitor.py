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
# 감시 대상
# ============================================================

# 영월캠프 Room만 감시
# 글램핑 / 카라반 / 일반데크는 모두 제외
ROOMS = {
    "Room-1",
    "Room-2",
    "Room-3",
    "Room-4",
}


# ============================================================
# Telegram
# ============================================================

def send_telegram(message):
    url = (
        f"https://api.telegram.org/bot"
        f"{BOT_TOKEN}/sendMessage"
    )

    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message,
        },
        timeout=30,
    )

    response.raise_for_status()

    print("Telegram 알림 전송 완료")


# ============================================================
# 월별 예약 페이지 URL
# ============================================================

def get_month_url(year, month):
    params = {
        "key": "4865",
        "searchMonth": month,
        "searchYear": year,
        "searchSiteId": "100",
        "siteId": "100",
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
# 토요일 확인
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

    # Python:
    # 월요일=0
    # ...
    # 토요일=5
    # 일요일=6
    return date_obj.weekday() == 5


# ============================================================
# 현재 월 + 다음 월
# ============================================================

def get_target_months():

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
        (next_year, next_month),
    ]


# ============================================================
# 날짜 찾기
# ============================================================

def find_day_number(cell):
    """
    성동구 달력의 날짜 칸에서
    <span class="day">숫자</span>를 찾는다.

    시설명에 들어가는 Room-1 등의 숫자와
    날짜 숫자가 섞이는 문제를 방지하기 위해
    class="day"를 우선 사용한다.
    """

    day_tag = cell.find(
        class_=lambda value: (
            value
            and "day" in value
        )
    )

    if day_tag:
        text = normalize(
            day_tag.get_text(
                " ",
                strip=True
            )
        )

        if text.isdigit():
            day = int(text)

            if 1 <= day <= 31:
                return day

    return None


# ============================================================
# Room 버튼의 예약 가능 여부
# ============================================================

def is_room_available(element):
    """
    성동구 예약 페이지에서

    p-on  = 예약 가능
    p-off = 예약 마감

    으로 처리한다.

    반드시 p-on이 있어야 예약 가능으로 판단한다.
    """

    classes = element.get(
        "class",
        []
    )

    classes = {
        str(item).lower()
        for item in classes
    }

    # p-on이 없으면 예약 가능으로 판단하지 않는다.
    if "p-on" not in classes:
        return False

    # p-off가 동시에 있으면 안전하게 제외
    if "p-off" in classes:
        return False

    # disabled가 있으면 제외
    if element.has_attr("disabled"):
        return False

    aria_disabled = str(
        element.get(
            "aria-disabled",
            ""
        )
    ).lower()

    if aria_disabled == "true":
        return False

    return True


# ============================================================
# 한 달 검사
# ============================================================

def check_month(year, month):

    url = get_month_url(
        year,
        month
    )

    print("")
    print("=" * 70)
    print(
        f"{year}-{month:02d} 예약 확인 시작"
    )
    print("=" * 70)

    print(f"URL : {url}")

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
        timeout=60,
    )

    response.raise_for_status()

    print(
        f"HTTP 상태 : {response.status_code}"
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    results = []

    # --------------------------------------------------------
    # 핵심:
    # 달력의 td 단위로 확인
    # --------------------------------------------------------

    for cell in soup.find_all("td"):

        day = find_day_number(cell)

        if day is None:
            continue

        # 토요일만 검사
        if not is_saturday(
            year,
            month,
            day
        ):
            continue

        print(
            f"\n토요일 발견 : "
            f"{year}-{month:02d}-{day:02d}"
        )

        # ----------------------------------------------------
        # Room 버튼 찾기
        #
        # 실제 페이지에서는 button 태그에
        # p-on / p-off가 붙어 있음
        # ----------------------------------------------------

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

            # Room-1 ~ Room-4만 검사
            if facility_name not in ROOMS:
                continue

            # p-on인지 확인
            if not is_room_available(
                element
            ):
                continue

            date_string = (
                f"{year:04d}-"
                f"{month:02d}-"
                f"{day:02d}"
            )

            item = (
                date_string,
                facility_name
            )

            results.append(item)

            print(
                f"  [예약 가능] "
                f"{date_string} "
                f"{facility_name}"
            )

    # 중복 제거
    results = sorted(
        set(results)
    )

    print("")
    print(
        f"{year}-{month:02d} "
        f"토요일 예약 가능 Room : "
        f"{len(results)}개"
    )

    return results


# ============================================================
# GitHub에 저장된 이전 상태 읽기
# ============================================================

def load_previous_state():

    if (
        not GITHUB_TOKEN
        or not GITHUB_REPOSITORY
    ):
        print(
            "GitHub 상태 저장 기능을 "
            "사용하지 않습니다."
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
            "application/vnd.github+json",
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30,
    )

    # 아직 파일이 없으면 빈 상태
    if response.status_code == 404:
        print(
            "기존 alert_state.json이 없습니다."
        )

        return []

    response.raise_for_status()

    data = response.json()

    content = base64.b64decode(
        data["content"]
    ).decode("utf-8")

    try:
        state = json.loads(
            content
        )

        if not isinstance(
            state,
            list
        ):
            return []

        return state

    except json.JSONDecodeError:

        print(
            "기존 상태 파일을 읽을 수 없습니다."
        )

        return []


# ============================================================
# GitHub에 현재 상태 저장
# ============================================================

def save_current_state(
    current_state
):

    if (
        not GITHUB_TOKEN
        or not GITHUB_REPOSITORY
    ):
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
            "application/vnd.github+json",
    }

    # 기존 파일의 SHA 확인
    get_response = requests.get(
        url,
        headers=headers,
        timeout=30,
    )

    sha = None

    if get_response.status_code == 200:

        sha = get_response.json().get(
            "sha"
        )

    elif get_response.status_code != 404:

        get_response.raise_for_status()

    content = json.dumps(
        sorted(current_state),
        ensure_ascii=False,
        indent=2,
    )

    encoded_content = (
        base64.b64encode(
            content.encode("utf-8")
        )
        .decode("utf-8")
    )

    payload = {
        "message":
            "Update reservation state",

        "content":
            encoded_content,
    }

    # 기존 파일이면 SHA 필요
    if sha:
        payload["sha"] = sha

    response = requests.put(
        url,
        headers=headers,
        json=payload,
        timeout=30,
    )

    response.raise_for_status()

    print(
        "GitHub에 예약 상태 저장 완료"
    )


# ============================================================
# 메인
# ============================================================

def main():

    print("")
    print("=" * 70)
    print("영월캠프 예약 알림 프로그램")
    print("=" * 70)
    print("조건 : 토요일만")
    print("대상 : Room-1 ~ Room-4")
    print("상태 : p-on만 예약 가능")
    print("기간 : 현재 월 + 다음 월")
    print("=" * 70)

    all_results = []

    errors = []

    # --------------------------------------------------------
    # 현재 월 + 다음 월 검사
    # --------------------------------------------------------

    target_months = get_target_months()

    print("")
    print(
        f"검사 대상 월 : "
        f"{target_months}"
    )

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

            error_message = (
                f"{year}-{month:02d}: "
                f"{e}"
            )

            errors.append(
                error_message
            )

            print(
                f"확인 실패 : "
                f"{error_message}"
            )

    # --------------------------------------------------------
    # 한 달이라도 오류가 있으면
    # 기존 상태를 덮어쓰지 않는다.
    #
    # 이게 중요하다.
    # 사이트 오류 때문에 빈 상태로 저장하면
    # 다음 실행 때 같은 방을 다시 알릴 수 있기 때문.
    # --------------------------------------------------------

    if errors:

        print("")
        print(
            "예약 확인 중 오류가 발생했습니다."
        )

        for error in errors:
            print(error)

        print(
            "기존 GitHub 상태는 유지합니다."
        )

        return

    # --------------------------------------------------------
    # 현재 예약 가능 상태
    # --------------------------------------------------------

    current_state = sorted(
        set(all_results)
    )

    print("")
    print("=" * 70)
    print("현재 예약 가능 상태")
    print("=" * 70)

    if current_state:

        for date_string, room in current_state:

            print(
                f"{date_string} "
                f"{room}"
            )

    else:

        print(
            "현재 예약 가능한 Room이 없습니다."
        )

    # --------------------------------------------------------
    # 이전 상태
    # --------------------------------------------------------

    previous_state = (
        load_previous_state()
    )

    previous_set = {
        tuple(item)
        for item in previous_state
    }

    current_set = {
        tuple(item)
        for item in current_state
    }

    # --------------------------------------------------------
    # 새롭게 예약 가능해진 것만 찾기
    # --------------------------------------------------------

    newly_available = sorted(
        current_set - previous_set
    )

    print("")
    print("=" * 70)
    print("새롭게 예약 가능해진 Room")
    print("=" * 70)

    if newly_available:

        for date_string, room in newly_available:

            print(
                f"{date_string} "
                f"{room}"
            )

    else:

        print(
            "새롭게 예약 가능해진 Room이 없습니다."
        )

    # --------------------------------------------------------
    # Telegram 알림
    # --------------------------------------------------------

    if newly_available:

        message_lines = [
            "🚨 영월캠프 예약 가능 알림",
            "",
        ]

        for date_string, room in newly_available:

            message_lines.append(
                f"📅 {date_string}"
            )

            message_lines.append(
                f"🏕️ {room}"
            )

            message_lines.append("")

        message_lines.append(
            "※ 토요일만 확인"
        )

        message_lines.append(
            "성동구 영월캠프"
        )

        message = "\n".join(
            message_lines
        )

        send_telegram(
            message
        )

        print("")
        print(
            f"Telegram 알림 : "
            f"{len(newly_available)}건"
        )

    else:

        print("")
        print(
            "Telegram 알림 없음"
        )

    # --------------------------------------------------------
    # 현재 상태 저장
    # --------------------------------------------------------

    save_current_state(
        current_state
    )

    print("")
    print("=" * 70)
    print("예약 확인 완료")
    print("=" * 70)


# ============================================================
# 실행
# ============================================================

if __name__ == "__main__":
    main()
