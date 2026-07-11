import os
import uuid
import hashlib

from pathlib import Path
from typing import Any, Callable, Optional

from deepwrap.core import SessionManager, Auth
from deepwrap.api import ChatsAPI, FilesAPI, PowAPI
from deepwrap.api.chat_session import ChatSession
from deepwrap.utils.config_store import ConfigStore
from deepwrap.utils.bearer_token_extractor import BearerTokenExtractor
from deepwrap.native_tools import NativeTools
from deepwrap.function_calling import Tool
from deepwrap.memory import MemoryStore
from deepwrap.project_intelligence import ProjectIntelligence

class Client:
    """
    Public DeepWrap client.

    This is the main user-facing entrypoint. It exposes:
        - chats:     low-level chat session API
        - pow:       low-level proof-of-work API

    If `api_key` is omitted, the client attempts to load it from:
        - DEEPWRAP_API_KEY
        - DEEPSEEK_API_KEY
    """

    def __init__(
        self, 
        api_key: Optional[str] = None,
        allow_browser_auth: bool = False,
        auth_timeout: Optional[int] = None,
        agent_mode: bool = True,
        working_directory: Optional[str | Path] = None,
        command_timeout: float = 30.0,
        max_agent_rounds: int = 8,
        memory_enabled: bool = True,
        memory_path: Optional[str | Path] = None,
        memory_namespace: str = "default",
        resume_session_id: Optional[str] = None,
    ) -> None:
        """
        Initialize the public client.

        Args:
            api_key:
                Optional bearer token. If omitted, the token is loaded from the
                environment.

            allow_browser_auth:
                If True, the client will attempt browser-based authentication if no API key is provided or found in the environment.

            auth_timeout:
                Optional timeout for the authentication process.
        """

        self.auth = Auth()
        self.agent_mode = agent_mode
        self.max_agent_rounds = max_agent_rounds
        self.native_tools = NativeTools(
            working_directory=working_directory,
            timeout=command_timeout,
        )
        self._custom_tools: dict[str, tuple[Tool, Callable[..., Any]]] = {}
        self.memory = (
            MemoryStore(
                memory_path or (ConfigStore().path.parent / "memory.db"),
                namespace=memory_namespace,
            )
            if memory_enabled
            else None
        )
        project_root = self.native_tools.working_directory
        project_key = hashlib.sha256(str(project_root).encode()).hexdigest()[:16]
        self.project = ProjectIntelligence(
            project_root,
            ConfigStore().path.parent / "projects" / f"{project_key}.json",
        )

        self._resume_session_id = resume_session_id
        self._resume_claimed = False

        bearer_token = self._resolve_token(
            api_key            = api_key,
            allow_browser_auth = allow_browser_auth,
            auth_timeout       = auth_timeout,
        )

        self.session       = SessionManager(bearer_token = bearer_token)
        self.pow           = PowAPI(self)
        self.files         = FilesAPI(self)
        self.chats         = ChatsAPI(self)

        self._conversations: dict[str, ChatSession] = {}
        self._responses: dict[str, str]             = {}

    def register_tool(
        self,
        tool: Tool,
        function: Callable[..., Any],
        *,
        replace: bool = False,
    ) -> None:
        """Register an application-specific tool in the default agent loop."""

        native_names = set(self.native_tools.functions)
        if tool.name in native_names:
            raise ValueError(f"Cannot replace native tool: {tool.name}")
        if tool.name in self._custom_tools and not replace:
            raise ValueError(f"Tool is already registered: {tool.name}")
        self._custom_tools[tool.name] = (tool, function)

    @property
    def agent_tools(self) -> tuple[Tool, ...]:
        memory_tools = self.memory.definitions if self.memory is not None else ()
        return self.native_tools.definitions + memory_tools + self.project.definitions + tuple(
            item[0] for item in self._custom_tools.values()
        )

    @property
    def agent_functions(self) -> dict[str, Callable[..., Any]]:
        functions = dict(self.native_tools.functions)
        if self.memory is not None:
            functions.update(self.memory.functions)
        functions.update(self.project.functions)
        functions.update(
            {name: item[1] for name, item in self._custom_tools.items()}
        )
        return functions

    def _claim_memory_session(self, model: str) -> Optional[str]:
        if self.memory is None:
            return None
        if self._resume_session_id and not self._resume_claimed:
            self.memory.session_context(self._resume_session_id, limit=1)
            self._resume_claimed = True
            return self._resume_session_id
        return self.memory.create_session(model=model)

    def memory_context(self, query: str, session_id: Optional[str]) -> str:
        if self.memory is None:
            return ""
        sections: list[str] = []
        if session_id:
            context = self.memory.session_context(session_id, limit=20)
            if context:
                sections.append("[RESUMED SESSION]\n" + context)
        recalled = self.memory.recall(query, limit=8)
        if recalled:
            sections.append(
                "[RELEVANT LONG-TERM MEMORY]\n"
                + "\n".join(f"- ({item['id']}) {item['content']}" for item in recalled)
            )
        return "\n\n".join(sections)


    @classmethod
    def from_browser_auth(
        cls,
        *,
        timeout: Optional[int] = None,
    ) -> "Client":
        """
        Create a client by authenticating through the browser.
        """

        return cls(
            allow_browser_auth=True,
            auth_timeout=timeout,
        )


    @classmethod
    def _resolve_token(
        cls,
        api_key: Optional[str],
        allow_browser_auth: bool,
        auth_timeout: Optional[int],
    ) -> str:
        """
        Resolve the bearer token to use for authentication.
        The resolution order is as follows:
            1. Explicit `api_key` argument.
            2. Environment variables `DEEPWRAP_API_KEY` or `DEEPSEEK_API_KEY`.
            3. Browser authentication (if `allow_browser_auth` is True).
        Args:
            api_key:
                Optional explicit API key.

            allow_browser_auth:
                Whether to allow browser authentication if no API key is provided.

            auth_timeout:
                Optional timeout for the browser authentication process.
        
        Returns:
            The resolved bearer token.
        
        Raises:
            ValueError:
                If no API key is found and browser authentication is not allowed or fails.
        """

        bearer_token = (
            api_key
            or os.getenv("DEEPWRAP_API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
        )

        if bearer_token:
            return BearerTokenExtractor.normalize_token(bearer_token)
        
        config = ConfigStore().load()

        if config.token:
            return BearerTokenExtractor.normalize_token(config.token)

        if not allow_browser_auth:
            raise ValueError(
                "Missing API key. Pass api_key=..., set DEEPWRAP_API_KEY, "
                "or use Client.from_browser_auth()."
            )

        token = Auth().browser(timeout = auth_timeout)

        if not token:
            raise ValueError(
                "Browser authentication failed: bearer token was not captured."
            )

        return BearerTokenExtractor.normalize_token(token)

    def _create_conversation(self, model: str) -> tuple[str, ChatSession]:
        """
        Create and register a new conversation.

        Args:
            model:
                The model to bind to the newly created chat session.

        Returns:
            A tuple of `(conversation_id, chat_session)`.
        """

        conversation_id = f"conv_{uuid.uuid4().hex}"
        chat            = self.chats.create_session(model = model)

        self._conversations[conversation_id] = chat

        return conversation_id, chat

    def _resolve_conversation(
        self,
        model: str,
        conversation_id: Optional[str] = None,
        previous_response_id: Optional[str] = None,
    ) -> tuple[str, ChatSession]:
        """
        Resolve or create the chat session used for a response request.

        Args:
            model:
                The requested model.

            conversation_id:
                Optional explicit conversation identifier.

            previous_response_id:
                Optional previously returned response ID. If provided, the
                conversation linked to that response is reused.

        Returns:
            A tuple of `(conversation_id, chat_session)`.

        Raises:
            ValueError:
                If an unknown conversation or response ID is provided.
        """

        if previous_response_id is not None:
            conversation_id = self._responses.get(previous_response_id)

            if conversation_id is None:
                raise ValueError(
                    f"Unknown previous_response_id: {previous_response_id}"
                )

        if conversation_id is not None:
            chat = self._conversations.get(conversation_id)

            if chat is None:
                raise ValueError(f"Unknown conversation_id: {conversation_id}")

            if chat.model_type != model:
                raise ValueError(
                    "Model mismatch for existing conversation. "
                    f"Expected '{chat.model_type}', got '{model}'."
                )

            return conversation_id, chat

        return self._create_conversation(model)

    def _register_response(self, response_id: str, conversation_id: str) -> None:
        """
        Register a response ID under a conversation ID.

        Args:
            response_id:
                The locally generated response identifier.

            conversation_id:
                The conversation the response belongs to.
        """

        self._responses[response_id] = conversation_id
