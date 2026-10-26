from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_session
from app.models.user import MembershipTier, User
from app.schemas import UserCreate, UserOut

router = APIRouter(prefix="/api/users", tags=["users"])


def _to_out(user: User) -> UserOut:
    settings = get_settings()
    limit = settings.free_songs_per_month
    if user.tier == MembershipTier.pro:
        limit = settings.pro_songs_per_month
    elif user.tier == MembershipTier.studio:
        limit = 9999
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        tier=user.tier,
        songs_used_this_month=user.songs_used_this_month,
        songs_limit=limit,
        created_at=user.created_at,
    )


@router.post("", response_model=UserOut)
async def register(body: UserCreate, session: AsyncSession = Depends(get_session)) -> UserOut:
    existing = await session.execute(select(User).where(User.email == body.email))
    user = existing.scalar_one_or_none()
    if user:
        return _to_out(user)
    user = User(email=body.email, display_name=body.display_name or body.email.split("@")[0])
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return _to_out(user)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: str, session: AsyncSession = Depends(get_session)) -> UserOut:
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    return _to_out(user)
