# 포켓몬 굿즈 시세 추적 시스템 — 메인 에이전트 지침

## 1. 프로젝트 개요

포켓몬 굿즈(카드, 레고) 시세와 이벤트 정보를 자동 수집하여 GitHub Pages에 정적 웹사이트로 제공하는 시스템.

- **대상 사용자**: 비개발자 10명+ (모바일 접근 비율 높음)
- **기술 스택**: Python(수집/처리) + Vanilla JS(프론트엔드, CSR) + GitHub Actions(자동화)
- **배포**: GitHub Pages (`gh-pages` 브랜치, CSR 구조)
- **비용**: 무료 운영 원칙

## 2. 워크플로우 개요 (5단계 파이프라인)

```
[Step 1] 데이터 수집
         card-price-collector + lego-price-collector + event-collector 스킬 병렬 실행

[Step 2] 데이터 정제
         data-enrichment-agent (조건부, 신규/변경 시만)
         → data-processor 스킬 실행

[Step 3] 검증
         validator 스킬 실행

[Step 4] 사이트 빌드
         site-builder 스킬 실행

[Step 5] 배포
         gh-pages 브랜치 push
```

각 단계 실패 처리:
- **수집 실패**: 해당 소스만 스킵, 나머지 계속
- **정제/검증 실패**: 재시도(최대 2회) 후 이전 `data/` 파일 유지
- **빌드 실패**: 재시도(1회) 후 배포 중단
- **전체 실패**: 이전 데이터 유지 + GitHub Actions 실패 알림

## 3. 스킬 호출 규칙

| 스킬 | 호출 시점 | 실패 시 행동 |
|------|----------|------------|
| `card-price-collector` | Step 1, 항상 | 소스별 독립 실패 허용 |
| `lego-price-collector` | Step 1, 항상 | 소스별 독립 실패 허용 |
| `event-collector` | Step 1, 항상 | 소스별 독립 실패 허용 |
| `data-processor` | Step 2, 항상 | 재시도 2회 → 이전 데이터 유지 |
| `validator` | Step 3, 항상 | 스키마 실패 시 파이프라인 중단 |
| `site-builder` | Step 4, 항상 | 재시도 1회 → 배포 중단 |

스킬 실행 방법: `.claude/skills/{skill-name}/SKILL.md` 지침에 따라 스크립트 순차 실행.

## 4. 서브에이전트 호출 규칙

**`data-enrichment-agent`** 호출 조건 (하나라도 해당하면 실행):
- `data/raw/unmapped_cards.json` 파일이 존재하고 비어있지 않을 때
- `data/raw/cards_kr_naver.json`에 신규 게시글이 있을 때 (이전 실행과 비교)
- `data/raw/events_community.json`에 신규 이벤트가 있을 때
- `data/raw/duplicate_event_candidates.json`에 중복 의심 쌍이 있을 때

**추가 조건**: `ANTHROPIC_API_KEY` 환경변수가 설정되어 있어야 함.

조건 미충족 시 → 이전 LLM 처리 결과 재사용 (Claude API 호출 없음, 비용 0).

서브에이전트 실행: `.claude/agents/data-enrichment-agent/AGENT.md` 지침 참조.

## 5. 데이터 규칙

**파일 경로 규칙**:
- 수집 원본: `data/raw/{source}_{type}.json`
- 정제 결과: `data/cards.json`, `data/lego.json`, `data/events.json`
- 빌드 산출물: `site/build/` (JSON 포함)

**JSON 규칙**:
- `null` 값 사용 금지 — 데이터 없으면 해당 필드/배열 항목 자체를 제외
- 날짜/시각: ISO 8601 형식, KST (`+09:00`)
- KRW 가격: 정수. USD 가격: 소수점 2자리.
- 에디션 코드: `kr` (한국판), `en` (영어판). `jp`는 v2 예정.

**네이밍 규칙**:
- 카드 ID: `{set-slug}-{card-name-slug}` (예: `sv-pikachu-vangogh`)
- 이벤트 ID: `evt-{YYYYMMDD}-{title-slug}`
- 레고 ID: `lego-pokemon-{set-number}`

## 6. 에러 핸들링 원칙

- 개별 소스 실패: `logs/` 에 기록 후 스킵 — 파이프라인 중단하지 않음
- 차단 감지 (HTTP 403/429/CAPTCHA): 즉시 스킵 (재시도 절대 금지)
- 3일 연속 차단: `config/sources.json`의 해당 소스 `enabled: false` 자동 설정
- 스키마 검증 실패: 배포 중단 (`site-builder` 실행 안 함)
- 이상치 감지 (±300%): 경고 플래그 추가 후 배포 계속 (데이터 숨기지 않음)

## 7. 배포 규칙

- 배포 조건: Step 3 검증 통과 (스키마 에러 없을 것)
- 배포 대상: `site/build/` → `gh-pages` 브랜치
- 롤백 기준: 배포 후 HTTP 200 응답 없으면 이전 커밋으로 자동 롤백

## 8. 금지 사항

- 유료 API 무단 사용 (eBay Browse API 외 유료 API 추가 불가)
- 환율: 1,500 KRW/USD 고정값 사용 (한국은행 ECOS API 미사용) — `exchange_rate.json`의 `expires_at: 2099` 유지, BOK_API_KEY 불필요
- 차단 감지 후 강제 재시도
- API 키 소스 코드 하드코딩 → 반드시 환경변수 사용
- SNS 크롤링 (인스타그램, X/트위터) — 포켓몬코리아 공식 웹사이트만 허용
- JSON에 `null` 값 포함
- `bricklink_api.py` 활성화 (`enabled: false` 유지, v2 예정)

## 9. 국내 플랫폼 크롤링 정책

**번개장터 / 당근마켓**:
- ToS 위반 리스크를 인지한 상태에서 제한적으로 허용
- 수집 전 `config/sources.json`의 `enabled` 필드 확인
- 차단 감지 시 즉시 스킵 (재시도 절대 금지)
- 3일 연속 차단 → `logs/block_tracker.json` 기록 후 자동 비활성화
- 번개장터 가격 = 판매 희망가 (수수료 6%+ 미포함), UI에 명시 필수

**네이버 카페**:
- 공개 게시판(로그인 없이 접근 가능한 게시글)만 대상
- HTTP 302 리다이렉트(로그인 페이지) 감지 시 해당 게시글 스킵
- 시세글 파싱은 스크립트가 아닌 `data-enrichment-agent` (LLM)가 처리

## 10. LLM 호출 정책

- 신규/변경 데이터 감지 시만 Claude API 호출 (변경 없으면 0원)
- 이전 실행 결과를 캐시로 재사용
- `ANTHROPIC_API_KEY` 미설정 시: LLM 작업 전체 스킵, 매핑 테이블만 사용
- 예상 API 호출 빈도: 주 1~2회 (비용 무시 가능한 수준)
- LLM 호출 대상 작업만: 카드명 추론, 시세글 파싱, 이벤트 중복 판단, 이벤트 분류
