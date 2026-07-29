from fastapi import APIRouter, Depends, Request, UploadFile

from app.core.deps import get_current_user
from app.models.user import User
from app.services.upload_service import save_upload

router = APIRouter()


@router.post("/photo")
async def upload_photo(
    request: Request,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Uploads a photo for use as a case or sighting photo_url. Requires
    auth (so anonymous sighting submissions can't include a photo unless the
    tipster logs in first -- a deliberate scope tradeoff, see
    docs/SECURITY_AND_ACCESS.md). Returns a URL under /media/ that's served
    by the StaticFiles mount in main.py."""
    filename = await save_upload(file)
    url = f"{str(request.base_url).rstrip('/')}/media/{filename}"
    return {"url": url}
