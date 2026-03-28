# 포켓몬 굿즈 시세 추적 시스템

포켓몬 굿즈(카드, 레고, 콜라보 상품) 시세와 이벤트 정보를 한눈에 제공하는 정적 웹사이트.
GitHub Pages로 배포, GitHub Actions로 하루 2회 자동 갱신.

---

## 문서 목차

| 파일 | 내용 |
|------|------|
| [01-context.md](01-context.md) | 배경 및 목적, 범위, 데이터 소스, 제약조건, 용어 정의 |
| [02-workflow.md](02-workflow.md) | 5단계 파이프라인, 단계별 상세, 폴백 전략 |
| [03-project-structure.md](03-project-structure.md) | 폴더 구조, CLAUDE.md 섹션, 에이전트/스킬 목록 |
| [04-data-schemas.md](04-data-schemas.md) | JSON 파일 형식 (cards, lego, events, watchlist, grading_config) |
| [05-frontend.md](05-frontend.md) | UI 구조, 기술 스택, 데이터 전달 패턴 |
| [06-cicd.md](06-cicd.md) | GitHub Actions 워크플로우, LLM 조건부 호출 로직 |
| [07-risks.md](07-risks.md) | 리스크 항목별 영향 및 대응 방안 |
| [08-roadmap.md](08-roadmap.md) | v2/v3 향후 확장 계획 |

---

## 시스템 개요

```
GitHub Actions (하루 2회)
    │
    ├── Step 1: 데이터 수집  (TCGPlayer, eBay, 번개장터, 당근, 네이버카페, BrickEconomy...)
    ├── Step 2: 데이터 정제  (카드명 매핑, 에디션 태깅, 가격 정규화)
    ├── Step 3: 검증         (스키마, 이상치 탐지)
    ├── Step 4: 사이트 빌드  (정적 파일 복사)
    └── Step 5: 배포         (gh-pages 브랜치)
```

**핵심 제약**
- 호스팅: GitHub Pages (정적 사이트, CSR 구조)
- 비용: 무료 운영 원칙
- LLM 호출: 신규/변경 데이터 감지 시만 (비용 최적화)
- 국내 플랫폼 크롤링: 차단 시 자동 폴백
