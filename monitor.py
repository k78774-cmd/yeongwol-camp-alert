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
# 진단용 설정
#
# True이면 평일에도 시설 상태를 일부 출력한다.
# Telegram 알림은 여전히 토요일만 한다.
# ============================================================

DEBUG_WEEKDAY = True


# ============================================================
# HTTP 기본 헤더
#
# 캐시 방지를 위해 no-cache 추가
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/138.0 Safari/537.36"
    ),
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
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
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()


# ============================================================
# 월별 예약 페이지 URL
#
# cachebuster를 추가해서 이전 페이지가 남지 않도록 한다.
# ============================================================

def get_month_url(year, month):

    cachebuster = str(int(datetime.now().timestamp() * 1000))

    params = {
        "key": "4865",
        "searchMonth": month,
        "searchYear": year,
        "searchSiteId": "100",
        "siteId": "100",
        "_cache": cachebuster,
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
    # 수요일 = 2
    # 목요일 = 3
    # 금요일 = 4
    # 토요일 = 5
    # 일요일 = 6

    return date_obj.weekday() == 5


# ============================================================
# 날짜 찾기
# ============================================================

def find_day_number(cell):

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
# 시설명 정리
#
# 사이트에서 줄바꿈이나 공백이 들어오는 경우를 대비한다.
# ============================================================

def normalize_facility_name(text):

    text = normalize(text)

    # 공백 제거
    text_no_space = text.replace(" ", "")

    # 정확한 시설명 찾기
    for facility in FACILITIES:

        if text == facility:
            return facility

        if text_no_space == facility.replace(" ", ""):
            return facility

    return None


# ============================================================
# HTML 요소의 상태를 사람이 보기 좋게 설명
# ============================================================

def get_element_status(element):

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
    )

    onclick = str(
        element.get(
            "onclick",
            ""
        )
    )

    element_text = normalize(
        element.get_text(
            " ",
            strip=True
        )
    )

    return {
        "classes": classes,
        "aria_disabled": aria_disabled,
        "disabled": disabled,
        "title": title,
        "onclick": onclick,
        "text": element_text,
    }


# ============================================================
# 예약 가능 여부 확인
#
# 기존의 p-on만 보는 방식에서 확장
# ============================================================

def facility_is_available(element):

    info = get_element_status(element)

    classes = info["classes"]
    aria_disabled = info["aria_disabled"]
    disabled = info["disabled"]
    title = info["title"].lower()
    onclick = info["onclick"].lower()
    element_text = info["text"].lower()

    combined = " ".join(
        [
            classes,
            aria_disabled,
            disabled,
            title,
            onclick,
            element_text
        ]
    )

    # --------------------------------------------------------
    # 명확한 예약 불가 상태
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
        "closed",
    ]

    for word in unavailable_patterns:

        if word in combined:
            return False

    # --------------------------------------------------------
    # disabled 속성
    # --------------------------------------------------------

    if aria_disabled == "true":
        return False

    if disabled == "true":
        return False

    # --------------------------------------------------------
    # 예약 가능 표시
    #
    # 현재 확인된 사이트 구조에서 p-on을 우선 인정
    # --------------------------------------------------------

    if "p-on" in classes:
        return True

    # --------------------------------------------------------
    # onclick이 실제 예약 동작을 가지고 있으면
    # 예약 가능한 시설일 가능성이 높다.
    # --------------------------------------------------------

    if onclick:
        return True

    return False


# ============================================================
# 요소 상태를 출력
#
# 문제 발생 시 실제 HTML 상태를 확인하기 위한 진단
# ============================================================

def print_debug_element(
    date_string,
    facility_name,
    element
):

    info = get_element_status(element)

    print(
        "    [진단] "
        f"{date_string} "
        f"{facility_name} "
        f"| class={info['classes']} "
        f"| disabled={info['disabled']} "
        f"| aria-disabled={info['aria_disabled']} "
        f"| title={info['title']} "
        f"| onclick={'있음' if info['onclick'] else '없음'}"
    )


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

    # --------------------------------------------------------
    # 홈페이지 요청
    # --------------------------------------------------------

    response = requests.get(
    url,
    headers=HEADERS,
    timeout=60,
    verify=False
    )

    print(
        f"HTTP 상태 : {response.status_code}"
    )

    response.raise_for_status()

    # --------------------------------------------------------
    # HTML 분석
    # --------------------------------------------------------

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    results = []

    # 진단용
    weekday_available_count = 0

    saturday_count = 0

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

        # ----------------------------------------------------
        # 시설명이 하나라도 들어있는 달력 칸인지 확인
        # ----------------------------------------------------

        if not any(
            facility in text
            for facility in FACILITIES
        ):
            continue

        # ----------------------------------------------------
        # 날짜 찾기
        # ----------------------------------------------------

        day = find_day_number(cell)

        if day is None:
            continue

        date_string = (
            f"{year:04d}-"
            f"{month:02d}-"
            f"{day:02d}"
        )

        saturday = is_saturday(
            year,
            month,
            day
        )

        if saturday:

            saturday_count += 1

            print()
            print(
                f"토요일 발견 : {date_string}"
            )

        # ----------------------------------------------------
        # 시설 버튼/링크 확인
        # ----------------------------------------------------

        elements = cell.find_all(
            ["button", "a"]
        )

        cell_available = []

        for element in elements:

            facility_name = normalize_facility_name(
                element.get_text(
                    " ",
                    strip=True
                )
            )

            # 대상 시설이 아니면 무시
            if facility_name is None:
                continue

            available = facility_is_available(
                element
            )

            # ------------------------------------------------
            # 평일 진단
            #
            # 평일에도 실제 예약 가능한 시설이 있는지 확인
            # ------------------------------------------------

            if not saturday and DEBUG_WEEKDAY:

                if available:

                    weekday_available_count += 1

                    print_debug_element(
                        date_string,
                        facility_name,
                        element
                    )

            # ------------------------------------------------
            # 토요일
            # ------------------------------------------------

            if saturday:

                # 상태 진단
                print_debug_element(
                    date_string,
                    facility_name,
                    element
                )

                if available:

                    result = (
                        date_string,
                        facility_name
                    )

                    if result not in cell_available:

                        cell_available.append(
                            result
                        )

        # ----------------------------------------------------
        # 토요일 예약 가능 시설 추가
        # ----------------------------------------------------

        if saturday:

            for result in cell_available:

                if result not in results:

                    results.append(result)

                    print(
                        f"  [예약 가능] "
                        f"{result[0]} "
                        f"{result[1]}"
                    )

    # ========================================================
    # 월별 결과
    # ========================================================

    results = sorted(
        set(results)
    )

    print()
    print(
        f"{year}-{month:02d} "
        f"토요일 수 : {saturday_count}개"
    )

    if DEBUG_WEEKDAY:

        print(
            f"{year}-{month:02d} "
            f"평일에서 발견한 예약 가능 시설 요소 : "
            f"{weekday_available_count}개"
        )

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
        "조건 : 토요일만 Telegram 알림"
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
        "상태 : 예약 가능한 시설"
    )

    print(
        "기간 : 현재 월 + 다음 월"
    )

    print(
        "평일 : 상태 진단만 실시"
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
        "현재 토요일 예약 가능 상태"
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
            "현재 토요일 예약 가능한 시설 없음"
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

    # ========================================================
    # 핵심
    #
    # 이전에는 없었고
    # 지금은 있으면 신규 예약 가능
    #
    # 예약가능 → 예약불가 → 예약가능
    # 이 경우에도 다시 알림
    # ========================================================

    newly_available = sorted(
        current_set - previous_set
    )

    # ========================================================
    # 결과 출력
    # ========================================================

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

    # ========================================================
    # Telegram 알림
    # ========================================================

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
            "토요일만 알림"
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

            # ------------------------------------------------
            # Telegram 실패 시 상태를 저장하지 않는다.
            # 다음 실행 때 다시 알림을 받을 수 있게 한다.
            # ------------------------------------------------

            return

    else:

        print()
        print(
            "Telegram 알림 없음"
        )

    # --------------------------------------------------------
    # 현재 상태 저장
    #
    # 알림 성공 후 저장
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
