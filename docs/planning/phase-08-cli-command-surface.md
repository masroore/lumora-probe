# Phase 08 CLI Command Surface

The `lumora` CLI is a client of the live `/api/v1` surface. It does not construct a
second application runtime, event bus, or SQLite writer.

| Command | Mode | API call / local input |
|---|---|---|
| `lumora health` | Live | `GET /api/v1/health` |
| `lumora captures list` | Live | `GET /api/v1/captures` |
| `lumora capture inspect PATH` | Offline | Reads `manifest.json` from a capture directory or `.lpcap` archive |

`--server` selects the live API base URL and defaults to `http://127.0.0.1:8000`.
Offline inspection never contacts the server and does not initialize application
services. Live commands return JSON for automation and exit non-zero on transport or
response-shape errors.
