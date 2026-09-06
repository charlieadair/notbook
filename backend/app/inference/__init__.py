from app.config import Settings
from app.inference.base import InferenceAdapter, InferenceProtocol
from app.inference.openai_compatible import OpenAICompatibleInference
from app.inference.stub import StubInference


def build_inference(settings: Settings) -> InferenceAdapter:
    kind = settings.resolved_adapter()
    if kind == "openai-compatible":
        if not settings.openai_api_base or not settings.openai_api_key:
            raise ValueError(
                "INFERENCE_ADAPTER=openai-compatible requires OPENAI_API_BASE and OPENAI_API_KEY"
            )
        return OpenAICompatibleInference(
            api_base=settings.openai_api_base,
            api_key=settings.openai_api_key,
            embed_model=settings.openai_embed_model,
            chat_model=settings.openai_chat_model,
        )
    return StubInference()


__all__ = [
    "InferenceAdapter",
    "InferenceProtocol",
    "OpenAICompatibleInference",
    "StubInference",
    "build_inference",
]
