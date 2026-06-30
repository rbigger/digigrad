# Gradphone — Dependencies & Core-Path Setup

Reference for what Gradphone needs to run, and the minimal "core path" from a
clean machine to a live clone. Generated 2026-06-30 from `pyproject.toml`
(v0.3.0) and the resolved `.venv`.

---

## 1. System / runtime prerequisites

| Dependency | Why | How it's obtained |
|---|---|---|
| macOS or Linux (Windows = WSL2) | Supported platforms | — |
| git | Clone the repo | Pre-installed / OS pkg mgr |
| **Python 3.12** (exactly; `>=3.12,<3.13`) | Runtime | `setup.sh` → `brew install python@3.12` (or OS pkg mgr) |
| **ffmpeg** | Transcode Telegram voice notes | `setup.sh` (OS pkg mgr, with confirm) |
| **cloudflared** | Public tunnel so Twilio can reach you | `setup.sh` → downloaded project-local into `.tools/` (no system change) |
| A phone that receives SMS | One-time Twilio verification | — |

## 2. Python dependencies (declared — `pyproject.toml`)

14 direct dependencies; role of each:

| Package | Role in the core path |
|---|---|
| fastapi | The bridge HTTP/WS service (port 8082) |
| uvicorn[standard] | ASGI server that runs the bridge |
| twilio | Phone calls + Media Streams |
| websockets | Streams call audio (Twilio Media Streams) |
| python-telegram-bot | The Telegram chat interface / commands |
| sqlalchemy[asyncio] | ORM over the tenant database |
| aiosqlite | Async SQLite driver (default local DB) |
| alembic | DB schema migrations (`alembic.ini`, `migrations/`) |
| psycopg[binary] | PostgreSQL driver (alternate/prod DB option) |
| python-dotenv | Loads `.env` config |
| jinja2 | Templates (operator switchboard web UI) |
| itsdangerous | Signs the bridge session cookie |
| python-multipart | Form/multipart handling on the bridge |
| linkup-sdk | Optional live web search on calls |
| aiohttp | Async HTTP client (service calls) |

**Pulled in transitively but core to the product:**

| Package | Role |
|---|---|
| **gradbot** (PyPI) | The voice pipeline: STT → LLM → TTS orchestration |
| **gradium** | Voice cloning + STT + TTS SDK (the "sounds like you" engine) |
| numpy | Audio sample processing |
| pydantic / pydantic-settings | Config + request models |
| starlette | ASGI framework under FastAPI |

Full resolved set: **53 packages** (`/.venv`; see `pip freeze`).

## 3. External services / API keys (accounts you create)

**Required**

| Service | Keys (`.env`) | Purpose |
|---|---|---|
| Gradium | `GRADIUM_API_KEY`, `AGENT_VOICE_ID` | Voice clone, STT, TTS |
| LLM (OpenAI-compatible) | `OPENAI_API_KEY` (+ `LLM_BASE_URL`, `LLM_MODEL`) | The "brain" |
| Telegram | `TELEGRAM_BOT_TOKEN` (@BotFather), `ALLOWED_TELEGRAM_IDS` (@userinfobot) | Chat interface; fails closed |
| Twilio | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` | Phone calls in/out |

**Optional add-ons**

| Service | Keys | Purpose |
|---|---|---|
| Linkup | `LINKUP_API_KEY` | Live web search on calls |
| Gmail | `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD` | "Summarize my emails" |
| Google Places | `GOOGLE_PLACES_API_KEY` | Look up a business to call |

**Auto-generated / set by the scripts (do not edit):**
`BRIDGE_API_KEY` (setup.sh), local-dev defaults
(`TWILIO_MACHINE_DETECTION=Disable`, `ENABLE_INBOUND=true`,
`ALLOW_ARBITRARY_OUTBOUND=true`), and `PUBLIC_HTTP_URL`/`PUBLIC_WS_URL`
(run_local.sh, from the tunnel).

---

## 4. Core path — clean machine → live clone

```
1. git clone <your-fork>/digigrad && cd digigrad
2. scripts/setup.sh            # Python 3.12 + ffmpeg + cloudflared,
                               # .venv + deps, scaffolds .env (+ BRIDGE_API_KEY)
3. Edit .env                   # paste the 4 required services' keys (§3)
4. scripts/run_local.sh        # tunnel up → write PUBLIC_* → point Twilio
                               # webhook → start bridge + bot.  Leave running.
5. curl http://localhost:8082/healthz     # {"status":"ok",...}
6. Telegram: /start → /register → Share my number → send a 15-30s voice note
   → "clone my voice".  Then text it, send a voice note, or /callme.
```

Stop: Ctrl-C in the `run_local.sh` terminal. Cleanup: `/clear_voice` in
Telegram and rotate any handed-to-you keys.

## 5. Process / port map

| Process | Command | Port |
|---|---|---|
| bridge (Twilio + internal API) | `uvicorn gradphone.bridge:app` | 8082 |
| Telegram bot | `python -m gradphone.bot` | — (long-poll) |
| tunnel | `cloudflared tunnel --url http://localhost:8082` | public HTTPS/WSS |
