from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models.streamer import Streamer, StreamerAccount
from app.schemas.streamer import (
    StreamerCreate,
    StreamerUpdate,
    StreamerOut,
    StreamerAccountCreate,
    StreamerAccountOut,
)

router = APIRouter(prefix="/streamers", tags=["Streamers"])


@router.get("", response_model=list[StreamerOut])
def list_streamers(
    active_only: bool = False,
    db: Session = Depends(get_db)
):
    query = db.query(Streamer).options(selectinload(Streamer.accounts))

    if active_only:
        query = query.filter(Streamer.is_active.is_(True))

    return query.order_by(
        Streamer.priority.desc(),
        Streamer.name.asc()
    ).all()


@router.post("", response_model=StreamerOut, status_code=201)
def create_streamer(
    payload: StreamerCreate,
    db: Session = Depends(get_db)
):
    streamer = Streamer(**payload.model_dump())
    db.add(streamer)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Streamer slug already exists"
        )

    return db.query(Streamer).options(
        selectinload(Streamer.accounts)
    ).filter(Streamer.id == streamer.id).first()


@router.get("/{streamer_id}", response_model=StreamerOut)
def get_streamer(streamer_id: int, db: Session = Depends(get_db)):
    streamer = db.query(Streamer).options(
        selectinload(Streamer.accounts)
    ).filter(Streamer.id == streamer_id).first()

    if not streamer:
        raise HTTPException(status_code=404, detail="Streamer not found")

    return streamer


@router.patch("/{streamer_id}", response_model=StreamerOut)
def update_streamer(
    streamer_id: int,
    payload: StreamerUpdate,
    db: Session = Depends(get_db)
):
    streamer = db.query(Streamer).filter(
        Streamer.id == streamer_id
    ).first()

    if not streamer:
        raise HTTPException(status_code=404, detail="Streamer not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(streamer, key, value)

    db.commit()
    db.refresh(streamer)
    return streamer


@router.delete("/{streamer_id}", status_code=204)
def delete_streamer(streamer_id: int, db: Session = Depends(get_db)):
    streamer = db.query(Streamer).filter(
        Streamer.id == streamer_id
    ).first()

    if not streamer:
        raise HTTPException(status_code=404, detail="Streamer not found")

    db.delete(streamer)
    db.commit()


@router.post(
    "/{streamer_id}/accounts",
    response_model=StreamerAccountOut,
    status_code=201
)
def add_streamer_account(
    streamer_id: int,
    payload: StreamerAccountCreate,
    db: Session = Depends(get_db)
):
    streamer = db.query(Streamer).filter(
        Streamer.id == streamer_id
    ).first()

    if not streamer:
        raise HTTPException(status_code=404, detail="Streamer not found")

    account = StreamerAccount(
        streamer_id=streamer_id,
        **payload.model_dump()
    )
    db.add(account)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This platform username is already registered"
        )

    db.refresh(account)
    return account


@router.get(
    "/{streamer_id}/accounts",
    response_model=list[StreamerAccountOut]
)
def list_streamer_accounts(
    streamer_id: int,
    db: Session = Depends(get_db)
):
    streamer = db.query(Streamer).filter(
        Streamer.id == streamer_id
    ).first()

    if not streamer:
        raise HTTPException(status_code=404, detail="Streamer not found")

    return db.query(StreamerAccount).filter(
        StreamerAccount.streamer_id == streamer_id
    ).all()