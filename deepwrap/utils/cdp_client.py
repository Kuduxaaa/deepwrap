import json
import websocket

from typing import Dict, Any, Optional

class CDPClient:
    """
    Simple wrapper around a DevTools Protocol WebSocket connection.
     - Provides methods to send commands and receive responses from the DevTools interface.
     - Manages message IDs and connection lifecycle.
     - Includes convenience methods to enable the Network and Page domains and to close the browser.
    """
    
    def __init__(self, websocket_url: str, timeout: int = 1) -> None:
        self.websocket_url = websocket_url
        self.timeout = timeout
        self.message_id = 0
        self.ws = websocket.create_connection(
            websocket_url,
            timeout=timeout,
            suppress_origin=True,
        )

    def send(self, method: str, params: Optional[Dict[str, Any]] = None) -> int:
        """
        Send a command to the DevTools interface.
        
        Args:
            method (str): The DevTools method to invoke (e.g., "Network.enable").
            params (Optional[Dict[str, Any]]): An optional dictionary of parameters to include with the command.
        
        Returns:
                int: The message ID assigned to this command, which can be used to correlate responses.
        """

        self.message_id += 1

        payload = {
            "id": self.message_id,
            "method": method,
        }

        if params is not None:
            payload["params"] = params

        self.ws.send(json.dumps(payload))
        return self.message_id

    def recv(self) -> Dict[str, Any]:
        """
        Receive a message from the DevTools interface and parse it as JSON.
        """
        
        return json.loads(self.ws.recv())

    def enable_network(self) -> None:
        """
        Convenience method to enable the Network domain.
        """
        
        self.send("Network.enable")
        self.send("Page.enable")

    def close_browser(self) -> None:
        """
        Send the command to close the browser window.
        """
        
        try:
            self.send("Browser.close")
        except Exception:
            pass

    def close(self) -> None:
        """
        Close the WebSocket connection.
        """
        
        try:
            self.ws.close()
        except Exception:
            pass