# API Key Auth Plan

## Goal

- `document-agent-api`가 기존 웹 로그인용 JWT 외에 `MCP` 연동용 `API key` 인증을 제공한다.
- Web의 현재 로그인 흐름은 유지하고, `MCP`는 사용자가 직접 입력한 `API key`로 문서 API를 호출할 수 있게 한다.
- 계약 변경은 문서와 OpenAPI를 먼저 맞춘 뒤 구현한다.

## Current State

- 현재 인증 수단은 `Authorization: Bearer <access-token>` 하나뿐이다.
- `/api/v1/documents*`와 `/api/v1/auth/me`는 모두 JWT 기반 사용자 인증만 허용한다.
- 저장소 가이드가 요구하는 `docs/SPEC.md`, `docs/API_SPEC.md`, `docs/DATA_MODEL.md`는 아직 저장소에 없다.
- 실제 구현과 테스트는 이미 존재하므로, 이번 작업에서는 코드만이 아니라 계약 문서도 같이 정리해야 한다.

## Working Assumptions

- MVP에서는 사용자당 `복수 API key`를 지원한다.
- 각 key는 `name`을 가진다.
- `API key`는 장기 자격증명이며, 원문 값은 생성 시점에만 반환한다.
- 서버에는 원문 key를 저장하지 않고, `hash + prefix + created_at`만 저장한다.
- 문서 API는 `JWT` 또는 `API key` 둘 중 하나로 접근 가능해야 한다.
- `API key` 생성/목록/폐기는 `JWT 로그인 사용자`만 수행할 수 있어야 한다.

## Proposed Contract

### Auth Surface

- 유지:
  - `POST /api/v1/auth/register`
  - `POST /api/v1/auth/login`
  - `GET /api/v1/auth/me`
- 추가:
  - `GET /api/v1/auth/api-keys`
    - 현재 사용자의 API key 목록 조회
  - `POST /api/v1/auth/api-keys`
    - `name`을 받아 새 API key 발급
    - 응답에서만 원문 API key 반환
  - `DELETE /api/v1/auth/api-keys/{api_key_id}`
    - 특정 API key 폐기

### Authentication Behavior

- 문서 관련 엔드포인트는 아래 두 방식 중 하나를 허용한다.
  - `Authorization: Bearer <jwt-access-token>`
  - `X-API-Key: <raw-api-key>`
- `MCP` 호환성을 위해 `Authorization: Bearer <raw-api-key>`도 허용하는 것이 실용적이다.
  - 단, key prefix로 `JWT`와 구분 가능한 형식을 사용한다.
  - 예: `dagk_...`
- `/api/v1/auth/api-keys*` 엔드포인트는 `JWT`만 허용한다.
  - 유출된 API key만으로 새 key를 발급하거나 삭제하면 안 된다.

### OpenAPI / Markdown Docs

- FastAPI가 노출하는 OpenAPI schema에 `apiKey` 보안 스키마를 반영한다.
- 문서 엔드포인트 security를 `Bearer` 또는 `ApiKey` 허용 형태로 바꾼다.
- `docs/API_SPEC.md`에 인증 방식과 key lifecycle을 서술한다.
- `docs/DATA_MODEL.md`에 사용자-API key 저장 방식을 반영한다.
- 누락된 `docs/SPEC.md`, `docs/API_SPEC.md`, `docs/DATA_MODEL.md`를 이번 작업에서 함께 생성한다.

## Proposed Data Model

### Minimal MVP Option

- `user_api_keys` 테이블 추가
  - `id`
  - `user_id`
  - `name`
  - `key_hash`
  - `key_prefix`
  - `created_at`

## Implementation Plan

1. Contract sync
   - 누락된 `docs/SPEC.md`, `docs/API_SPEC.md`, `docs/DATA_MODEL.md`를 생성한다.
   - 현재 OpenAPI 생성 결과에 API key 보안 스키마와 신규 엔드포인트를 반영한다.
2. Persistence
   - `users` 모델과 Alembic migration에 API key 관련 컬럼을 추가한다.
   - `UserModel`과 관련 schema/type을 확장한다.
3. API key generation
   - 충분한 길이의 랜덤 raw key를 생성한다.
   - 서버 저장 시에는 `SHA-256` 또는 `HMAC-SHA-256` 기반 hash만 저장한다.
   - 응답에는 raw key 전체와 prefix, createdAt를 반환한다.
4. Auth service split
   - 기존 `AuthService`에 `issue_api_key`, `revoke_api_key`, `get_api_key_status`를 추가하거나 별도 service로 분리한다.
   - `JWT 전용 current user dependency`와 `JWT 또는 API key 허용 dependency`를 분리한다.
5. Request authentication
   - 인증 dependency가 `Authorization`과 `X-API-Key`를 모두 읽도록 확장한다.
   - `JWT` 검증 실패와 `API key` 검증 실패의 에러 코드를 구분해 정리한다.
6. Route integration
   - 문서 라우터는 `JWT 또는 API key` dependency를 사용하도록 변경한다.
   - API key 관리 라우터는 `JWT 전용` dependency를 사용한다.
7. Tests
   - auth router/service 테스트에 API key 발급, 조회, 폐기, 회전 케이스를 추가한다.
   - documents router 테스트에 `X-API-Key` 및 `Bearer <api-key>` 인증 케이스를 추가한다.
   - 기존 JWT 흐름 회귀 테스트를 유지한다.
8. Developer docs
   - `.env.example`와 `README.md`에 인증 방식 설명을 추가한다.
   - MCP 저장소에서 어떤 헤더를 쓰면 되는지 연결 가이드를 남긴다.

## Error Handling

- 신규 에러 코드 후보
  - `invalid_api_key`
  - `api_key_not_found`
  - `api_key_required`
- 기존 `unauthorized`, `invalid_access_token`, `access_token_expired`와 충돌하지 않게 정리한다.
- 관리 엔드포인트는 인증 실패 시 기존 JWT 에러 체계를 유지한다.

## Validation Checklist

- JWT 로그인 사용자는 기존 Web 흐름을 그대로 사용할 수 있다.
- API key만 가진 MCP 클라이언트가 문서 생성/조회/다운로드/삭제를 수행할 수 있다.
- 원문 API key는 생성 응답 이후 다시 조회되지 않는다.
- DB에는 raw key가 저장되지 않는다.
- OpenAPI와 markdown 문서가 실제 구현과 일치한다.

## Out Of Scope

- API key별 권한 범위
- API key 마지막 사용 시각 저장
- 조직/워크스페이스 단위 key
- 비동기 job 인증 체계
