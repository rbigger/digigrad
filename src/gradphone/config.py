from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _req(name: str) -> str:
    """Read a required env var, failing fast with a clear, actionable message.

    Same fail-on-startup behavior as before, but a missing/empty value now
    raises a readable RuntimeError naming the variable instead of a cryptic
    ``KeyError: 'AGENT_VOICE_ID'`` from deep in an import.
    """
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(
            f"Missing required environment variable {name!r}. "
            "Set it in your .env (see .env.example) and restart."
        )
    return val


@dataclass(frozen=True)
class Config:
    gradium_api_key: str = field(default_factory=lambda: _req("GRADIUM_API_KEY"))
    # No hardcoded default: a real voice UID is account-scoped, so baking one in
    # would ship the original author's clone with every fork. Set it in .env.
    agent_voice_id: str = field(default_factory=lambda: _req("AGENT_VOICE_ID"))

    twilio_account_sid: str = field(default_factory=lambda: _req("TWILIO_ACCOUNT_SID"))
    twilio_auth_token: str = field(default_factory=lambda: os.environ.get("TWILIO_AUTH_TOKEN", ""))
    twilio_phone_number: str = field(default_factory=lambda: _req("TWILIO_PHONE_NUMBER"))


cfg = Config()
