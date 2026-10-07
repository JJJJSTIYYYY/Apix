from urllib.parse import quote

from apix.agent.core.bot.protocol.base import HTTPProtocol


class GeminiProtocol(HTTPProtocol):
    requires_api_key = True

    def route(self, stream):
        action = "streamGenerateContent?alt=sse" if stream else "generateContent"
        model = self.model.removeprefix("models/")
        return f"{self.endpoint}/models/{quote(model, safe='')}:{action}", {
            "x-goog-api-key": self.api_key,
            "content-type": "application/json",
        }
