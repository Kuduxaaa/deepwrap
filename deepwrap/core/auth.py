import time
import requests
import websocket

from typing import Optional
from deepwrap.config import Config
from deepwrap.utils.browser_process import BrowserProcess
from deepwrap.utils.port_finder import PortFinder
from deepwrap.utils.cdp_client import CDPClient
from deepwrap.utils.dev_tools_http import DevToolsHTTP
from deepwrap.utils.bearer_token_extractor import BearerTokenExtractor

class BrowserAuthProvider:
    """
    Handles browser-based authentication to obtain a Bearer token.
     - Launches a Chromium-based browser with remote debugging enabled.
     - Waits for the user to complete the login process.
     - Listens for network requests in the browser to extract the Bearer token from the Authorization header.
     - Cleans up the browser process and temporary user data directory after authentication is complete or if a timeout occurs.
    """
    
    def __init__(self, login_url: str, timeout: Optional[int] = None) -> None:
        self.login_url = login_url
        self.timeout = timeout

    def get_bearer_token(self) -> Optional[str]:
        """
        Perform the browser-based authentication flow to obtain a Bearer token.
        
        Returns:
            The obtained Bearer token if authentication is successful, otherwise None.
        """
        
        port = PortFinder.find_free_port()

        browser = BrowserProcess(self.login_url, port)
        client = None

        try:
            browser.start()

            DevToolsHTTP.wait_until_ready(port)
            websocket_url = DevToolsHTTP.get_page_websocket_url(port)

            client = CDPClient(websocket_url)
            client.enable_network()

            started_at = time.time()

            while True:
                if self.timeout is not None and time.time() - started_at > self.timeout:
                    return None

                try:
                    message = client.recv()
                except websocket.WebSocketTimeoutException:
                    continue

                token = BearerTokenExtractor.from_cdp_message(message)

                if token:
                    return token

        finally:
            if client:
                client.close_browser()
                client.close()

            browser.terminate()


class Auth:
    """
    Handles authentication for DeepWrap interactions.

    - Stores a requests.Session instance.
    - Supports browser-based authentication through an installed Chromium browser.
    - Captures Bearer tokens from authenticated browser requests.
    - Applies Authorization header to the session.
    """

    def __init__(self) -> None:
        self._is_authenticated = False
        self.bearer_token: Optional[str] = None

    def is_authed(self) -> bool:
        """
        Check if the session is currently authenticated.
        
        Returns:
            True if authenticated, False otherwise.
        """
        
        return self._is_authenticated

    def browser(
        self,
        timeout: Optional[int] = None,
    ) -> Optional[str]:
        """
        Perform browser-based authentication to obtain a Bearer token.
        
        Args:
            timeout: Optional timeout in seconds for the authentication process. If None, will wait indefinitely.
        
        Returns:
            The obtained Bearer token if authentication is successful, otherwise None.
        """
        
        provider = BrowserAuthProvider(
            login_url = Config.login_url,
            timeout   = timeout,
        )
        

        token = provider.get_bearer_token()

        if not token:
            return None
        
        self._is_authenticated = True

        return token
