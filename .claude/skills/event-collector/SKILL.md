# Event Collector Skill

## 목적

포켓몬코리아 공식 웹사이트와 네이버 카페 공개 게시판에서 이벤트/행사 정보를 수집한다.

## 트리거 조건

파이프라인 Step 1 시작 시 항상 실행.

## 실행 순서

```bash
python .claude/skills/event-collector/scripts/pokemon_korea_scraper.py || true
python .claude/skills/event-collector/scripts/pokemoncard_scraper.py || true
python .claude/skills/event-collector/scripts/naver_search_scraper.py || true
python .claude/skills/event-collector/scripts/naver_cafe_scraper.py || true
```

## 입력

- `config/sources.json` — 이벤트 소스 URL
- 환경변수: `GOOGLE_SHEET_ID` (구글시트 폴백용, 선택사항)

## 출력

- `data/raw/events_official.json` — 포켓몬코리아 공식 이벤트
- `data/raw/events_community.json` — 카페/커뮤니티 이벤트

## 폴백 전략

```
1차: 네이버 카페 공개 게시판 크롤링
  ↓ 실패
2차: 구글시트 수동 입력 데이터 fetch (GOOGLE_SHEET_ID 환경변수 필요)
  ↓ (항상 작동)
최종: 이벤트 탭에 "커뮤니티 정보는 수동 업데이트" 안내
```

## 제약

- SNS(인스타그램, X) 크롤링 금지 — 공식 웹사이트만 수집
- 네이버 카페: 공개 게시판만 (로그인 불필요 게시글)
