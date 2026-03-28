# Validator Skill

## 목적

`data/` JSON 파일들의 스키마 유효성, 데이터 품질, 신선도를 검증한다.

## 트리거 조건

파이프라인 Step 3, `data-processor` 스킬 실행 후 항상 실행.

## 실행

```bash
python .claude/skills/validator/scripts/validate_data.py
```

## 입력

- `data/cards.json`, `data/lego.json`, `data/events.json`

## 출력

- `logs/validate_{YYYYMMDD_HHMM}.json` — 검증 결과 로그

## 검증 항목

| 항목 | 기준 | 실패 시 |
|------|------|--------|
| JSON 스키마 유효성 | 필수 필드 존재, 타입 일치 | 파이프라인 중단 |
| 가격 이상치 | 전일 대비 ±300% 초과 | 경고 플래그 후 계속 |
| 이벤트 날짜 | 30일 이전 이벤트 | 아카이브 이동 |
| 데이터 신선도 | updated_at 24시간 이내 | 경고 로그 |

## 성공 기준

스키마 에러 없음. 경고 플래그가 있어도 배포 계속 진행.
