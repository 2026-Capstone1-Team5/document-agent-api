# API Spec

## Base

- Base path: `/api/v1`
- Content types:
  - auth: `application/json`
  - document upload: `multipart/form-data`
  - document download: `text/markdown`, `application/json`

## Authentication

### JWT bearer

- Header: `Authorization: Bearer <access-token>`
- Used by:
  - `POST /auth/register`
  - `POST /auth/login`
  - `GET /auth/me`
  - `GET|POST /auth/api-keys`
  - `PATCH /auth/api-keys/{api_key_id}`
  - `DELETE /auth/api-keys/{api_key_id}`
  - all document endpoints

### API key

- Headers:
  - `X-API-Key: <api-key>`
  - or `Authorization: Bearer <api-key>`
- Used by:
  - all document endpoints
- Not accepted by:
  - `GET /auth/me`
  - `GET|POST /auth/api-keys`
  - `PATCH /auth/api-keys/{api_key_id}`
  - `DELETE /auth/api-keys/{api_key_id}`

## Auth Endpoints

### `POST /auth/register`

- Create user and return bearer access token.

### `POST /auth/login`

- Authenticate user and return bearer access token.

### `GET /auth/me`

- Return current authenticated user profile.
- Requires JWT bearer token.

### `GET /auth/api-keys`

- Return current user's API key list.
- Each item contains:
  - `id`
  - `name`
  - `prefix`
  - `createdAt`
- Raw API key is never returned by list endpoints.

### `POST /auth/api-keys`

- Issue a new named API key for the current user.
- Request body fields:
  - `name`
- Response fields:
  - `apiKey`
  - `key.id`
  - `key.name`
  - `key.prefix`
  - `key.createdAt`

### `DELETE /auth/api-keys/{api_key_id}`

- Revoke one API key owned by the current user.
- Returns `204 No Content`.

### `PATCH /auth/api-keys/{api_key_id}`

- Rename one API key owned by the current user.
- Request body fields:
  - `name`
- Response fields:
  - `id`
  - `name`
  - `prefix`
  - `createdAt`

## Document Endpoints

### `POST /documents`

- Upload a supported file and synchronously persist a parsed document result.
- Supported file families:
  - PDF
  - HWP/HWPX
  - image formats accepted by current router rules
- Requires JWT or API key.

### `GET /documents`

- Return paginated documents owned by the authenticated user.
- Query params:
  - `limit`
  - `offset`
  - `filename`
- Requires JWT or API key.

### `GET /documents/{document_id}`

- Return document metadata for one owned document.
- Requires JWT or API key.

### `GET /documents/{document_id}/result`

- Return stored parse result for one owned document.
- Requires JWT or API key.

### `GET /documents/{document_id}/download?format=markdown|json`

- Download markdown or canonical JSON result.
- Requires JWT or API key.

### `DELETE /documents/{document_id}`

- Delete one owned document and associated result.
- Requires JWT or API key.

## Error Shape

- All structured API errors use:

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {}
  }
}
```

## Auth Error Codes

- `unauthorized`
- `invalid_access_token`
- `access_token_expired`
- `invalid_credentials`
- `invalid_api_key`
- `invalid_api_key_name`
- `api_key_name_already_exists`
- `api_key_not_found`
- `email_already_exists`
- `invalid_email_format`

## Document Error Codes

- `missing_filename`
- `empty_file`
- `unsupported_file_type`
- `malformed_multipart_request`
- `document_not_found`
- `unsupported_download_format`
