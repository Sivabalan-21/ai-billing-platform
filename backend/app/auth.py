import hmac
import os

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)
OPEN_PATHS = {"/health"}


def require_admin(request: Request, key: str | None = Security(_header)):
    expected = os.getenv("ADMIN_API_KEY", "")
    if not expected or request.url.path in OPEN_PATHS:
        return  # no key configured (local dev) or a public path
    if not key or not hmac.compare_digest(key.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Missing or wrong admin key")