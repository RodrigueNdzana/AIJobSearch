from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_role
from app.database import get_db
from app.models.employer import Employer
from app.models.user import User, UserRole
from app.schemas.employer import EmployerOut, EmployerUpdate

router = APIRouter(prefix="/api/employers", tags=["employers"])


async def _get_own_company(db: AsyncSession, user: User) -> Employer:
    result = await db.execute(select(Employer).where(Employer.user_id == user.id))
    employer = result.scalar_one_or_none()
    if employer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employer profile not found")
    return employer


@router.get("/me", response_model=EmployerOut)
async def get_my_company(
    current_user: User = Depends(require_role(UserRole.employer)),
    db: AsyncSession = Depends(get_db),
):
    return await _get_own_company(db, current_user)


@router.patch("/me", response_model=EmployerOut)
async def update_my_company(
    payload: EmployerUpdate,
    current_user: User = Depends(require_role(UserRole.employer)),
    db: AsyncSession = Depends(get_db),
):
    employer = await _get_own_company(db, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(employer, field, value)
    await db.commit()
    await db.refresh(employer)
    return employer
