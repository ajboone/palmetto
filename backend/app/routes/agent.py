from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAI, OpenAIError

from app.agent.service import (
    AgentIterationLimitError,
    AgentServiceError,
    run_agent_query,
)
from app.agent.tools import ToolContext
from app.config import PALMETTO_OPENAI_MODEL
from app.models.agent import AgentQuery, AgentResponse
from app.services.charleston_gis import get_gis_client
from app.services.noaa import get_noaa_client
from app.services.weather import get_weather_client


router = APIRouter(prefix="/api/agent", tags=["agent"])


def create_openai_client() -> OpenAI:
    try:
        return OpenAI()
    except OpenAIError as exc:
        raise HTTPException(
            status_code=503,
            detail="PALMETTO AI agent is not configured. Set OPENAI_API_KEY in the environment.",
        ) from exc


@router.post("/query", response_model=AgentResponse)
async def query_agent(
    query: AgentQuery,
    noaa_client=Depends(get_noaa_client),
    weather_client=Depends(get_weather_client),
    gis_client=Depends(get_gis_client),
) -> AgentResponse:
    context = ToolContext(
        noaa_client=noaa_client,
        weather_client=weather_client,
        gis_client=gis_client,
    )
    openai_client = create_openai_client()
    try:
        return await run_agent_query(
            question=query.question,
            client=openai_client,
            context=context,
            model=PALMETTO_OPENAI_MODEL,
        )
    except AgentIterationLimitError as exc:
        raise HTTPException(
            status_code=502,
            detail="PALMETTO could not complete the evidence investigation within its tool limit.",
        ) from exc
    except AgentServiceError as exc:
        raise HTTPException(
            status_code=502,
            detail="PALMETTO AI agent could not complete the request.",
        ) from exc
    finally:
        openai_client.close()