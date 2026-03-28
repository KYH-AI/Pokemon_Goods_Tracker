# Lego Price Collector Skill

## 목적

포켓몬 레고 세트의 가격 정보를 BrickEconomy(중고 시세)와 LEGO 공식 사이트(정가)에서 수집한다.

## 트리거 조건

파이프라인 Step 1 시작 시 항상 실행.

## 실행 순서

```bash
python .claude/skills/lego-price-collector/scripts/brickeconomy_scraper.py || true
python .claude/skills/lego-price-collector/scripts/lego_official_scraper.py || true
# bricklink_api.py는 v2 예정, 현재 비활성화
```

## 입력

- `config/watchlist.json` — 수집 대상 레고 목록
- `config/sources.json` — 소스별 URL
- `config/exchange_rate.json` — USD→KRW 환율 캐시

## 출력

- `data/raw/lego_brickeconomy.json`
- `data/raw/lego_official.json`

## 에러 처리

- BrickEconomy 차단 시: `lego_official.json`의 정가만 표시
- 스크립트 오류 시: `||true`로 스킵

## 제약

- `bricklink_api.py`: `sources.json`에서 `enabled: false`. 절대 활성화 금지 (v2 예정)
