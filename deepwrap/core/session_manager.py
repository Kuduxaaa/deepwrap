import requests

from typing import Optional
from deepwrap.config import Config

class SessionManager:
    """
    Manages HTTP sessions with appropriate headers and cookies for DeepSeek interactions.
     - Initializes a requests.Session with default headers from Config.
     - Allows setting of authorization header using a bearer token.
     - Supports adding cookies to the session for domain-specific interactions.
     - Provides get and post methods that automatically include default timeouts.
    """
    
    def __init__(self, bearer_token: str, cookies: Optional[dict[str, str]] = None) -> None:
        self.session = requests.Session()
        self.session.headers.update(Config.headers)
        self.session.headers["authorization"] = f"Bearer {bearer_token}"

        if cookies:
            for name, value in cookies.items():
                self.session.cookies.set(name, value, domain = Config.base_domain)

    def get(self, url: str, **kwargs) -> requests.Response:
        """
        Wrapper around requests.Session.get that applies default timeout and any additional kwargs.
        
        Args:
            url (str): The URL to send the GET request to.
            **kwargs: Additional keyword arguments to pass to requests.Session.get.
            
        Returns:
            requests.Response: The response object resulting from the GET request.
        """
        
        kwargs.setdefault("timeout", Config.default_timeout)
        
        return self.session.get(url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        """
        Wrapper around requests.Session.post that applies default timeout and any additional kwargs.

        Args:
            url (str): The URL to send the POST request to.
            **kwargs: Additional keyword arguments to pass to requests.Session.post.

        Returns:
            requests.Response: The response object resulting from the POST request.
        """

        if not kwargs.get("stream"):
            kwargs.setdefault("timeout", Config.default_timeout)
        
        return self.session.post(url, **kwargs)