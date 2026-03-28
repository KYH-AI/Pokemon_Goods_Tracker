# Data Processor Skill

## 목적

수집된 raw 데이터를 정제, 정규화, 병합하여 최종 산출물 JSON을 생성한다.

## 트리거 조건

파이프라인 Step 2에서 `data-enrichment-agent` 실행 후 항상 실행.

## 실행 순서 (의존성 순서 준수)

```bash
python .claude/skills/data-processor/scripts/card_name_mapper.py
python .claude/skills/data-processor/scripts/edition_tagger.py
python .claude/skills/data-processor/scripts/grading_normalizer.py
python .claude/skills/data-processor/scripts/price_normalizer.py
python .claude/skills/data-processor/scripts/event_deduplicator.py
python .claude/skills/data-processor/scripts/data_merger.py
```

## 입력

- `data/raw/` — 모든 raw 수집 파일
- `data/raw/*_parsed.json` — LLM 처리 결과 (있는 경우)
- `config/card_name_map.json`, `config/grading_config.json`, `config/exchange_rate.json`

## 출력

- `data/cards.json` — 정제된 카드 시세 (전체 스키마)
- `data/lego.json` — 정제된 레고 가격
- `data/events.json` — 정제된 이벤트 정보

## 에러 처리

- 실패 시 재시도 2회 → 이전 `data/*.json` 파일 유지
- null 값 생성 금지 — 데이터 없으면 해당 항목 제외

## 성공 기준

`data/cards.json`, `data/lego.json`, `data/events.json` 3개 파일 생성.
