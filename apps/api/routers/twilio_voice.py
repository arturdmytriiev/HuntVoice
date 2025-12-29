"""Twilio voice call handling endpoints."""

import json
from datetime import datetime
from fastapi import APIRouter, Form, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Optional

from apps.api.deps import get_db
from database.models import CallLog, ConversationState, Reservation, CallStatus, ReservationStatus
from integrations.twilio.twiml import (
    generate_greeting_twiml,
    generate_step_twiml,
    generate_error_twiml
)
from core.services.graph_service import RestaurantBotGraph
from core.services.menu_service import menu_service


router = APIRouter(prefix="/twilio", tags=["twilio"])


def get_bot_graph() -> RestaurantBotGraph:
    """Get restaurant bot graph instance."""
    return RestaurantBotGraph(menu_service)


@router.post("/voice")
async def handle_incoming_call(
    request: Request,
    CallSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Handle incoming voice call - greeting and initial gather.

    Args:
        request: FastAPI request object
        CallSid: Twilio Call SID
        From: Caller's phone number
        To: Called phone number
        db: Database session

    Returns:
        Response: TwiML XML response
    """
    try:
        # Create call log entry
        call_log = CallLog(
            call_sid=CallSid,
            from_number=From,
            to_number=To,
            status=CallStatus.IN_PROGRESS
        )
        db.add(call_log)

        # Create initial conversation state
        conversation_state = ConversationState(
            call_sid=CallSid,
            current_step="greeting",
            state_data=json.dumps({})
        )
        db.add(conversation_state)
        db.commit()

        # Generate step URL for subsequent interactions
        base_url = str(request.base_url).rstrip('/')
        step_url = f"{base_url}/api/v1/twilio/step"

        # Generate greeting TwiML
        twiml = generate_greeting_twiml(step_url)

        return Response(content=twiml, media_type="application/xml")

    except Exception as e:
        db.rollback()
        return Response(
            content=generate_error_twiml(f"An error occurred: {str(e)}"),
            media_type="application/xml"
        )


@router.post("/step")
async def handle_call_step(
    request: Request,
    CallSid: str = Form(...),
    SpeechResult: Optional[str] = Form(None),
    Digits: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Handle conversation step - process speech, run graph, update state.

    Args:
        request: FastAPI request object
        CallSid: Twilio Call SID
        SpeechResult: Speech recognition result from user
        Digits: DTMF digits if user pressed keys
        db: Database session

    Returns:
        Response: TwiML XML response
    """
    try:
        # Get user input (prefer speech over digits)
        user_input = SpeechResult or Digits or ""

        # Load conversation state from database
        conversation_state = db.query(ConversationState).filter(
            ConversationState.call_sid == CallSid
        ).first()

        if not conversation_state:
            return Response(
                content=generate_error_twiml("Session not found. Please call again."),
                media_type="application/xml"
            )

        # Parse current state data
        try:
            state_data = json.loads(conversation_state.state_data) if conversation_state.state_data else {}
        except json.JSONDecodeError:
            state_data = {}

        # Run graph to process input and get next step
        bot_graph = get_bot_graph()
        result = bot_graph.run(
            current_step=conversation_state.current_step,
            user_input=user_input,
            state_data=state_data
        )

        # Update conversation state
        conversation_state.current_step = result.get("next_step", "greeting")
        conversation_state.state_data = json.dumps(result.get("state", {}))
        db.commit()

        # Handle reservation creation if confirmed
        if result.get("next_step") == "goodbye" and result.get("state", {}).get("confirmed"):
            await create_reservation_from_state(CallSid, result.get("state", {}), db)

        # Update call log transcript
        call_log = db.query(CallLog).filter(CallLog.call_sid == CallSid).first()
        if call_log:
            current_transcript = call_log.transcript or ""
            call_log.transcript = f"{current_transcript}\nUser: {user_input}\nBot: {result.get('message', '')}"
            db.commit()

        # Generate step URL for next interaction
        base_url = str(request.base_url).rstrip('/')
        step_url = f"{base_url}/api/v1/twilio/step"

        # Generate TwiML response
        should_hangup = result.get("should_hangup", False)
        twiml = generate_step_twiml(
            message=result.get("message", ""),
            step_url=step_url,
            should_hangup=should_hangup
        )

        # Update call status if hanging up
        if should_hangup and call_log:
            call_log.status = CallStatus.COMPLETED
            call_log.ended_at = datetime.utcnow()
            db.commit()

        return Response(content=twiml, media_type="application/xml")

    except Exception as e:
        db.rollback()
        return Response(
            content=generate_error_twiml(f"An error occurred: {str(e)}"),
            media_type="application/xml"
        )


async def create_reservation_from_state(call_sid: str, state: dict, db: Session):
    """
    Create a reservation from conversation state.

    Args:
        call_sid: Twilio Call SID
        state: Conversation state data
        db: Database session
    """
    try:
        # Parse reservation date and time
        reservation_date_str = f"{state.get('reservation_date', '')} {state.get('reservation_time', '')}"
        # For now, use current date as placeholder - in production, parse the date properly
        reservation_date = datetime.utcnow()

        # Get call log to extract phone number
        call_log = db.query(CallLog).filter(CallLog.call_sid == call_sid).first()
        customer_phone = call_log.from_number if call_log else "Unknown"

        # Create reservation
        reservation = Reservation(
            call_sid=call_sid,
            customer_name=state.get('customer_name', 'Unknown'),
            customer_phone=customer_phone,
            party_size=state.get('party_size', 2),
            reservation_date=reservation_date,
            special_requests=None,
            status=ReservationStatus.CONFIRMED
        )
        db.add(reservation)
        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create reservation: {str(e)}")


@router.post("/status")
async def handle_call_status(
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    CallDuration: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Handle Twilio status callback for call completion.

    Args:
        CallSid: Twilio Call SID
        CallStatus: Call status
        CallDuration: Call duration in seconds
        db: Database session

    Returns:
        dict: Success response
    """
    try:
        call_log = db.query(CallLog).filter(CallLog.call_sid == CallSid).first()

        if call_log:
            if CallStatus == "completed":
                call_log.status = CallStatus.COMPLETED
                call_log.ended_at = datetime.utcnow()
                call_log.duration_seconds = CallDuration
            elif CallStatus == "failed" or CallStatus == "busy" or CallStatus == "no-answer":
                call_log.status = CallStatus.FAILED
                call_log.ended_at = datetime.utcnow()

            db.commit()

        return {"status": "success"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
