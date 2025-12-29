"""Admin endpoints for viewing reservations and call logs."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from apps.api.deps import get_db
from database.models import Reservation, CallLog, ReservationStatus, CallStatus
from database.schemas import ReservationResponse, CallLogResponse


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/reservations", response_model=List[ReservationResponse])
async def list_reservations(
    status: Optional[ReservationStatus] = Query(None, description="Filter by reservation status"),
    limit: int = Query(50, ge=1, le=200, description="Number of reservations to return"),
    offset: int = Query(0, ge=0, description="Number of reservations to skip"),
    db: Session = Depends(get_db)
):
    """
    List all reservations with optional filtering.

    Args:
        status: Filter by reservation status (pending, confirmed, cancelled, completed)
        limit: Maximum number of reservations to return
        offset: Number of reservations to skip (for pagination)
        db: Database session

    Returns:
        List[ReservationResponse]: List of reservations
    """
    try:
        query = db.query(Reservation)

        # Apply status filter if provided
        if status:
            query = query.filter(Reservation.status == status)

        # Order by most recent first
        query = query.order_by(desc(Reservation.created_at))

        # Apply pagination
        reservations = query.offset(offset).limit(limit).all()

        return reservations

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch reservations: {str(e)}")


@router.get("/reservations/{reservation_id}", response_model=ReservationResponse)
async def get_reservation(
    reservation_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific reservation by ID.

    Args:
        reservation_id: Reservation ID
        db: Database session

    Returns:
        ReservationResponse: Reservation details
    """
    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()

    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    return reservation


@router.get("/calls", response_model=List[CallLogResponse])
async def list_call_logs(
    status: Optional[CallStatus] = Query(None, description="Filter by call status"),
    limit: int = Query(50, ge=1, le=200, description="Number of call logs to return"),
    offset: int = Query(0, ge=0, description="Number of call logs to skip"),
    db: Session = Depends(get_db)
):
    """
    List all call logs with optional filtering.

    Args:
        status: Filter by call status (initiated, in_progress, completed, failed)
        limit: Maximum number of call logs to return
        offset: Number of call logs to skip (for pagination)
        db: Database session

    Returns:
        List[CallLogResponse]: List of call logs
    """
    try:
        query = db.query(CallLog)

        # Apply status filter if provided
        if status:
            query = query.filter(CallLog.status == status)

        # Order by most recent first
        query = query.order_by(desc(CallLog.started_at))

        # Apply pagination
        call_logs = query.offset(offset).limit(limit).all()

        return call_logs

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch call logs: {str(e)}")


@router.get("/calls/{call_sid}", response_model=CallLogResponse)
async def get_call_log(
    call_sid: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific call log by Call SID.

    Args:
        call_sid: Twilio Call SID
        db: Database session

    Returns:
        CallLogResponse: Call log details
    """
    call_log = db.query(CallLog).filter(CallLog.call_sid == call_sid).first()

    if not call_log:
        raise HTTPException(status_code=404, detail="Call log not found")

    return call_log


@router.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """
    Get basic statistics about calls and reservations.

    Args:
        db: Database session

    Returns:
        dict: Statistics including total calls, reservations, etc.
    """
    try:
        total_calls = db.query(CallLog).count()
        completed_calls = db.query(CallLog).filter(CallLog.status == CallStatus.COMPLETED).count()
        failed_calls = db.query(CallLog).filter(CallLog.status == CallStatus.FAILED).count()

        total_reservations = db.query(Reservation).count()
        confirmed_reservations = db.query(Reservation).filter(
            Reservation.status == ReservationStatus.CONFIRMED
        ).count()
        pending_reservations = db.query(Reservation).filter(
            Reservation.status == ReservationStatus.PENDING
        ).count()
        cancelled_reservations = db.query(Reservation).filter(
            Reservation.status == ReservationStatus.CANCELLED
        ).count()

        return {
            "calls": {
                "total": total_calls,
                "completed": completed_calls,
                "failed": failed_calls,
                "in_progress": total_calls - completed_calls - failed_calls
            },
            "reservations": {
                "total": total_reservations,
                "confirmed": confirmed_reservations,
                "pending": pending_reservations,
                "cancelled": cancelled_reservations
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")
