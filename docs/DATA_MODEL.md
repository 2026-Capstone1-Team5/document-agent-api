# Data Model

## Overview

- Current persistence uses three tables:
  - `users`
  - `user_api_keys`
  - `documents`
  - `document_results`
- The document domain still centers on `documents` and `document_results`.
- `users` exists to support authentication, ownership, and API key issuance.

## `users`

- Purpose:
  - application user account
  - JWT identity subject
  - document owner
- Columns:
  - `id`
  - `email`
  - `password_hash`
  - `created_at`
  - `updated_at`
- Rules:
  - `email` is unique

## `user_api_keys`

- Purpose:
  - named long-lived credentials for MCP or agent clients
- Columns:
  - `id`
  - `user_id`
  - `name`
  - `key_hash`
  - `key_prefix`
  - `created_at`
- Rules:
  - belongs to one `users` row
  - raw API key is never stored
  - `key_hash` is unique
  - `name` is unique per user

## `documents`

- Purpose:
  - metadata and ownership for one successfully parsed source document
- Columns:
  - `id`
  - `owner_user_id`
  - `source_object_key`
  - `filename`
  - `content_type`
  - `file_data`
  - `created_at`
  - `updated_at`
- Rules:
  - belongs to one `users` row when owner exists
  - source payload may be stored in object storage via `source_object_key`

## `document_results`

- Purpose:
  - canonical parse outputs for one document
- Columns:
  - `document_id`
  - `markdown`
  - `canonical_json`
  - `markdown_object_key`
  - `canonical_json_object_key`
  - `created_at`
  - `updated_at`
- Rules:
  - one-to-one with `documents`
  - result payload may be stored inline or in object storage

## Relationships

- `users.id` -> `documents.owner_user_id`
- `users.id` -> `user_api_keys.user_id`
- `documents.id` -> `document_results.document_id`

## API Key Storage Rule

- Server-generated API key lifecycle:
  - generate raw key once
  - return raw key only in issue response
  - persist only `key_hash`, `key_prefix`, and `created_at`
  - delete one `user_api_keys` row on revoke
