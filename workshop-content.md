# Everyone Should Build a Digital Clone

AI Engineer 2026 · Everybody Gets a Digital Clone!

Review outline for the team: the full arc and context of the workshop, in short. This will be fleshed out into the final script later. `[VIDEO: ...]` marks a short how-to clip to record.

---

## Part 0 — Open

- Hook: build a voice clone of yourself that runs on your own laptop. No hosting. Text it, send voice notes, and call a real number where your own voice answers.
- The big idea (the slide to photograph): everyone should build a digital clone. It doesn't have to be a heavy platform like openclaw. Small enough to own, real enough to act in your voice (call a restaurant, brief your day).
- Line to land: the clone that does one real task beats the platform you never finish setting up.

## Part 1 — Get your clone running

Goal: everyone's clone replies in their own voice and calls their phone.

- Clone the repo, run `setup.sh`. Installs in the background, writes a starter `.env`.
- Collect keys:
  - You make these: Telegram bot token (BotFather), your Telegram ID (@userinfobot), Gradium key, Gradium voice id, OpenAI key. `[VIDEO: one per key]`
  - We hand you: Twilio account SID, auth token, phone number. `[Twilio handout method: TBD]`
  - Auto-set by `setup.sh`: `BRIDGE_API_KEY` (generated) plus the local-dev flags `ENABLE_INBOUND`, `ALLOW_ARBITRARY_OUTBOUND`, `TWILIO_MACHINE_DETECTION`.
  - `GRADIUM_BASE_URL`: leave blank, it defaults to the public Gradium host.
  - Two gotchas: `AGENT_VOICE_ID` is required (app won't start without it); your `ALLOWED_TELEGRAM_IDS` must include you (or the bot ignores everyone).
- Paste keys into `.env`.
- Run `run_local.sh`: opens a tunnel, connects your number, starts the app. Confirm with `/healthz`.
- In Telegram: `/register`, share your number, send a 10 to 12 second voice note, consent to clone, `/voice` to confirm, then `/callme` to get a call. `[VIDEO: a good voice sample]`

## Part 2 — How it works (in the code)

Theme: it stays small and readable (not openclaw), but it still acts.

### What happens when you call your agent

The flow when someone dials your Twilio number (accurate to `src/gradphone/bridge.py`):

```
📞  You call your agent
    (your Twilio number)
         │
         ▼
   ┌──────────┐    incoming call
   │ ☎️ Twilio │────────────────────►  POST /twilio/voice   (through your tunnel)
   └──────────┘                              │
                                             ▼
              ┌────────────────────────────────────────────────────┐
              │  🖥️  bridge.py   (running on your laptop)            │
              │                                                     │
              │  1. check it's really Twilio (signed request)       │
              │  2. who's calling?  → caller ID = identity          │
              │       • it's you      → assistant                   │
              │                         (your cloned voice,         │
              │                          your memory, all tools)    │
              │       • someone else  → receptionist                │
              │                         (take a message only)       │
              │  3. answer with <Connect><Stream> → open audio link │
              └────────────────────────────────────────────────────┘
                                             │
         ┌───────────────────────────────────┘
         ▼   Twilio opens a 2-way audio stream   (WS /twilio/stream · 8 kHz μ-law)
   ┌──────────────────────────────────────────────────────────────┐
   │  🎧  the live call loop   (gradbot.run)                        │
   │                                                               │
   │   you talk ─► 🎙️ Gradium STT ─► 🧠 OpenAI LLM ─► 🔊 Gradium TTS │
   │               speech → text      picks tools      your voice   │
   │                                      │  ▲            │         │
   │                                      ▼  │            └─► back   │
   │                                  ⇅ tools                to you  │
   │             assistant: remember · web search ·                 │
   │                        find + call a business ·                │
   │                        email summary · hang up                 │
   │             receptionist: take a message · hang up             │
   └──────────────────────────────────────────────────────────────┘
         │
         ▼   when the call ends
   📝 transcript + 🎚️ recording saved · 🧠 new memories extracted · 💬 Telegram summary sent to you
```

Details worth calling out: inbound only answers if `ENABLE_INBOUND` is on (otherwise it politely declines), caller ID is the identity check (`get_tenant_by_phone`), the wire audio is 8 kHz μ-law, and there's a voicemail branch if a machine answers.

- It acts through tools: the model calls functions (remember/recall, web search, find + call a business, summarize email, hang up). That's what makes it an assistant, not just a voice.
- Same number, different caller: you get the full assistant; a stranger gets a receptionist that can only take a message. Trust is decided in one `mode` branch that picks both prompt and tools:

```
# bridge.py — _make_session_config()
if mode == "assistant":
    instructions = build_assistant_prompt(spec, memory_digest=memory_digest)
    tools = _assistant_tool_defs()      # memory, web search, find + call a business, email, hang up
elif mode == "receptionist":
    owner = os.environ.get("OPERATOR_NAME", "").strip()
    instructions = build_receptionist_prompt(spec, owner_name=owner)
    tools = _receptionist_tool_defs()   # take a message, hang up — nothing else
else:
    instructions = build_business_prompt(spec, opener_already_spoken=False)
    tools = _tool_defs()                # outbound business-call tools

return gradbot.SessionConfig(voice_id=voice_id, instructions=instructions,
                             language=lang, tools=tools, ...)
```

  There's no path where a stranger gets your tools, because the tools are chosen here, once, from who's calling.
- Why it's light: a call is just speech in, model, speech out. Gradbot runs that loop (audio, speech, model, talking over each other) and you drive it with a handful of objects. That's why it fits on a laptop.
- What makes it yours: memory (facts it remembers and reuses) plus your cloned voice.

### Voice agent concepts worth knowing

The vocabulary for building voice agents. Gradbot handles most of this for us, but everyone should walk out knowing the terms.

- Cascaded pipeline: speech to text, then the model, then text to speech, chained together. Every stage is inspectable and swappable. This is what gradphone uses.
- Speech to speech (end to end): one model takes audio in and gives audio out. Fewer moving parts, but less to inspect and tune. The other main approach.
- Half duplex (walkie-talkie): one side talks at a time, you wait your turn. Phone lines are half duplex by nature.
- Full duplex: both sides can talk at once, like a real conversation. The feel we want, even over a half-duplex line.
- VAD (voice activity detection): telling when someone is actually speaking versus silence.
- Endpointing / turn detection: deciding when the caller has finished their turn so the agent can reply. Too eager and it cuts you off, too slow and it feels laggy.
- Barge-in: letting the caller interrupt while the agent is talking. The agent stops and listens. This is what makes a half-duplex line feel full duplex.
- Turn-taking: the whole dance of who speaks when, built from VAD, endpointing, barge-in, and silence handling.
- Fillers: a short "let me see" so the line isn't dead while the model thinks.
- When latency matters: on a live call it really does, silence feels like a dropped call, so we stream everything. Off the call (a voice note, a translation) nobody is waiting, so we optimize for quality instead.
- Time to first audio: how long from the end of your turn to the first sound coming back. This is the thing people actually feel as fast or slow.
- Wire format: phone audio is 8 kHz μ-law (G.711). Mismatched sample rates are usually why audio sounds too fast or too slow.

## Part 3 — Take it home

- Optional keys to unlock more, each one a tool the agent gains when the key is present:
  - `LINKUP_API_KEY` → live web search on calls.
  - `GMAIL_ADDRESS` + `GMAIL_APP_PASSWORD` → "summarize my emails."
  - `GOOGLE_PLACES_API_KEY` → find a business and call it for you (the `find_business` tool only appears when this is set).
  - `[VIDEO: one per key]`
- Keep building on your running base with Claude Code or codex.
- Cleanup: stop everything with Ctrl-C in `run_local.sh`, drop your voice clone with `/clear_voice`, delete the call recordings, and rotate any handed-out keys (mainly Twilio).

## Appendix

- Troubleshooting table: won't start, bot ignores you, no call comes through, audio sounds off, etc.
- Sources and links.
