from fastapi import APIRouter, Request

from app.schemas import HealthOut, InferenceInfoOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
@router.get("/api/v1/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok")


@router.get("/inference", response_model=InferenceInfoOut)
@router.get("/api/v1/inference", response_model=InferenceInfoOut)
def inference_info(request: Request) -> InferenceInfoOut:
    adapter = request.app.state.inference
    return InferenceInfoOut(
        adapter=adapter.name,
        embed_model=getattr(adapter, "embed_model", None),
        chat_model=getattr(adapter, "chat_model", None),
        study_logic_mounted=bool(getattr(request.app.state, "study_logic_mounted", False)),
    )
