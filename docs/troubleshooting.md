# 문제 해결 가이드

## 1. 크롤링 차단 대처

### 증상
- GitHub Actions 로그에 `[BLOCKED]` 또는 `HTTP 403/429` 메시지
- `logs/block_tracker.json`에 해당 소스의 `consecutive_days` 값 증가

### 조치 방법

**즉시 조치 (자동):**
- 차단 감지 시 해당 소스는 즉시 스킵, 파이프라인은 계속 실행
- 3일 연속 차단 시 `config/sources.json`의 `enabled: false` 자동 설정

**수동 재활성화:**
```json
// config/sources.json 에서 해당 소스 enabled를 true로 변경
{
  "card_sources": {
    "bunjang": {
      "enabled": true   // false → true 로 변경 후 push
    }
  }
}
```

**block_tracker 초기화:**
```
logs/block_tracker.json 파일에서 해당 소스의 consecutive_days를 0으로 초기화
```

---

## 2. watchlist.json에 카드 추가 방법 (비개발자용)

### 새 카드 추가 순서

1. GitHub 저장소 → `config/watchlist.json` 파일 클릭
2. 우측 상단 **연필 아이콘(편집)** 클릭
3. `"cards"` 배열 마지막 항목 뒤에 쉼표(`,`) 추가 후 새 항목 입력:

```json
{
  "id": "세트코드-카드이름슬러그",
  "name_en": "영어 카드명",
  "name_ko": "한국어 카드명",
  "set": "확장팩 이름",
  "set_id": "세트코드",
  "category": "expansion",
  "editions": ["en", "kr"],
  "tcgplayer_id": "TCGPlayer 상품 ID",
  "pricecharting_id": "pricecharting-url-id",
  "ebay_search_keywords": ["검색어1", "검색어2"],
  "naver_cafe_keywords": ["한국어 검색어"],
  "domestic_search_keywords": ["국내 플랫폼 검색어"]
}
```

**ID 찾는 방법:**
- `tcgplayer_id`: TCGPlayer 상품 URL의 숫자 부분
  - `https://www.tcgplayer.com/product/503625/...` → `503625`
- `pricecharting_id`: PriceCharting URL 마지막 부분
  - `https://www.pricecharting.com/game/pokemon-151-charizard-ex` → `pokemon-151-charizard-ex`

4. 페이지 하단 **Commit changes** 클릭
5. GitHub Actions가 자동 실행되어 새 카드 수집 시작

---

## 3. 수동 실행 방법

### GitHub Actions에서 수동 트리거

1. 저장소 → **Actions** 탭
2. 좌측 **포켓몬 굿즈 시세 수집 및 배포** 클릭
3. **Run workflow** 버튼 클릭
4. 옵션 선택 후 **Run workflow** 확인

### 로컬에서 개별 스크립트 실행

```bash
# 환경 변수 설정
export ANTHROPIC_API_KEY="sk-ant-..."
export BOK_API_KEY="..."

# 카드 수집
python .claude/skills/card-price-collector/scripts/tcgplayer_scraper.py

# 데이터 정제
python .claude/skills/data-processor/scripts/data_merger.py

# 검증
python .claude/skills/validator/scripts/validate_data.py

# 사이트 빌드
python .claude/skills/site-builder/scripts/build_site.py
```

---

## 4. 환율 캐시 갱신 방법

### 자동 갱신 (기본)
`config/exchange_rate.json`의 `expires_at` 날짜 이후 자동 갱신됨.

### 수동 강제 갱신

방법 1 — 캐시 만료일 수정:
```json
// config/exchange_rate.json 의 expires_at을 과거 날짜로 변경
{
  "expires_at": "2020-01-01T00:00:00+09:00"
}
```
다음 실행 시 `price_normalizer.py`가 BOK API를 호출하여 갱신.

방법 2 — 로컬 직접 실행:
```bash
export BOK_API_KEY="한국은행_API_키"
python .claude/skills/data-processor/scripts/price_normalizer.py
```

### BOK API 키 없는 경우
`config/exchange_rate.json`의 `rate` 값을 현재 환율로 직접 수정:
```json
{
  "rate": 1350.0,
  "fallback_used": true,
  "expires_at": "2026-12-31T00:00:00+09:00"
}
```

---

## 5. 검증 실패로 배포가 중단됐을 때

### 증상
- GitHub Actions에서 Step 3 (검증) 실패
- `logs/validate_YYYYMMDD_HHMM.json`에 오류 내용

### 로그 확인
```
Actions 탭 → 실패한 워크플로우 → [Step 3] 데이터 검증 → 로그 펼치기
```

### 자주 발생하는 오류

**null 값 포함 오류:**
- 원인: 스크립트가 null 값을 JSON에 포함
- 조치: `data/cards.json` 직접 열어 null 값 포함 항목 삭제 후 커밋

**파일 없음 오류:**
- 원인: 모든 소스가 수집 실패
- 조치: 이전에 생성된 `data/cards.json` 이 있으면 자동 유지
  없으면 GitHub Actions 다시 실행

**스키마 오류:**
- 원인: 필수 필드(id, updated_at 등) 누락
- 조치: `data_merger.py`를 로컬에서 디버그 실행

---

## 6. 사이트가 표시되지 않을 때

**데이터 파일 경로 확인:**
```
site/build/data/cards.json   ← 이 파일이 없으면 화면에 아무것도 표시 안 됨
site/build/data/lego.json
site/build/data/events.json
```

**브라우저 개발자 도구 확인:**
- F12 → Console 탭에서 fetch 오류 확인
- Network 탭에서 `data/cards.json` 요청 상태 확인 (200이어야 정상)

**CORS 오류 (로컬 테스트 시):**
```bash
# 로컬 HTTP 서버 실행 (file:// 프로토콜 대신 http:// 사용)
cd site/build
python -m http.server 8080
# 브라우저에서 http://localhost:8080 접속
```
