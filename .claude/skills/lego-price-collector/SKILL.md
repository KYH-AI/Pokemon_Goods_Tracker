# Lego Price Collector Skill

## 목적

포켓몬 레고 세트의 가격 정보를 LEGO 공식(정가), 번개장터(중고가), BrickSet(단종 여부)에서 수집한다.

## 트리거 조건

파이프라인 Step 1 시작 시 항상 실행.

## 실행 순서

```bash
python .claude/skills/lego-price-collector/scripts/lego_official_scraper.py || true
python .claude/skills/lego-price-collector/scripts/lego_bunjang_scraper.py || true
python .claude/skills/lego-price-collector/scripts/brickset_scraper.py || true
python .claude/skills/lego-price-collector/scripts/brickeconomy_scraper.py || true
# bricklink_api.py: v2 예정, 현재 비활성화
```

## 입력

- `config/watchlist.json` — 수집 대상 레고 목록 (`official_price_krw`, `bunjang_search_keywords` 포함)
- `config/sources.json` — 소스별 URL
- 환경변수: `BRICKSET_API_KEY`

## 출력

- `data/raw/lego_official.json` — 정가 (LEGO 공식 scraping 또는 watchlist fallback)
- `data/raw/lego_bunjang.json` — 번개장터 중고 시세
- `data/raw/lego_brickset.json` — 단종 여부, 출시연도, 피스 수
- `data/raw/lego_brickeconomy.json` — 중고/새상품 시세, 프리미엄율 (현재 403 차단)

## 에러 처리

- LEGO 공식 403 차단 시: `watchlist.json`의 `official_price_krw` 사용 (price_source: "watchlist")
- 번개장터 매물 없음: `no_results` 상태로 기록, 파이프라인 계속
- BrickSet API 키 미설정: 즉시 스킵 (단종 여부 미표시)
- BrickEconomy 403 차단: 스킵 (premium_pct는 data_merger에서 번개장터가로 자동 계산)
- 스크립트 오류 시: `|| true`로 스킵

## 제약

- `bricklink_api.py`: `sources.json`에서 `enabled: false`. 절대 활성화 금지 (v2 예정)
