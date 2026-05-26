from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from deepwrap.client import Client


class BaseAPI:
    """
    Base class for all API modules.

    Provides shared access to the root client and its session manager, along
    with convenience wrappers for GET and POST requests.
    """

    def __init__(self, client: "Client") -> None:
        self._client  = client
        self._session = client.session

    def _get(self, url: str, **kwargs: Any):
        """
        Send a GET request through the shared session manager.
        """

        return self._session.get(url, **kwargs)

    def _post(self, url: str, **kwargs: Any):
        """
        Send a POST request through the shared session manager.
        """

        return self._session.post(url, **kwargs)