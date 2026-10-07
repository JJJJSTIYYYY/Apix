from apix.agent.core.bot.protocol.base import HTTPProtocol


class AnthropicProtocol(HTTPProtocol):
    requires_api_key = True

    def route(self, stream):
        return f"{self.endpoint}/messages", {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
