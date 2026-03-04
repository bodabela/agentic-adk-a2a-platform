"""Entry point to expose coder_agent as an A2A server."""

import asyncio
import json
import logging
import uuid
from pathlib import Path

from dotenv import load_dotenv

# Load module-level .env
_module_dir = Path(__file__).resolve().parent.parent
load_dotenv(_module_dir / ".env")

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

logger = logging.getLogger("coder_agent.a2a")

# Note: This is used as:
#   uvicorn modules.coder_agent.agent.serve_a2a:app --port 8001
# from the project root directory.

app = FastAPI(title="coder_agent A2A Server")

CARD_PATH = Path(__file__).parent / "agent_card.json"


@app.get("/.well-known/agent.json")
async def agent_card():
    return json.loads(CARD_PATH.read_text())


@app.get("/health")
async def health():
    return {"status": "ok", "agent": "coder_agent"}


# --- A2A JSON-RPC handler ---

# Cache runners per model: { model_name: Runner }
_runners: dict[str, object] = {}
# Map task_id → session_id for conversation continuity
_task_sessions: dict[str, str] = {}


def _get_runner(model: str | None = None):
    """Get or create an ADK Runner, optionally for a specific model."""
    from modules.coder_agent.agent.agent import DEFAULT_MODEL

    requested_model = model or DEFAULT_MODEL
    if requested_model in _runners:
        return _runners[requested_model]

    try:
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from modules.coder_agent.agent.agent import create_agent

        agent = create_agent(requested_model)
        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name="coder_agent_a2a",
            session_service=session_service,
        )
        _runners[requested_model] = runner
        logger.info("ADK Runner initialized for coder_agent (model=%s)", requested_model)
        return runner
    except Exception as e:
        logger.error("Failed to initialize ADK Runner (model=%s): %s", requested_model, e)
        return None


@app.post("/")
async def a2a_endpoint(request: Request):
    """Handle A2A JSON-RPC requests (tasks/send)."""
    body = await request.json()
    req_id = body.get("id", str(uuid.uuid4()))
    method = body.get("method", "")
    params = body.get("params", {})

    logger.info("[A2A] method=%s id=%s", method, req_id)

    if method != "tasks/send":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        })

    # Extract user message and optional model override
    message = params.get("message", {})
    parts = message.get("parts", [])
    user_text = " ".join(p.get("text", "") for p in parts if p.get("type") == "text")
    task_id = params.get("id", str(uuid.uuid4()))
    model_override = params.get("model")

    from modules.coder_agent.agent.agent import DEFAULT_MODEL
    actual_model = model_override or DEFAULT_MODEL

    logger.info("[A2A] task=%s model=%s prompt=%s", task_id, actual_model, user_text[:200])

    runner = _get_runner(model_override)
    if runner is None:
        # No ADK available — return the prompt as-is (for testing)
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "id": task_id,
                "status": {"state": "completed"},
                "artifacts": [{
                    "parts": [{"type": "text", "text": f"[coder_agent echo] {user_text}"}],
                }],
            },
        })

    # Run the agent via ADK Runner
    try:
        import time
        from google.genai import types as genai_types

        start_time = time.monotonic()

        # Reuse session for the same task_id (conversation continuity)
        existing_session_id = _task_sessions.get(task_id)
        if existing_session_id:
            session = await runner.session_service.get_session(
                app_name="coder_agent_a2a",
                user_id="flow_engine",
                session_id=existing_session_id,
            )
            logger.info("[A2A] task=%s reusing session=%s", task_id, existing_session_id)
        else:
            session = None

        if session is None:
            session = await runner.session_service.create_session(
                app_name="coder_agent_a2a",
                user_id="flow_engine",
            )
            _task_sessions[task_id] = session.id
            logger.info("[A2A] task=%s new session=%s", task_id, session.id)

        user_content = genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=user_text)],
        )

        agent_response_parts = []
        total_output_chars = 0
        async for event in runner.run_async(
            user_id="flow_engine",
            session_id=session.id,
            new_message=user_content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        total_output_chars += len(part.text)
            if event.is_final_response():
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            agent_response_parts.append(part.text)

        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        result_text = "\n".join(agent_response_parts) or "[No response from agent]"
        logger.info("[A2A] task=%s response=%s", task_id, result_text[:500])

        # Estimate tokens from character counts (~4 chars per token)
        input_tokens_est = max(len(user_text) // 4, 1)
        output_tokens_est = max(total_output_chars // 4, 1)

        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "id": task_id,
                "status": {"state": "completed"},
                "artifacts": [{
                    "parts": [{"type": "text", "text": result_text}],
                }],
                "usage": {
                    "input_tokens_est": input_tokens_est,
                    "output_tokens_est": output_tokens_est,
                    "model": actual_model,
                    "provider": "google",
                    "latency_ms": elapsed_ms,
                },
            },
        })
    except Exception as e:
        logger.error("[A2A] task=%s error: %s", task_id, e, exc_info=True)
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "id": task_id,
                "status": {"state": "failed"},
                "artifacts": [{
                    "parts": [{"type": "text", "text": f"Agent error: {e}"}],
                }],
            },
        })


async def _get_or_create_session(runner, task_id: str):
    """Get existing session for task_id or create a new one."""
    existing_session_id = _task_sessions.get(task_id)
    if existing_session_id:
        session = await runner.session_service.get_session(
            app_name="coder_agent_a2a",
            user_id="flow_engine",
            session_id=existing_session_id,
        )
        if session:
            logger.info("[A2A] task=%s reusing session=%s", task_id, existing_session_id)
            return session

    session = await runner.session_service.create_session(
        app_name="coder_agent_a2a",
        user_id="flow_engine",
    )
    _task_sessions[task_id] = session.id
    logger.info("[A2A] task=%s new session=%s", task_id, session.id)
    return session


@app.post("/tasks/sendSubscribe")
async def a2a_stream_endpoint(request: Request):
    """Handle A2A streaming requests — returns SSE stream of intermediate events."""
    body = await request.json()
    req_id = body.get("id", str(uuid.uuid4()))
    params = body.get("params", {})

    message = params.get("message", {})
    parts = message.get("parts", [])
    user_text = " ".join(p.get("text", "") for p in parts if p.get("type") == "text")
    task_id = params.get("id", str(uuid.uuid4()))
    model_override = params.get("model")

    from modules.coder_agent.agent.agent import DEFAULT_MODEL
    actual_model = model_override or DEFAULT_MODEL

    logger.info("[A2A-SSE] task=%s model=%s prompt=%s", task_id, actual_model, user_text[:200])

    runner = _get_runner(model_override)
    if runner is None:
        async def no_runner_stream():
            yield {
                "event": "final",
                "data": json.dumps({
                    "jsonrpc": "2.0", "id": req_id,
                    "result": {
                        "id": task_id,
                        "status": {"state": "completed"},
                        "artifacts": [{"parts": [{"type": "text", "text": f"[echo] {user_text}"}]}],
                    },
                }),
            }
        return EventSourceResponse(no_runner_stream())

    async def event_stream():
        try:
            import time
            from google.adk.agents.run_config import RunConfig, StreamingMode
            from google.genai import types as genai_types

            start_time = time.monotonic()
            session = await _get_or_create_session(runner, task_id)
            user_content = genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=user_text)],
            )

            agent_response_parts = []
            total_output_chars = 0

            async for event in runner.run_async(
                user_id="flow_engine",
                session_id=session.id,
                new_message=user_content,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            ):
                author = getattr(event, "author", None) or ""
                content = getattr(event, "content", None)
                is_partial = getattr(event, "partial", False)

                # Partial text events — stream token-by-token
                if is_partial and content and hasattr(content, "parts"):
                    for part in content.parts:
                        if hasattr(part, "text") and part.text:
                            # Skip partial function_call argument streaming
                            if hasattr(part, "function_call") and part.function_call:
                                continue
                            total_output_chars += len(part.text)
                            is_thought = getattr(part, "thought", False)
                            yield {
                                "event": "streaming_text",
                                "data": json.dumps({
                                    "task_id": task_id,
                                    "author": author,
                                    "text": part.text,
                                    "is_thought": bool(is_thought),
                                }),
                            }
                            await asyncio.sleep(0)
                    continue

                if event.is_final_response():
                    if content and hasattr(content, "parts"):
                        for part in content.parts:
                            if hasattr(part, "text") and part.text:
                                total_output_chars += len(part.text)
                                agent_response_parts.append(part.text)
                    continue

                # Non-partial intermediate events (complete thinking, tool calls, results)
                if content and hasattr(content, "parts"):
                    for part in content.parts:
                        if hasattr(part, "text") and part.text:
                            total_output_chars += len(part.text)
                            is_thought = getattr(part, "thought", False)
                            yield {
                                "event": "thinking",
                                "data": json.dumps({
                                    "task_id": task_id,
                                    "author": author,
                                    "text": part.text,
                                    "is_thought": bool(is_thought),
                                }),
                            }
                            await asyncio.sleep(0)
                        elif hasattr(part, "function_call") and part.function_call:
                            fc = part.function_call
                            yield {
                                "event": "tool_call",
                                "data": json.dumps({
                                    "task_id": task_id,
                                    "author": author,
                                    "tool_name": fc.name,
                                    "tool_args": dict(fc.args) if fc.args else {},
                                }),
                            }
                            await asyncio.sleep(0)
                        elif hasattr(part, "function_response") and part.function_response:
                            fr = part.function_response
                            resp_data = fr.response
                            if hasattr(resp_data, "model_dump"):
                                resp_data = resp_data.model_dump()
                            elif not isinstance(resp_data, (dict, list, str, int, float, bool, type(None))):
                                resp_data = str(resp_data)
                            yield {
                                "event": "tool_result",
                                "data": json.dumps({
                                    "task_id": task_id,
                                    "author": author,
                                    "tool_name": fr.name,
                                    "tool_response": resp_data,
                                }, default=str),
                            }
                            await asyncio.sleep(0)

            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            result_text = "\n".join(agent_response_parts) or "[No response from agent]"
            logger.info("[A2A-SSE] task=%s response=%s", task_id, result_text[:500])

            # Estimate tokens from character counts (~4 chars per token)
            input_tokens_est = max(len(user_text) // 4, 1)
            output_tokens_est = max(total_output_chars // 4, 1)

            yield {
                "event": "final",
                "data": json.dumps({
                    "jsonrpc": "2.0", "id": req_id,
                    "result": {
                        "id": task_id,
                        "status": {"state": "completed"},
                        "artifacts": [{"parts": [{"type": "text", "text": result_text}]}],
                        "usage": {
                            "input_tokens_est": input_tokens_est,
                            "output_tokens_est": output_tokens_est,
                            "model": actual_model,
                            "provider": "google",
                            "latency_ms": elapsed_ms,
                        },
                    },
                }),
            }

        except Exception as e:
            logger.error("[A2A-SSE] task=%s error: %s", task_id, e, exc_info=True)
            yield {
                "event": "final",
                "data": json.dumps({
                    "jsonrpc": "2.0", "id": req_id,
                    "result": {
                        "id": task_id,
                        "status": {"state": "failed"},
                        "artifacts": [{"parts": [{"type": "text", "text": f"Agent error: {e}"}]}],
                    },
                }),
            }

    return EventSourceResponse(event_stream())
