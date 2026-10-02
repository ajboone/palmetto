import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from app.agent.service import AgentIterationLimitError, run_agent_query
from app.agent.instructions import PALMETTO_AGENT_INSTRUCTIONS
from app.agent.tools import (
    EMPTY_OBJECT_SCHEMA,
    PALMETTO_TOOLS,
    ToolContext,
    dispatch_tool_call,
)
from app.routes import agent as agent_route
from openai import OpenAIError
from app.services.weather import NWSServiceError


class OutputItem:
    def __init__(self, **fields):
        self.fields = fields
        for key, value in fields.items():
            setattr(self, key, value)

    def model_dump(self, mode="python"):
        return dict(self.fields)


class FakeResponse:
    def __init__(self, output, output_text=""):
        self.output = output
        self.output_text = output_text


class FakeResponses:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(
            {
                **kwargs,
                "input": json.loads(json.dumps(kwargs["input"])),
            }
        )
        if not self.responses:
            raise AssertionError("Unexpected Responses API iteration")
        return self.responses.pop(0)


def fake_client(*responses):
    return SimpleNamespace(responses=FakeResponses(responses), close=lambda: None)


def function_call(name, call_id, arguments="{}"):
    return OutputItem(
        type="function_call",
        name=name,
        call_id=call_id,
        arguments=arguments,
        id=f"fc_{call_id}",
        status="completed",
    )


def test_registered_tools_are_narrow_strict_empty_object_functions() -> None:
    assert {tool["name"] for tool in PALMETTO_TOOLS} == {
        "get_current_water_level",
        "get_tide_predictions",
        "get_hourly_weather",
        "get_precipitation_forecast",
        "get_weather_alerts",
        "get_road_impacts",
        "get_flood_risk",
    }
    assert all(tool["type"] == "function" and tool["strict"] for tool in PALMETTO_TOOLS)
    assert all(tool["parameters"] == EMPTY_OBJECT_SCHEMA for tool in PALMETTO_TOOLS)


def test_agent_instructions_require_concise_actionable_evidence_and_uncertainty() -> None:
    instructions = " ".join(PALMETTO_AGENT_INSTRUCTIONS.casefold().split())

    for section in (
        "bottom line",
        "what palmetto found",
        "recommended action",
        "confidence",
    ):
        assert section in instructions
    assert "100-180 words" in instructions
    assert "never recalculate, alter, or override that score" in instructions
    assert "risk category is null" in instructions
    assert "flood-related impacts from other" in instructions
    assert "never invent an exact" in instructions
    assert "structured response already preserves tools_used and limitations" in instructions


def test_simple_response_without_tool_calls_returns_output_text() -> None:
    client = fake_client(FakeResponse([], "Check the official alerts before travel."))

    result = asyncio.run(run_agent_query(
        question="Flood conditions?",
        client=client,
        context=ToolContext(None, None, None),
        model="test-model",
    ))

    assert result.answer == "Check the official alerts before travel."
    assert result.tools_used == []
    assert result.tool_call_count == 0
    assert result.model == "test-model"
    assert client.responses.requests[0]["input"] == [
        {"role": "user", "content": "Flood conditions?"}
    ]


def test_flood_risk_tool_round_trips_matching_call_id_and_preserves_output_items() -> None:
    client = fake_client(
        FakeResponse(
            [
                OutputItem(
                    type="reasoning",
                    id="rs_1",
                    summary=[],
                    content=[{"type": "reasoning_text", "text": "checking evidence"}],
                    status="completed",
                    encrypted_content="encrypted-reasoning-payload",
                ),
                OutputItem(
                    type="message",
                    id="msg_1",
                    role="assistant",
                    status="completed",
                    content=[],
                ),
                function_call("get_flood_risk", "call-risk"),
            ]
        ),
        FakeResponse([], "PALMETTO assessed LOW risk with complete evidence."),
    )
    invoked = []

    async def risk_handler(context):
        invoked.append(context)
        return {"risk_level": "LOW", "score": 5}

    result = asyncio.run(run_agent_query(
        question="What is the current PALMETTO risk?",
        client=client,
        context=ToolContext("noaa", "weather", "gis"),
        handlers={"get_flood_risk": risk_handler},
    ))

    assert len(invoked) == 1
    assert result.tools_used == ["get_flood_risk"]
    assert result.tool_call_count == 1
    continuation = client.responses.requests[1]["input"]
    assert continuation[1] == {
        "type": "reasoning",
        "id": "rs_1",
        "summary": [],
        "content": [{"type": "reasoning_text", "text": "checking evidence"}],
        "encrypted_content": "encrypted-reasoning-payload",
    }
    assert continuation[2] == {
        "type": "function_call",
        "call_id": "call-risk",
        "name": "get_flood_risk",
        "arguments": "{}",
    }
    assert continuation[3]["type"] == "function_call_output"
    assert continuation[3]["call_id"] == "call-risk"
    assert json.loads(continuation[3]["output"]) == {
        "risk_level": "LOW",
        "score": 5,
    }
    assert all("status" not in item for item in continuation[1:])
    assert all(item.get("type") != "message" for item in continuation[1:])


def test_multiple_function_calls_are_all_executed_and_returned() -> None:
    calls = [
        function_call("get_current_water_level", "call-water"),
        function_call("get_weather_alerts", "call-alerts"),
    ]
    client = fake_client(FakeResponse(calls), FakeResponse([], "Evidence checked."))
    executed = []
    active = 0
    max_active = 0

    async def water(context):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        executed.append("water")
        await asyncio.sleep(0)
        active -= 1
        return {"value": 3.2}

    async def alerts(context):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        executed.append("alerts")
        await asyncio.sleep(0)
        active -= 1
        return []

    result = asyncio.run(run_agent_query(
        question="Check current evidence.",
        client=client,
        context=ToolContext(None, None, None),
        handlers={
            "get_current_water_level": water,
            "get_weather_alerts": alerts,
        },
    ))

    assert set(executed) == {"water", "alerts"}
    assert max_active == 2
    assert result.tool_call_count == 2
    assert result.tools_used == ["get_current_water_level", "get_weather_alerts"]
    outputs = [
        item
        for item in client.responses.requests[1]["input"]
        if item.get("type") == "function_call_output"
    ]
    assert [item["call_id"] for item in outputs] == ["call-water", "call-alerts"]
    assert all("status" not in item for item in client.responses.requests[1]["input"])


def test_dispatch_parses_empty_json_arguments_and_serializes_pydantic() -> None:
    from app.models.risk import EvidenceStatus, RiskAssessment, RiskLevel

    async def handler(context):
        return RiskAssessment(
            risk_level=RiskLevel.LOW,
            score=0,
            assessed_at="2026-10-02T12:00:00Z",
            location_name="Charleston, South Carolina",
            evidence_status=EvidenceStatus.AVAILABLE,
            components=[],
            contributing_factors=[],
            unavailable_sources=[],
            limitations=[],
            methodology="test",
            disclaimer="test",
        )

    output = asyncio.run(dispatch_tool_call(
        tool_name="get_flood_risk",
        arguments="{}",
        context=ToolContext(None, None, None),
        handlers={"get_flood_risk": handler},
    ))

    assert json.loads(output)["risk_level"] == "LOW"
    assert json.loads(output)["score"] == 0


@pytest.mark.parametrize(
    ("tool_name", "arguments", "expected_error"),
    [
        ("not_registered", "{}", "Unknown PALMETTO tool."),
        ("known", "not-json", "Tool arguments must be valid JSON."),
        ("known", "[]", "This PALMETTO tool accepts no arguments."),
        ("known", '{"station":"other"}', "This PALMETTO tool accepts no arguments."),
    ],
)
def test_unknown_or_malformed_tool_calls_fail_safely(
    tool_name, arguments, expected_error
) -> None:
    async def handler(context):
        raise AssertionError("Invalid tool call must not execute")

    result = asyncio.run(dispatch_tool_call(
        tool_name=tool_name,
        arguments=arguments,
        context=ToolContext(None, None, None),
        handlers={"known": handler},
    ))

    assert json.loads(result)["ok"] is False
    assert json.loads(result)["error"] == expected_error


def test_provider_service_failure_becomes_structured_tool_error() -> None:
    async def handler(context):
        raise NWSServiceError("raw upstream details must not leak")

    output = asyncio.run(dispatch_tool_call(
        tool_name="get_weather_alerts",
        arguments="{}",
        context=ToolContext(None, None, None),
        handlers={"get_weather_alerts": handler},
    ))

    assert json.loads(output) == {
        "ok": False,
        "tool": "get_weather_alerts",
        "error": "NWS data unavailable",
    }
    assert "raw upstream details" not in output


def test_tool_errors_are_reported_as_limitations_and_counted() -> None:
    client = fake_client(
        FakeResponse([function_call("get_weather_alerts", "call-alert")]),
        FakeResponse([], "NWS alerts were unavailable."),
    )

    async def failing_handler(context):
        raise NWSServiceError("private details")

    result = asyncio.run(run_agent_query(
        question="Check alerts.",
        client=client,
        context=ToolContext(None, None, None),
        handlers={"get_weather_alerts": failing_handler},
    ))

    assert result.tools_used == ["get_weather_alerts"]
    assert result.tool_call_count == 1
    assert result.limitations == ["get_weather_alerts: NWS data unavailable."]
    tool_output = client.responses.requests[1]["input"][-1]
    assert json.loads(tool_output["output"])["ok"] is False


def test_tool_iteration_limit_stops_repeated_calls() -> None:
    repeated_call = FakeResponse([function_call("get_flood_risk", "call-repeat")])
    client = fake_client(repeated_call, repeated_call, repeated_call)
    executed = []

    async def handler(context):
        executed.append(True)
        return {"score": 1}

    with pytest.raises(AgentIterationLimitError):
        asyncio.run(run_agent_query(
            question="Repeat?",
            client=client,
            context=ToolContext(None, None, None),
            max_tool_iterations=2,
            handlers={"get_flood_risk": handler},
        ))

    assert len(client.responses.requests) == 3
    assert len(executed) == 2


def test_agent_endpoint_rejects_empty_and_blank_questions(client_factory) -> None:
    client = client_factory(lambda request: httpx.Response(500))

    assert client.post("/api/agent/query", json={"question": ""}).status_code == 422
    assert client.post("/api/agent/query", json={"question": "   "}).status_code == 422


def test_agent_endpoint_returns_agent_response_without_openai_call(
    client_factory, monkeypatch
) -> None:
    mocked_openai = fake_client(FakeResponse([], "Use official sources before travel."))
    monkeypatch.setattr(agent_route, "create_openai_client", lambda: mocked_openai)
    client = client_factory(lambda request: httpx.Response(500))

    response = client.post(
        "/api/agent/query",
        json={"question": "  What should I know about Charleston flooding?  "},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Use official sources before travel.",
        "tools_used": [],
        "tool_call_count": 0,
        "model": agent_route.PALMETTO_OPENAI_MODEL,
        "limitations": [],
    }


def test_agent_endpoint_sanitizes_missing_openai_key(client_factory, monkeypatch) -> None:
    def missing_key():
        raise OpenAIError("secret-looking configuration detail")

    monkeypatch.setattr(agent_route, "OpenAI", missing_key)
    client = client_factory(lambda request: httpx.Response(500))

    response = client.post(
        "/api/agent/query", json={"question": "What should I know today?"}
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "PALMETTO AI agent is not configured. Set OPENAI_API_KEY in the environment."
    }
    assert "secret-looking" not in response.text