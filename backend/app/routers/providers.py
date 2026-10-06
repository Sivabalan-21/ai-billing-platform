from fastapi import APIRouter
from app.providers.registry import list_providers

router = APIRouter(tags=["providers"])


@router.get("/providers")
def providers():
    return list_providers()