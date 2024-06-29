import os
import urllib.parse
import requests
from twilio.rest import Client
from httpx import AsyncClient
from fastapi import APIRouter, Request, HTTPException, Response

from app.core.config import settings
from app.chatbot.messages import *
from app.chatbot.flow import FLOW, FlowManager
from app.schemas.participation import Status, Participation
from app.helpers.users import get_user, post_user
from app.helpers.participation import get_current_ticket_number, get_participation, create_participation

client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

router = APIRouter()

async def get_current_participation(client: AsyncClient, user: User) -> Participation:
    participations = await get_participation(client, phone=user.phone, status=Status.INCOMPLETE.value)

    if isinstance(participations, list):
        participation = participations[0] if participations else None
    if not participation:
        participation = await create_participation(client, user)

    return participation

async def handle_user(httpx_client: AsyncClient, user: User, participation: Participation, message: Message):
    flow_manager = FlowManager(FLOW, user, participation)
    await flow_manager.execute(client, httpx_client, message)


async def handle_new_user(httpx_client: AsyncClient, message: Message):
    user = await post_user(httpx_client, message.from_number)
    count = await get_current_ticket_number(httpx_client)
    send_message(
        client,
        FLOW[Steps.ONBOARDING].message_template,
        user,
        {"1": str(count)}
    )


@ router.post("/")
async def webhook(request: Request, response: Response):
    try:
        body_bytes = await request.body()
        message = Message(body_bytes)
        print(
            f"Received message: {message.body_content}, from: {message.from_number}")
        if not (message.body_content or message.num_media) or not message.from_number:
            raise AttributeError

        async with AsyncClient() as client:
            user = await get_user(client, message.from_number)
            if user:
                participation = await get_current_participation(client, user)
                await handle_user(client, user, participation, message)
            else:
                await handle_new_user(client, message)
        print("ending...")

        return {"message": "Received", "from": message.from_number}

    except AttributeError:
        error_message = "Invalid message format. Please ensure the message is correctly formatted."
        response.status_code = 400
        return {"error": error_message}

    except HTTPException as http_exc:
        response.status_code = http_exc.status_code
        return {"error": http_exc.detail}

    except Exception as exc:
        response.status_code = 500
        print(f'Exception: {exc}')
        return {"error": "An unexpected error occurred. Please try again later."}
