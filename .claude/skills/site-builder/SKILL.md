# Site Builder Skill

## 목적

`data/` JSON 파일과 `site/templates/`, `site/static/`을 `site/build/`로 복사하여
GitHub Pages 배포 준비를 완료한다.

## 트리거 조건

파이프라인 Step 4, `validator` 스킬 통과 후 실행.

## 실행

```bash
python .claude/skills/site-builder/scripts/build_site.py
```

## 입력

- `site/templates/index.html` — CSR 껍데기 HTML
- `site/static/` — CSS, JS, 이미지
- `data/cards.json`, `data/lego.json`, `data/events.json`

## 출력

- `site/build/index.html` — 메타 정보 주입된 HTML
- `site/build/static/` — 정적 자산
- `site/build/data/` — JSON 데이터 파일
- `site/build/build_info.json` — 빌드 메타 정보

## CSR 구조 주의사항

빌드 도구(Webpack 등) 사용 안 함. 단순 파일 복사 + 메타 정보 주입.
`site/build/data/` 경로에 JSON 파일이 있어야 브라우저의 fetch가 작동함.

## 성공 기준

`site/build/index.html` + `site/build/data/cards.json` 파일 존재.
