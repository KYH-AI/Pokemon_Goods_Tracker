# 6. GitHub Actions CI/CD

## 6.1 워크플로우 구조 개요

```yaml
# .github/workflows/collect-and-deploy.yml 구조 개요
name: Collect & Deploy

on:
  schedule:
    - cron: '0 0 * * *'    # 09:00 KST (UTC 00:00)
    - cron: '0 9 * * *'    # 18:00 KST (UTC 09:00)
  workflow_dispatch: {}     # 수동 실행 지원

env:
  EBAY_API_KEY: ${{ secrets.EBAY_API_KEY }}
  BOK_API_KEY: ${{ secrets.BOK_API_KEY }}           # 한국은행 공개 API
  ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }} # LLM (변경사항 있을 때만 호출)
  GOOGLE_SHEET_ID: ${{ secrets.GOOGLE_SHEET_ID }}   # 폴백용 구글시트

jobs:
  collect:
    # Step 0: 환율 갱신 (한국은행 API, 일 1회)
    # Step 1~3: 데이터 수집, 정제, 검증
    #   - 수집: SNS 제외. eBay는 영어판 카드만.
    #   - LLM 호출: 신규/변경 데이터 감지 시만 (diff 체크 후 조건부 실행)
    # Python 환경 세팅 → 스크립트 순차 실행

  build-and-deploy:
    needs: collect
    # Step 4~5: 정적 파일 복사 + gh-pages 배포 (CSR 구조, 빌드 도구 없음)
```

---

## 6.2 LLM 조건부 호출 로직

```python
# data-enrichment-agent 호출 전 diff 체크
new_cards = [c for c in watchlist if c["id"] not in existing_mapping]
new_events = [e for e in raw_events if e["id"] not in existing_events]

if new_cards or new_events:
    # LLM 호출 (Claude API)
    run_data_enrichment_agent(new_cards, new_events)
else:
    # 변경사항 없음 → LLM 스킵 (비용 0)
    pass
```

> LLM 실제 호출은 **주 1~2회 수준**으로, API 비용은 사실상 무료에 가까움.
