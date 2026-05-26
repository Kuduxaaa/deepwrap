from typing import Any, Dict, Optional

class BearerTokenExtractor:
    """
    Utility class to extract bearer tokens from CDP messages.
    """
    
    @staticmethod
    def from_headers(headers: Optional[Dict[str, Any]]) -> Optional[str]:
        """
        Extract a bearer token from the given headers dictionary.
        
        Args:
            headers (Optional[Dict[str, Any]]): A dictionary of HTTP headers.

        Returns:
            Optional[str]: The extracted bearer token if found, otherwise None.
        """

        if not headers:
            return None

        for key, value in headers.items():
            if key.lower() != "authorization":
                continue

            value = str(value)

            if value.lower().startswith("bearer "):
                return value.split(" ", 1)[1]

        return None

    @classmethod
    def from_cdp_message(cls, message: Dict[str, Any]) -> Optional[str]:
        """
        Extract a bearer token from a CDP message if it contains relevant network request information.
        
        Args:
            message (Dict[str, Any]): A CDP message represented as a dictionary.
        
        Returns:
            Optional[str]: The extracted bearer token if found, otherwise None.
        """
        
        method = message.get("method")
        params = message.get("params", {})

        if method == "Network.requestWillBeSent":
            request = params.get("request", {})
            return cls.from_headers(request.get("headers", {}))

        if method == "Network.requestWillBeSentExtraInfo":
            return cls.from_headers(params.get("headers", {}))

        return None


    @staticmethod
    def normalize_token(token: str) -> str:
        """
        Normalize a bearer token by stripping whitespace and removing the "Bearer " prefix if present.

        Args:
            token: The raw bearer token string.
        
        Returns: 
            The normalized bearer token.
        
        Raises: 
            ValueError if the token is empty after normalization.
        """

        token = token.strip()

        if token.lower().startswith("bearer "):
            token = token[7:].strip()

        if not token:
            raise ValueError("API key cannot be empty.")

        return token