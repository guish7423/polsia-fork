"""Model provider implementations — one module per API family.

Each provider extends :class:`app.core.model_instance.ModelProvider` and
handles the wire format for its API family.
"""

from app.core.model_providers.openai_compatible import OpenAICompatibleProvider
from app.core.model_providers.mock import MockProvider

__all__ = [
    "OpenAICompatibleProvider",
    "MockProvider",
]
