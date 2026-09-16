def check_month(year, month):
    url = get_month_url(year, month)

    print(f"\n========== {year}-{month:02d} HTML 진단 시작 ==========")
    print(f"URL : {url}")

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

    print(f"HTTP 상태 : {response.status_code}")
    print(f"HTML 길이 : {len(response.text):,} bytes")

    soup = BeautifulSoup(response.text, "html.parser")

    print("\n========== 시설명 검색 ==========\n")

    found = 0

    for facility in FACILITIES:

        print(f"\n### 시설 : {facility}")

        # 시설명이 들어간 태그를 '부분 포함'으로 검색
        elements = soup.find_all(
            lambda tag: (
                tag.name in ["a", "td", "li", "span", "div"]
                and facility in normalize(tag.get_text(" ", strip=True))
            )
        )

        if not elements:
            print("→ 해당 시설명을 포함한 태그를 찾지 못함")
            continue

        # 너무 많은 중복 태그 제거
        printed = 0

        for element in elements:

            # 부모 태그에도 같은 내용이 반복되므로
            # 실제로 시설명이 들어있는 비교적 작은 태그만 우선 확인
            text = normalize(element.get_text(" ", strip=True))

            if len(text) > 500:
                continue

            print("\n----------------------------------------")
            print(f"시설명 : {facility}")
            print(f"태그   : {element.name}")
            print(f"class  : {element.get('class')}")
            print(f"id     : {element.get('id')}")
            print(f"href   : {element.get('href')}")
            print(f"onclick: {element.get('onclick')}")

            data_attrs = {
                k: v
                for k, v in element.attrs.items()
                if str(k).startswith("data-")
            }

            print(f"data   : {data_attrs}")

            print("\n[태그 안의文字]")
            print(text[:500])

            # 바로 위 부모
            parent = element.parent

            if parent:

                print("\n[부모 태그]")
                print(f"태그   : {parent.name}")
                print(f"class  : {parent.get('class')}")
                print(f"id     : {parent.get('id')}")
                print(f"href   : {parent.get('href')}")
                print(f"onclick: {parent.get('onclick')}")

                parent_data = {
                    k: v
                    for k, v in parent.attrs.items()
                    if str(k).startswith("data-")
                }

                print(f"data   : {parent_data}")

            # 가장 중요한 부분
            # 시설명이 들어있는 실제 HTML을 그대로 출력
            print("\n[HTML 원본]")
            print(str(element)[:3000])

            found += 1
            printed += 1

            # 같은 시설에 대한 중복 출력 방지
            if printed >= 3:
                print("\n→ 같은 시설은 3개까지만 표시")
                break

    print("\n========================================")
    print(f"총 확인된 HTML 요소 : {found}개")
    print("========================================\n")

    # 진단용이므로 예약 상태를 변경하지 않음
    return []
if __name__ == "__main__":
    check_month(2026, 9)
    check_month(2026, 10)
