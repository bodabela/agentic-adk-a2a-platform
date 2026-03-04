"""Entry point to expose coder_agent as an A2A server."""

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

_runner = None
# Map task_id → session_id for conversation continuity
_task_sessions: dict[str, str] = {}


def _get_runner():
    """Lazy-init the ADK Runner for coder_agent."""
    global _runner
    if _runner is not None:
        return _runner

    try:
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from modules.coder_agent.agent.agent import root_agent

        session_service = InMemorySessionService()
        _runner = Runner(
            agent=root_agent,
            app_name="coder_agent_a2a",
            session_service=session_service,
        )
        logger.info("ADK Runner initialized for coder_agent")
        return _runner
    except Exception as e:
        logger.error("Failed to initialize ADK Runner: %s", e)
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

    # Extract user message
    message = params.get("message", {})
    parts = message.get("parts", [])
    user_text = " ".join(p.get("text", "") for p in parts if p.get("type") == "text")
    task_id = params.get("id", str(uuid.uuid4()))

    logger.info("[A2A] task=%s prompt=%s", task_id, user_text[:200])

    runner = _get_runner()
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
        from google.genai import types as genai_types

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
        async for event in runner.run_async(
            user_id="flow_engine",
            session_id=session.id,
            new_message=user_content,
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            agent_response_parts.append(part.text)

        result_text = "\n".join(agent_response_parts) or "[No response from agent]"
        logger.info("[A2A] task=%s response=%s", task_id, result_text[:500])

        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "id": task_id,
                "status": {"state": "completed"},
                "artifacts": [{
                    "parts": [{"type": "text", "text": result_text}],
                }],
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

    logger.info("[A2A-SSE] task=%s prompt=%s", task_id, user_text[:200])

    runner = _get_runner()
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
            from google.genai import types as genai_types

            session = await _get_or_create_session(runner, task_id)
            user_content = genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=user_text)],
            )

            agent_response_parts = []

            async for event in runner.run_async(
                user_id="flow_engine",
                session_id=session.id,
                new_message=user_content,
            ):
                author = getattr(event, "author", None) or ""
                content = getattr(event, "content", None)

                if event.is_final_response():
                    if content and hasattr(content, "parts"):
                        for part in content.parts:
                            if hasattr(part, "text") and part.text:
                                agent_response_parts.append(part.text)
                    continue

                # Stream intermediate events
                if content and hasattr(content, "parts"):
                    for part in content.parts:
                        if hasattr(part, "text") and part.text:
                            yield {
                                "event": "thinking",
                                "data": json.dumps({
                                    "task_id": task_id,
                                    "author": author,
                                    "text": part.text,
                                }),
                            }
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

            result_text = "\n".join(agent_response_parts) or "[No response from agent]"
            logger.info("[A2A-SSE] task=%s response=%s", task_id, result_text[:500])

            yield {
                "event": "final",
                "data": json.dumps({
                    "jsonrpc": "2.0", "id": req_id,
                    "result": {
                        "id": task_id,
                        "status": {"state": "completed"},
                        "artifacts": [{"parts": [{"type": "text", "text": result_text}]}],
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
