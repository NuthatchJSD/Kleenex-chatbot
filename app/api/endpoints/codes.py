from fastapi import APIRouter
from typing import Annotated

from app.core.auth import *
from app.core.services.codes import code_counts

router = APIRouter()


@router.get("/count")
async def get_code_counters(
    _: Annotated[DashboardUser, Depends(get_current_user)],
):
    code_counters = await code_counts()
    return code_counters
