from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.auth_user import AuthUser
from app.models.candidate import Candidate
from app.schemas.candidate import CandidateCreate, CandidateResponse, CandidateListResponse

router = APIRouter()


@router.post("/candidates", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
async def create_candidate(
    payload: CandidateCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    # Check for duplicate candidate_id
    result = await db.execute(
        select(Candidate).where(Candidate.candidate_id == payload.candidate_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Candidate with ID '{payload.candidate_id}' already exists",
        )

    candidate = Candidate(
        candidate_id=payload.candidate_id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
    )
    db.add(candidate)
    await db.flush()
    await db.refresh(candidate)
    return candidate


@router.get("/candidates", response_model=CandidateListResponse)
async def list_candidates(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    result = await db.execute(
        select(Candidate).order_by(Candidate.created_at.desc()).offset(skip).limit(limit)
    )
    candidates = result.scalars().all()

    count_result = await db.execute(select(func.count(Candidate.id)))
    total = count_result.scalar()

    return CandidateListResponse(candidates=candidates, total=total)


@router.get("/candidates/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    result = await db.execute(
        select(Candidate).where(
            (Candidate.id == candidate_id) | (Candidate.candidate_id == candidate_id)
        )
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )
    return candidate
