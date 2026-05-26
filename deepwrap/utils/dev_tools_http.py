import time
import json
import urllib.request

from typing import Dict, Any

class DevToolsHTTP:
    """
    Utility class for interacting with the DevTools HTTP endpoints.
     - Provides methods to wait for the DevTools endpoint to become ready and to retrieve the WebSocket URL for page targets.
     - Uses simple polling with a timeout to handle cases where the browser process may take time to initialize the DevTools interface.
    """
    
    @staticmethod
    def get_json(url: str, timeout: int = 2) -> Any:
        """
        Helper method to perform a GET request and parse the response as JSON.
        
        Args:
            url (str): The URL to send the GET request to.
            timeout (int): The timeout in seconds for the HTTP request.
        
        Returns:
            Any: The parsed JSON response.
        
        Raises:
            Exception: If the HTTP request fails or the response is not valid JSON.
        """
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    @classmethod
    def wait_until_ready(cls, port: int, timeout: int = 15) -> Dict[str, Any]:
        """
        Wait until the DevTools HTTP endpoint is ready by polling the /json/version endpoint.
        
        Args:
            port (int): The port number where the DevTools HTTP endpoint is expected to be available.
            timeout (int): The maximum time in seconds to wait for the endpoint to become ready.
        
        Returns:
            Dict[str, Any]: The parsed JSON response from the /json/version endpoint once it becomes
            
        Raises:            
            Exception: If the endpoint does not become ready within the specified timeout.
        """

        deadline = time.time() + timeout

        while time.time() < deadline:
            try:
                return cls.get_json(f"http://127.0.0.1:{port}/json/version")
            
            except Exception:
                time.sleep(0.2)

        raise Exception("DevTools endpoint did not become ready in time.")

    @classmethod
    def get_page_websocket_url(cls, port: int, timeout: int = 15) -> str:
        """
        Retrieve the WebSocket URL for the first page target from the DevTools HTTP endpoint.
        
        Args:
            port (int): The port number where the DevTools HTTP endpoint is expected to be available.
            timeout (int): The maximum time in seconds to wait for a page target to become available.
            
        Returns:
            str: The WebSocket URL for the first page target.
            
        Raises:
            Exception: If no page target with a WebSocket URL is found within the specified timeout.
        """
        
        deadline = time.time() + timeout

        while time.time() < deadline:
            try:
                targets = cls.get_json(f"http://127.0.0.1:{port}/json")

                for target in targets:
                    if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
                        return target["webSocketDebuggerUrl"]

            except Exception:
                pass

            time.sleep(0.2)

        raise Exception("Could not find page WebSocket endpoint.")