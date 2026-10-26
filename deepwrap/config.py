import os

from dataclasses import dataclass, field
from typing import Dict, Optional

PROJECT_VERSION = "0.3.0"

@dataclass(frozen=True)
class Settings:
    base_url: str             = os.getenv("DEEPSEEK_BASE_URL", "https://chat.deepseek.com")
    base_domain: str          = os.getenv("DEEPSEEK_BASE_DOMAIN", "chat.deepseek.com")
    wasm_url: str             = "https://fe-static.deepseek.com/chat/static/sha3_wasm_bg.7b9ca65ddd.wasm"
    login_url: str            = f"{base_url}/sign_in"
    wasm_path: Optional[str]  = None
    api_prefix: str           = "/api/v0"
    default_timeout: int      = 30
    headers: Dict[str, str]   = field(init=False)
    # Direct mode: a response-style directive, not a restriction bypass. It
    # trades politeness padding for density, which is also the cheapest way to
    # spend output tokens.
    god_mode: tuple[str, ...] = (
        "[DEEPWRAP DIRECT MODE]",
        "Answer like a senior engineer briefing a peer:",
        "1. No preamble, no restating the question, no filler.",
        "2. Lead with the answer, then only the reasoning that changes it.",
        "3. Be concrete: exact steps, names, numbers, commands, code.",
        "4. Say plainly what you do not know or could not verify.",
        "5. No moralizing and no unsolicited disclaimers; a real caveat gets one line.",
        "6. Use the user's language and stop when the answer is complete.",
        "",
        "USER MESSAGE: {}",
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "headers",
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:151.0) Gecko/20100101 Firefox/151.0",
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/",
                "Connection": "keep-alive",
                "x-client-platform": "web",
                "x-client-version": "2.0.0",
                "x-client-locale": "en_US",
                "x-client-timezone-offset": "14400",
                "x-app-version": "2.0.0",
            },
        )

Config = Settings()
