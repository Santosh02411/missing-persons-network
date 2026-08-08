from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.user import User, UserRole


def search_authorities(db: Session, query: str | None, limit: int = 20) -> list[User]:
    """Verified authority/NGO accounts, optionally filtered by a text match
    on org name, contact name, or email. Backs the "share this case with
    another station" picker -- unlike nearby_authorities() in geo_service,
    this isn't proximity-limited, since sharing deliberately needs to reach
    stations outside the case's own jurisdiction (e.g. the person was last
    seen near a state border, or may have travelled)."""
    stmt = (
        select(User)
        .where(
            User.role == UserRole.AUTHORITY,
            User.is_verified.is_(True),
            User.is_active.is_(True),
        )
        .order_by(User.org_name, User.full_name)
        .limit(limit)
    )
    if query:
        like = f"%{query}%"
        stmt = stmt.where(
            or_(
                User.org_name.ilike(like),
                User.full_name.ilike(like),
                User.email.ilike(like),
            )
        )
    return list(db.scalars(stmt))
