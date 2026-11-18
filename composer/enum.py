from enum import Enum

class LLMProvider(Enum):
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai-compatible"
    OPEN_ROUTER = "open-router"
    GOOGLE = "google"

class ServerTransport(Enum):
    STDIO = "stdio"
    HTTP = "http"