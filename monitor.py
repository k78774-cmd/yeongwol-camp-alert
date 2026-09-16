import re
import requests
from bs4 import BeautifulSoup


# ==========================================
# 기본 설정
# ==========================================

BASE_URL = (
    "https://www.sd.go.kr/booking/"
    "rcrtfrFcltyResveInfoWebRegistCalendarView.do"
)


# 일반데크는 제외
FACILITIES = [
    "룸-1",
    "룸-2",
    "룸-3",
    "룸-4",
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


# ==========================================
# 월별 주소 만들기
# ==========================================

def get_month_url(year, month):
    return (
        f"{BASE_URL}"
        f"?searchMonth={month}"
        f"&searchYear={year}"
        f"&siteId=100"
    )


# ==========================================
# 글자 정리
# ==========================================

def normalize(text):
    if text is None:
        return ""

    text = str(text)

    # 여러 공백을 하나로
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ==========================================
# HTML 진단
# ==========================================

def check_month(year, month):

    url = get_month_url(year, month)

    print("\n")
    print("=" * 70)
    print(f"{year}-{month:02d} HTML 진단 시작")
    print("=" * 70)
    print(f"URL : {url}")

    try:

        response = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/138.0 Safari/537.36"
                )
            },
            timeout=60
        )

        response.raise_for_status()

    except Exception as e:

        print("\n사이트 접속 실패")
        print(f"오류 : {e}")
        return

    print(f"HTTP 상태 : {response.status_code}")
    print(f"실제 접속 URL : {response.url}")
    print(f"HTML 길이 : {len(response.text):,} bytes")
    print(
        f"Content-Type : "
        f"{response.headers.get('Content-Type')}"
    )

    soup = BeautifulSoup(response.text, "html.parser")

    # ==========================================
    # 기본 HTML 정보
    # ==========================================

    print("\n")
    print("=" * 70)
    print("기본 HTML 정보")
    print("=" * 70)

    title = soup.title

    if title:
        print(f"페이지 제목 : {normalize(title.get_text())}")
    else:
        print("페이지 제목 : 없음")

    print(
        f"script 개수 : "
        f"{len(soup.find_all('script'))}"
    )

    print(
        f"table 개수 : "
        f"{len(soup.find_all('table'))}"
    )

    print(
        f"a 태그 개수 : "
        f"{len(soup.find_all('a'))}"
    )


    # ==========================================
    # 1차 진단
    # 시설명이 HTML 원본에 존재하는지 확인
    # ==========================================

    print("\n")
    print("=" * 70)
    print("1차 진단 : HTML 원본에서 시설명 찾기")
    print("=" * 70)

    raw_html = response.text

    raw_found = 0

    for facility in FACILITIES:

        positions = [
            m.start()
            for m in re.finditer(
                re.escape(facility),
                raw_html,
                re.IGNORECASE
            )
        ]

        print(
            f"{facility:10s} : "
            f"{len(positions)}회"
        )

        if positions:

            raw_found += len(positions)

            # 처음 발견된 위치 주변 HTML 출력
            for index, pos in enumerate(positions[:2]):

                print("\n----------------------------------------")
                print(
                    f"{facility} "
                    f"→ 발견 위치 {index + 1}"
                )
                print("----------------------------------------")

                start = max(0, pos - 1000)
                end = min(
                    len(raw_html),
                    pos + 2500
                )

                snippet = raw_html[start:end]

                print(snippet)


    # ==========================================
    # 2차 진단
    # BeautifulSoup으로 시설명 태그 찾기
    # ==========================================

    print("\n")
    print("=" * 70)
    print("2차 진단 : BeautifulSoup 시설명 태그 찾기")
    print("=" * 70)

    found = 0

    for facility in FACILITIES:

        print("\n")
        print(f"### 시설 : {facility}")

        elements = soup.find_all(
            lambda tag: (
                tag.name in [
                    "a",
                    "td",
                    "li",
                    "span",
                    "div"
                ]
                and facility in normalize(
                    tag.get_text(
                        " ",
                        strip=True
                    )
                )
            )
        )

        if not elements:

            print(
                "→ 해당 시설명을 포함한 "
                "태그를 찾지 못함"
            )

            continue

        print(
            f"→ 총 {len(elements)}개 태그 발견"
        )

        printed = 0

        for element in elements:

            text = normalize(
                element.get_text(
                    " ",
                    strip=True
                )
            )

            # 너무 큰 부모 태그는 제외
            if len(text) > 500:
                continue

            print("\n")
            print("-" * 50)

            print(f"시설명 : {facility}")
            print(f"태그   : {element.name}")
            print(
                f"class  : "
                f"{element.get('class')}"
            )
            print(
                f"id     : "
                f"{element.get('id')}"
            )
            print(
                f"href   : "
                f"{element.get('href')}"
            )
            print(
                f"onclick: "
                f"{element.get('onclick')}"
            )

            # data-* 속성
            data_attrs = {
                k: v
                for k, v in element.attrs.items()
                if str(k).startswith("data-")
            }

            print(
                f"data   : "
                f"{data_attrs}"
            )

            print("\n[태그 안의 문자]")
            print(text[:500])

            # 부모 태그
            parent = element.parent

            if parent:

                print("\n[부모 태그]")

                print(
                    f"태그   : "
                    f"{parent.name}"
                )

                print(
                    f"class  : "
                    f"{parent.get('class')}"
                )

                print(
                    f"id     : "
                    f"{parent.get('id')}"
                )

                print(
                    f"href   : "
                    f"{parent.get('href')}"
                )

                print(
                    f"onclick: "
                    f"{parent.get('onclick')}"
                )

                parent_data = {
                    k: v
                    for k, v in parent.attrs.items()
                    if str(k).startswith("data-")
                }

                print(
                    f"data   : "
                    f"{parent_data}"
                )

            # 실제 HTML
            print("\n[HTML 원본]")
            print(
                str(element)[:3000]
            )

            found += 1
            printed += 1

            if printed >= 3:

                print(
                    "\n→ 같은 시설은 "
                    "3개까지만 표시"
                )

                break


    # ==========================================
    # 3차 진단
    # 예약 관련 단어가 HTML에 있는지 확인
    # ==========================================

    print("\n")
    print("=" * 70)
    print("3차 진단 : 예약 관련 단어 검색")
    print("=" * 70)

    keywords = [
        "예약가능",
        "예약불가",
        "예약",
        "가능",
        "불가",
        "마감",
        "booking",
        "reserve",
        "available",
        "disabled"
    ]

    lower_html = raw_html.lower()

    for keyword in keywords:

        count = lower_html.count(
            keyword.lower()
        )

        print(
            f"{keyword:12s} : "
            f"{count}회"
        )


    # ==========================================
    # 최종 결과
    # ==========================================

    print("\n")
    print("=" * 70)
    print("진단 결과")
    print("=" * 70)

    print(
        f"시설명 HTML 원본 발견 횟수 : "
        f"{raw_found}"
    )

    print(
        f"BeautifulSoup 확인 요소 : "
        f"{found}"
    )

    if raw_found == 0:

        print("\n")
        print(
            "★ 중요 ★"
        )

        print(
            "HTML 원본에 시설명이 없습니다."
        )

        print(
            "→ 자바스크립트로 별도 데이터를 "
            "불러오는 방식일 가능성이 있습니다."
        )

    elif found == 0:

        print("\n")
        print(
            "★ 중요 ★"
        )

        print(
            "HTML 원본에는 시설명이 있지만 "
            "일반적인 태그 구조로 찾지 못했습니다."
        )

        print(
            "→ 위의 HTML 원본 내용을 확인해야 합니다."
        )

    else:

        print("\n")
        print(
            "시설명 HTML 구조를 확인했습니다."
        )

        print(
            "→ 위에 출력된 HTML을 이용해서 "
            "예약 가능 여부를 판별할 수 있습니다."
        )

    print("\n")
    print("=" * 70)
    print(
        f"{year}-{month:02d} "
        "HTML 진단 종료"
    )
    print("=" * 70)


# ==========================================
# 실행
# ==========================================

if __name__ == "__main__":

    check_month(2026, 9)

    check_month(2026, 10)
