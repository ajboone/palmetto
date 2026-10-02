import asyncio
import json
from collections.abc import Callable
from typing import Any

from app.agent.instructions import PALMETTO_AGENT_INSTRUCTIONS
from app.agent.tools import (
    PALMETTO_TOOLS,
    TOOL_HANDLERS,
    ToolContext,
    dispatch_tool_call,
)
from app.config import PALMETTO_AGENT_MAX_TOOL_ITERATIONS, PALMETTO_OPENAI_MODEL
from app.models.agent import AgentResponse


class AgentServiceError(Exception):
    pass


class AgentIterationLimitError(AgentServiceError):
    pass


def _value(item: Any, key: str) -> Any:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _output_item_for_input(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return item
    model_dump = getattr(item, "model_dump", None)
    if callable(model_dump):
        serialized = model_dump(mode="json")
        if isinstance(serialized, dict):
            return serialized
    raise AgentServiceError("OpenAI returned an unsupported response item.")


async def run_agent_query(
    *,
    question: str,
    client: Any,
    context: ToolContext,
    model: str = PALMETTO_OPENAI_MODEL,
    max_tool_iterations: int = PALMETTO_AGENT_MAX_TOOL_ITERATIONS,
    tools: list[dict[str, Any]] | None = None,
    handlers: dict[str, Callable[..., Any]] | None = None,
) -> AgentResponse:
    if max_tool_iterations < 0:
        raise ValueError("max_tool_iterations must not be negative")

    input_items: list[dict[str, Any]] = [{"role": "user", "content": question}]
    tool_definitions = PALMETTO_TOOLS if tools is None else tools
    handler_registry = TOOL_HANDLERS if handlers is None else handlers
    tools_used: list[str] = []
    limitations: list[str] = []
    tool_call_count = 0

    for iteration in range(max_tool_iterations + 1):
        try:
            response = await asyncio.to_thread(
                client.responses.create,
                model=model,
                instructions=PALMETTO_AGENT_INSTRUCTIONS,
                input=input_items,
                tools=tool_definitions,
            )
        except Exception as exc:
            raise AgentServiceError("OpenAI Responses API request failed.") from exc

        output_items = _value(response, "output")
        if not isinstance(output_items, (list, tuple)):
            raise AgentServiceError("OpenAI returned a malformed response.")
        input_items.extend(_output_item_for_input(item) for item in output_items)
        function_calls = [
            item for item in output_items if _value(item, "type") == "function_call"
        ]

        if not function_calls:
            answer = _value(response, "output_text")
            if not isinstance(answer, str) or not answer.strip():
                raise AgentServiceError("OpenAI returned no final answer.")
            return AgentResponse(
                answer=answer,
                tools_used=tools_used,
                tool_call_count=tool_call_count,
                model=model,
                limitations=limitations,
            )

        if iteration >= max_tool_iterations:
            raise AgentIterationLimitError(
                "PALMETTO agent reached its maximum tool iteration limit."
            )

        calls_to_dispatch = []
        for call in function_calls:
            tool_name = _value(call, "name")
            call_id = _value(call, "call_id")
            arguments = _value(call, "arguments")
            if not isinstance(tool_name, str) or not isinstance(call_id, str):
                raise AgentServiceError("OpenAI returned a malformed function call.")
            tool_call_count += 1
            if tool_name not in tools_used:
                tools_used.append(tool_name)
            calls_to_dispatch.append((tool_name, call_id, arguments))

        outputs = await asyncio.gather(
            *(
                dispatch_tool_call(
                    tool_name=tool_name,
                    arguments=arguments,
                    context=context,
                    handlers=handler_registry,
                )
                for tool_name, _, arguments in calls_to_dispatch
            )
        )
        for (tool_name, call_id, _), output in zip(calls_to_dispatch, outputs):
            parsed_output = json.loads(output)
            if isinstance(parsed_output, dict) and parsed_output.get("ok") is False:
                error = parsed_output.get("error")
                if isinstance(error, str):
                    limitation = f"{tool_name}: {error}."
                    if limitation not in limitations:
                        limitations.append(limitation)
            input_items.append(
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": output,
                }
            )

    raise AgentIterationLimitError("PALMETTO agent did not complete within its tool limit.")