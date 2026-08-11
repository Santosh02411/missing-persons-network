from fastapi import APIRouter

from app.core.config import settings
from app.schemas.emergency import EmergencyContact

router = APIRouter()


@router.get("", response_model=list[EmergencyContact])
def get_emergency_contacts() -> list[EmergencyContact]:
    """Deliberately public -- no login required. Emergency contact
    information (local police/child/women's helplines) must never sit
    behind an account wall; someone in the first urgent hours of a missing-
    persons situation shouldn't have to register first. Configurable via
    the EMERGENCY_CONTACTS setting for deployments outside India."""
    return [EmergencyContact.model_validate(c) for c in settings.EMERGENCY_CONTACTS]
