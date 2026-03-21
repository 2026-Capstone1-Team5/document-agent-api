# document-agent-api SPEC

## Purpose

- `document-agent-api`는 Document AI 서비스의 API 레이어다.
- Web 앱과 MCP 클라이언트가 공통으로 사용하는 문서 업로드, parse job 생성, 파싱 결과 조회, 다운로드, 삭제 기능을 제공한다.
- 문서 원본 preview/download를 위한 안전한 접근 경계도 제공한다.
- parser 엔진 내부 로직은 이 저장소의 책임이 아니다.

## Scope

- 사용자 등록/로그인
- 사용자 소유 문서 조회
- parse job 생성 및 상태 조회
- 파싱 결과 반환 및 다운로드
- 오브젝트 스토리지 기반 원본/결과 payload 저장
- 큐 기반 비동기 파싱 orchestration
- `MCP` 연동을 위한 `API key` 인증 제공

## MVP Rules

- 업로드 요청은 parse job 생성으로 끝나며, 실제 파싱은 비동기 worker가 수행한다.
- 성공한 파싱 결과만 문서 리소스로 저장한다.
- 문서 메타데이터는 최소화한다.
- 문서 도메인의 핵심 저장 구조는 `documents`와 `document_results`를 유지한다.
- 업로드 직후 상태 관리는 `parse_jobs`를 통해 분리한다.
- 사용자 인증과 소유권 관리를 위해 `users` 테이블을 함께 사용한다.

## Auth Model

- Web 사용자 흐름은 `JWT bearer access token`을 사용한다.
- MCP/agent 연동은 사용자가 발급한 `API key`를 사용한다.
- 문서 API는 `JWT` 또는 `API key` 둘 중 하나로 접근 가능하다.
- API key 발급/목록/폐기는 `JWT 로그인 사용자`만 수행할 수 있다.
- 사용자는 여러 개의 API key를 만들 수 있고, 각 key는 사람이 읽을 수 있는 `name`으로 관리한다.

## Non-Goals

- parser 알고리즘 구현
- API key 권한 스코프 관리

## Current Entry Points

- `src/main.py`
- `src/auth/router.py`
- `src/documents/router.py`
- `src/parse_jobs/router.py`
