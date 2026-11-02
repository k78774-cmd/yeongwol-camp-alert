# 영월캠프 예약 감시 — 무료 스케줄러 운영 안내

## 현재 자동 실행 (GitHub 자체)

- `.github/workflows/main.yml`: UTC 매 5분의 2, 7, 12, …, 57분에 실행 시도
- `workflow_dispatch`: 외부 예약 서비스 및 GitHub Actions 화면에서 수동 실행 가능
- 중복 실행 방지: `concurrency`로 같은 예약 감시의 실행 겹침을 제한
- 상태가 이전과 같으면 `alert_state.json`을 다시 저장하지 않음
- 예약 사이트/텔레그램 오류가 발생하면 Actions에서 **실패**로 표시
- 매일 오전 8:17 KST: 별도 점검 워크플로가 감시의 마지막 실행 결과를 텔레그램으로 발송

**한계:** GitHub `schedule`은 실행이 지연·누락될 수 있어 5분 실행을 보장하지 않습니다.
따라서 실제 취소 객실을 놓치지 않으려면 별도 무료 실행 서비스를 추가로 연결해야 합니다.

## 권장: cron-job.org로 5분마다 보조 호출 (사용자가 계정 연결)

1. [cron-job.org](https://cron-job.org/en/)에서 무료 계정을 만들고 새 cronjob을 생성합니다.
2. GitHub `Settings → Developer settings → Personal access tokens → Fine-grained tokens`에서 토큰을 새로 만듭니다.
   - Resource owner: `k78774-cmd`
   - Repository access: **Only selected repositories** → `yeongwol-camp-alert`
   - Repository permissions: **Actions: Read and write** (필수)
   - 다른 저장소 권한이나 `Contents: write`는 주지 않습니다.
   - 만료되면 이 연결도 끊기므로 만료 전 갱신해야 합니다.
3. cron-job 설정은 다음과 같습니다.

   - URL: `https://api.github.com/repos/k78774-cmd/yeongwol-camp-alert/actions/workflows/main.yml/dispatches`
   - Method: `POST`
   - Schedule: **5분마다**, 가능하면 GitHub 기본 실행의 2, 7, 12분과 겹치지 않는 0, 5, 10분 등
   - Header `Authorization`: `Bearer <앞에서 발급한 GitHub 토큰>`
   - Header `Accept`: `application/vnd.github+json`
   - Header `Content-Type`: `application/json`
   - Body: `{"ref":"main"}`
   - 오류 알림/실행 기록을 활성화합니다.

4. cron-job.org의 'Test run'으로 먼저 호출하고 GitHub Actions에서 `workflow_dispatch` 실행 기록을 확인합니다. GitHub API 성공 응답은 `204` 등으로 표시될 수 있습니다.
5. 텔레그램 예약 알림은 새로운 토요일 객실이 발견된 경우에만 보내며, 일일 정상 작동 확인 메시지는 별도로 1회 발송합니다.

**보안:** GitHub 토큰을 대화창, 저장소 코드, 실행 로그에 붙여 넣지 마세요. 외부 예약 서비스에 토큰을 맡겨야 하므로 계정 2단계 인증과 최소권한·토큰 만료일 관리가 중요합니다. 외부 서비스에 토큰을 보관하기 싫다면 외부 실행은 건너뛰고 GitHub 기본 예약 실행만 사용하되 지연 가능성을 감수해야 합니다.

## 운영 점검

- GitHub Actions: https://github.com/k78774-cmd/yeongwol-camp-alert/actions
- 최근 30분 내 `영월캠프 예약 확인` 성공 기록이 없으면 실행 누락 여부를 확인합니다.
- `영월캠프 하루 한 번 작동 확인` 경고 메시지가 오면 해당 실행 기록을 점검합니다.
- 인증 정보가 잘못되어도 상태 파일을 임의로 비우지 않습니다.
- 예약 불가(마감)는 알림을 보내지 않으며, 마감 → 예약 가능으로 바뀐 경우 다시 알림을 보냅니다.
