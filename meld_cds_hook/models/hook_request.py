from typing import Any, Dict, Optional
from pydantic import BaseModel, HttpUrl
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4
from pydantic import BaseModel, ValidationError


class FhirAuthorization(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    scope: str
    subject: str


class Context(BaseModel):
    userId: str
    patientId: str
    encounterId: str


class HookRequest(BaseModel):
    hook: str
    hookInstance: str
    fhirServer: Optional[HttpUrl] = None
    fhirAuthorization: Optional[FhirAuthorization] = None
    context: Dict[str, Any]
    prefetch: Optional[Dict[str, Any]] = None
