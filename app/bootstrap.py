from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models.enums import UserRole
from app.models.user import User
from app.security import hash_password


def create_development_admin() -> None:
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        return
    with SessionLocal() as db:
        existing = db.scalar(
            select(User).where(User.email == settings.bootstrap_admin_email.lower())
        )
        if existing:
            return
        db.add(
            User(
                email=settings.bootstrap_admin_email.lower(),
                full_name=settings.bootstrap_admin_name,
                password_hash=hash_password(settings.bootstrap_admin_password),
                role=UserRole.ADMIN,
            )
        )
        db.commit()
