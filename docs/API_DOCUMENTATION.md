# API Documentation

*Lists implemented endpoints only. Last updated: Stage 1.*
The planned API is in [STAGE0_PLAN.md §7](STAGE0_PLAN.md#7-api-design).

## Conventions

- Base URL: `http://127.0.0.1:<port>`. The port is chosen at each launch.
- Authentication: every `/api` request must include `X-PowerShift-Token: <token>` when the backend was started with `--token` (the desktop app always does this).
- JSON request and response bodies.

### Error format

All errors share one shape:

```json
{ "error": { "code": "validation_error", "message": "Some values are invalid.", "fields": { "name": "Field required" } } }
```

| Status | `code` | When |
|---|---|---|
| 401 | `unauthorized` | Token missing or wrong |
| 404 | `not_found` | Unknown route or record |
| 405 | `method_not_allowed` | Wrong HTTP method |
| 409 | `conflict` | Request conflicts with current data |
| 422 | `validation_error` | Invalid input; `fields` maps field → message |
| 500 | `internal_error` | Unexpected error (details only in the local log) |

## Endpoints

### `GET /api/health`

Used by the app to confirm the backend and database work.

Response `200`:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "schema_revision": "0001",
  "database_path": "C:\\...\\powershift.db"
}
```
