from apix.agent.core.bot.protocol.base import HTTPProtocol


class OllamaProtocol(HTTPProtocol):
    def route(self, stream):
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return f"{self.endpoint}/api/chat", headers
