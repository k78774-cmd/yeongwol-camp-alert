def check_month(year, month):
    url = get_month_url(year, month)

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

    soup = BeautifulSoup(response.text, "html.parser")

    print(f"\n========== {year}-{month:02d} HTML 진단 ==========\n")

    found = 0

    # 시설명이 들어 있는 모든 태그를 찾는다.
    for facility in FACILITIES:

        tags = soup.find_all(
            string=lambda s: s and normalize(s) == facility
        )

        for text_node in tags:

            found += 1

            element = text_node.parent

            print("\n----------------------------------------")
            print(f"시설명 : {facility}")
            print(f"태그   : {element.name}")
            print(f"class  : {element.get('class')}")
            print(f"href   : {element.get('href')}")
            print(f"onclick: {element.get('onclick')}")
            print(f"data   : { {k: v for k, v in element.attrs.items() if str(k).startswith('data-')} }")

            # 바로 위 부모
            parent = element.parent

            if parent:
                print("\n[부모 태그]")
                print(f"태그   : {parent.name}")
                print(f"class  : {parent.get('class')}")
                print(f"href   : {parent.get('href')}")
                print(f"onclick: {parent.get('onclick')}")
                print(
                    f"data   : "
                    f"{ {k: v for k, v in parent.attrs.items() if str(k).startswith('data-')} }"
                )

            # 위로 최대 3단계까지 확인
            ancestor = element

            for level in range(1, 4):

                ancestor = ancestor.parent

                if not ancestor:
                    break

                print(f"\n[상위 {level}단계]")
                print(f"태그   : {ancestor.name}")
                print(f"class  : {ancestor.get('class')}")
                print(f"href   : {ancestor.get('href')}")
                print(f"onclick: {ancestor.get('onclick')}")

            # 너무 많은 결과를 방지
            if found >= 20:
                print("\n진단 결과 20개 확인 → 중단")
                return []

    print(
        f"\n========== 총 {found}개 시설 HTML 확인 ==========\n"
    )

    return []
