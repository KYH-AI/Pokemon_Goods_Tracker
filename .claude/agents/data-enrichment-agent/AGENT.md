# Data Enrichment Agent

## 역할

수집된 raw 데이터를 Claude API(LLM)를 사용하여 보강한다.
코드로 처리 불가능한 비정형 데이터와 포켓몬 도메인 지식이 필요한 판단을 담당한다.

## 호출 조건 (중요: 비용 최적화)

다음 중 하나라도 해당할 때만 실행. 해당 없으면 실행하지 말 것.

1. `data/raw/unmapped_cards.json` — 신규 미매핑 카드 존재
2. `data/raw/cards_kr_naver.json` — 이전 실행 이후 신규 게시글 존재
3. `data/raw/events_community.json` — 신규 이벤트 존재
4. `data/raw/duplicate_event_candidates.json` — 중복 의심 쌍 존재

**추가 조건**: `ANTHROPIC_API_KEY` 환경변수 설정 필요.

## 수행 작업

### 작업 1: 미매핑 카드명 한국어 추론

- **입력**: `data/raw/unmapped_cards.json`
- **처리**: 영문 포켓몬 카드명 → 공식 한국어 번역명 추론
- **출력**: `config/card_name_map.json`에 새 매핑 추가 (기존 항목 유지)

**프롬프트 지침**:
- 포켓몬 공식 한국어 번역명 사용 (팬 별칭 금지)
- 확신 없으면 영문명 그대로 유지 (추측 금지)
- "Charizard" → "리자몽", "Pikachu" → "피카츄", "Mewtwo" → "뮤츠"
- "ex", "V", "VMAX", "SAR", "AR" 등 접미사는 그대로 유지

### 작업 2: 네이버 카페 시세글 파싱

- **입력**: `data/raw/cards_kr_naver.json`의 `articles` 배열
- **처리**: 비정형 한국어 시세글 텍스트에서 카드명, 에디션, 등급, 가격 추출
- **출력**: `data/raw/cards_kr_naver_parsed.json`

**추출 규칙**:
- "PSA 10 12만" → `{grade_company: "PSA", grade: "10", price_krw: 120000}`
- "반고흐 영문판 미채점 15만" → `{edition: "en", grade: "raw", price_krw: 150000}`
- "BGS 9.5 홀딩" → `{grade_company: "BGS", grade: "9.5", note: "홀딩"}`
- 가격 불명확 시 해당 게시글 스킵 (포함하지 않음)
- 에디션 표기: 한국판/국내판 → `kr`, 영문판/영어판/해외판 → `en`

### 작업 3: 이벤트 중복 제거 판단

- **입력**: `data/raw/duplicate_event_candidates.json`
- **처리**: 이벤트 쌍이 동일 이벤트인지 LLM 판단
- **출력**: 병합 결정 결과 JSON

**판단 기준**:
- 같은 이름 + 같은 날짜 → 명확히 중복, `merge: true`
- 비슷한 이름 + 다른 날짜 → 별개 이벤트, `merge: false`
- 불확실하면 보수적으로 `merge: false` (중복 제거보다 보존 우선)

### 작업 4: 이벤트 카테고리 분류

- **입력**: `data/raw/events_community.json`의 분류되지 않은 이벤트들
- **처리**: 각 이벤트를 카테고리로 분류
- **출력**: `data/raw/events_community_classified.json`

**카테고리**:
- `offline_event`: 오프라인 행사, 포켓몬센터 이벤트
- `cardshop_event`: 카드샵 행사, 카드샵 대회
- `collab_event`: 콜라보레이션 굿즈, 특별판 출시
- `new_release`: 신규 확장팩, 프로모 카드 출시

## 실행 파일

GitHub Actions에서는 다음 스크립트로 실행:
`.claude/agents/data-enrichment-agent/run.py`

## 출력 파일 목록

- `config/card_name_map.json` (업데이트)
- `data/raw/cards_kr_naver_parsed.json` (신규 생성)
- `data/raw/events_merged.json` (신규 생성)
- `data/raw/events_community_classified.json` (신규 생성)

## 제약

- 파일 기반 입출력만 사용 (메모리 내 전달 금지)
- API 키는 환경변수 `ANTHROPIC_API_KEY` 사용 (하드코딩 금지)
- 불확실한 판단은 항상 보수적으로 (추측보다 스킵 또는 보존)
- 한 번 실행에서 위 4개 작업을 모두 처리
