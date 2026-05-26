import base64
import json

from typing import TYPE_CHECKING

from .base import BaseAPI
from deepwrap.config import Config
from deepwrap.modules import PowChallenge, ProofOfWorkSolver

if TYPE_CHECKING:
    from deepwrap.client import Client


class PowAPI(BaseAPI):
    """
    Handles proof-of-work challenge retrieval and header construction.
    """

    CREATE_CHALLENGE_ENDPOINT = (
        f"{Config.base_url}{Config.api_prefix}/chat/create_pow_challenge"
    )

    def __init__(self, client: "Client") -> None:
        """
        Initialize the proof-of-work API module.
        """

        super().__init__(client)

        self._solver = ProofOfWorkSolver(wasm_path = Config.wasm_path)
        self._solver.warmup()

    def fetch_challenge(self, target_path: str) -> PowChallenge:
        """
        Fetch a proof-of-work challenge for the given API path.

        Args:
            target_path:
                The API path the challenge is being requested for.

        Returns:
            A parsed `PowChallenge` object.
        """

        resp = self._post(
            self.CREATE_CHALLENGE_ENDPOINT,
            json    = {"target_path": target_path},
            headers = {"content-type": "application/json"},
        )

        resp.raise_for_status()
        payload = resp.json()
        raw     = payload["data"]["biz_data"]["challenge"]

        return PowChallenge(
            algorithm    = raw["algorithm"],
            challenge    = raw["challenge"],
            salt         = raw["salt"],
            signature    = raw["signature"],
            difficulty   = int(raw["difficulty"]),
            expire_at    = int(raw["expire_at"]),
            expire_after = int(raw.get("expire_after", 0)),
            target_path  = raw["target_path"],
        )

    def build_header(self, target_path: str) -> str:
        """
        Build the base64-encoded `x-ds-pow-response` header value.

        Args:
            target_path:
                The API path the PoW response is being built for.

        Returns:
            The base64-encoded header value.
        """

        challenge = self.fetch_challenge(target_path)
        answer    = self._solver.solve(challenge)

        payload = {
            "algorithm":   challenge.algorithm,
            "challenge":   challenge.challenge,
            "salt":        challenge.salt,
            "answer":      answer,
            "signature":   challenge.signature,
            "target_path": target_path,
        }

        return base64.b64encode(
            json.dumps(payload, separators = (",", ":")).encode("utf-8")
        ).decode("ascii")