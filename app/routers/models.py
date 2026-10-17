from fastapi import APIRouter, Depends
from app.config import settings
from app.deps import verify_auth
from app.schemas import ModelsResponse

router = APIRouter(tags=["Models"])


@router.get("/models", response_model=ModelsResponse)
async def list_models(_auth: bool = Depends(verify_auth)):
    """Lists allowed models from configuration."""
    return ModelsResponse(
        models=settings.ALLOWED_MODELS,
        default_model=settings.GEMMA_MODEL,
    )
