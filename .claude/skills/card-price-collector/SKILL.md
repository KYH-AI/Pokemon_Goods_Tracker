# Card Price Collector Skill

## 목적

포켓몬 카드 시세를 해외(TCGPlayer, PriceCharting, eBay)와
국내(네이버 카페, 번개장터, 당근마켓) 소스에서 수집한다.

## 트리거 조건

파이프라인 Step 1 시작 시 항상 실행.

## 실행 순서

각 스크립트는 독립적으로 실행. 하나 실패해도 다음 계속.

```bash
python .claude/skills/card-price-collector/scripts/tcgplayer_scraper.py || true
python .claude/skills/card-price-collector/scripts/pricecharting_scraper.py || true
python .claude/skills/card-price-collector/scripts/ebay_scraper.py || true
python .claude/skills/card-price-collector/scripts/naver_cafe_price_scraper.py || true
python .claude/skills/card-price-collector/scripts/bunjang_scraper.py || true
python .claude/skills/card-price-collector/scripts/daangn_scraper.py || true
```

## 입력

- `config/watchlist.json` — 수집 대상 카드 목록
- `config/sources.json` — 소스별 URL 및 요청 설정
- `config/ebay_config.json` — eBay API 설정
- 환경변수: `EBAY_API_KEY`, `BOK_API_KEY`

## 출력

- `data/raw/cards_tcgplayer.json`
- `data/raw/cards_pricecharting.json`
- `data/raw/cards_ebay.json`
- `data/raw/cards_kr_naver.json`
- `data/raw/cards_bunjang.json`
- `data/raw/cards_daangn.json`

## 에러 처리

- HTTP 403/429/CAPTCHA 감지 → 즉시 스킵, `logs/block_tracker.json` 기록
- 3일 연속 차단 → `config/sources.json`의 해당 소스 `enabled: false` 자동 설정
- 전체 소스 실패 → 이전 `data/raw/` 파일 유지

## 제약

- eBay는 `en` 에디션 카드에만 적용 (`edition_scope: "en"`)
- 네이버 카페: 공개 게시판(로그인 불필요)만 접근
- 번개장터/당근마켓: 차단 감지 시 즉시 스킵, 강제 재시도 금지
- SNS 크롤링 시도 금지
