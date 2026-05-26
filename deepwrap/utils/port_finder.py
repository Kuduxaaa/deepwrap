import socket

class PortFinder:
    """
    Utility class to find free local ports for launching browser instances with remote debugging enabled.
     - Uses socket binding to find available ports on localhost.
     - Ensures that the selected port is free at the time of checking, but does not guarantee it will remain free.
     - Used by the authentication module to assign a remote debugging port for the browser instance.
    """

    @staticmethod
    def find_free_port() -> int:
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        return port