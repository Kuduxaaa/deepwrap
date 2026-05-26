from typing import TYPE_CHECKING, Optional

from .base import BaseAPI
from .chat_session import ChatSession

from deepwrap.config import Config

if TYPE_CHECKING:
    from deepwrap.client import Client


class ChatsAPI(BaseAPI):
    """
    Handles low-level chat session creation.

    This module is responsible for creating server-side chat sessions and
    returning `ChatSession` objects that can be used for multi-turn streaming
    interactions.
    """

    SUPPORTED_MODELS = {
        "expert",
        "default",
        "vision",
    }

    CREATE_SESSION_ENDPOINT = (
        f"{Config.base_url}{Config.api_prefix}/chat_session/create"
    )

    def __init__(self, client: "Client", model: str = "expert") -> None:
        """
        Initialize the chat API module.

        Args:
            client:
                The root client instance.

            model:
                Default model used when `create_session()` is called without an
                explicit model override.

        Raises:
            ValueError:
                If the provided default model is not supported.
        """

        super().__init__(client)

        if model not in self.SUPPORTED_MODELS:
            raise ValueError(f"Unsupported model: {model}")

        self.model_type = model

    def create_session(self, model: Optional[str] = None, god_mode: bool = False) -> ChatSession:
        """
        Create a new chat session.

        Args:
            model:
                Optional model override for the new session.
            
            god_mode:
                Whether to enable god mode for this session.

        Returns:
            A `ChatSession` object bound to the created server-side session.

        Raises:
            ValueError:
                If the resolved model is not supported.

            RuntimeError:
                If the API returns a non-zero response code.
        """

        model_type = model if model is not None else self.model_type

        if model_type not in self.SUPPORTED_MODELS:
            raise ValueError(f"Unsupported model: {model_type}")

        resp = self._post(
            self.CREATE_SESSION_ENDPOINT,
            headers = {"content-type": "application/json"},
            json    = {},
        )

        resp.raise_for_status()
        payload = resp.json()

        if payload.get("code") != 0:
            raise RuntimeError(f"create_session failed: {payload}")

        session_id = payload["data"]["biz_data"]["chat_session"]["id"]

        return ChatSession(
            client     = self._client,
            session_id = session_id,
            model_type = model_type,
            god_mode   = god_mode,
        )