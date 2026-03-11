"""Task management API."""

import asyncio
import time
import traceback
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.common.logging import get_logger
from src.interactions.models import AgentSuspended

logger = get_logger("tasks")

router = APIRouter()

# Module-level registry of pending interactions: interaction_id -> asyncio.Future
_pending_interactions: dict[str, asyncio.Future] = {}


class TaskSubmission(BaseModel):
    description: str
    context: dict | None = None
    root_agent_definition: str | None = None    # which root-agent def to use
    root_agent_instance_id: str | None = None   # or which running instance
    channel: str | None = None                  # interaction channel override


class TaskResponse(BaseModel):
    task_id: str
    status: str
    description: str


class TaskInteractionResponse(BaseModel):
    interaction_id: str
    response: Any


@router.post("/", response_model=TaskResponse)
async def create_task(submission: TaskSubmission, request: Request):
    """Submit a new task to the root agent."""
    task_id = str(uuid.uuid4())
    event_bus = request.app.state.event_bus

    await event_bus.emit("task_submitted", {
        "task_id": task_id,
        "description": submission.description,
    })

    # Execute via the root agent (async, non-blocking)
    asyncio.create_task(
        _execute_task(task_id, submission, request)
    )

    return TaskResponse(
        task_id=task_id,
        status="submitted",
        description=submission.description,
    )


@router.get("/{task_id}")
async def get_task(task_id: str, request: Request):
    """Get task status and cost report."""
    cost_tracker = request.app.state.cost_tracker
    report = cost_tracker.get_report(task_id)
    return {
        "task_id": task_id,
        "cost_report": report.model_dump() if report else None,
    }


@router.post("/interact")
async def submit_task_interaction(req: TaskInteractionResponse):
    """Submit a user response to a pending task interaction."""
    future = _pending_interactions.get(req.interaction_id)
    if future and not future.done():
        future.set_result(req.response)
        return {"status": "ok", "interaction_id": req.interaction_id}
    raise HTTPException(
        status_code=404,
        detail=f"No pending interaction found: {req.interaction_id}",
    )


async def _execute_task(task_id: str, submission: TaskSubmission, request: Request):
    """Run the root agent to process the task."""
    event_bus = request.app.state.event_bus

    logger.info("task_execution_start", task_id=task_id, description=submission.description)

    try:
        from google.adk.runners import Runner
        from google.genai import types

        root_manager = request.app.state.root_agent_manager
        session_manager = request.app.state.session_manager
        llm_config = request.app.state.llm_config
        default_model = llm_config.defaults.model
        logger.info("task_creating_agent", task_id=task_id, model=default_model)

        # Resolve which root-agent definition to use
        def_name = submission.root_agent_definition
        if not def_name:
            # Pick first available definition
            defs = root_manager.definitions
            def_name = next(iter(defs)) if defs else None
        if not def_name:
            raise ValueError("No root-agent definitions available")

        interaction_broker = getattr(request.app.state, "interaction_broker", None)
        root_agent = root_manager.create_root_agent(
            def_name,
            model_override=default_model,
            task_id=task_id,
            pending_interactions=_pending_interactions,
            event_bus=event_bus,
            instance_id=submission.root_agent_instance_id,
            interaction_broker=interaction_broker,
            channel=submission.channel or "web_ui",
        )
        logger.info("task_agent_created", task_id=task_id, agent=root_agent.name)

        session_service, session_id = await session_manager.get_or_create(
            task_id, app_name="agent_platform",
        )
        runner = Runner(
            agent=root_agent,
            app_name="agent_platform",
            session_service=session_service,
        )

        user_message = types.Content(
            role="user",
            parts=[types.Part(text=submission.description)],
        )

        logger.info("task_runner_start", task_id=task_id, session_id=session_id)

        from google.adk.agents.run_config import RunConfig, StreamingMode

        cost_tracker = request.app.state.cost_tracker
        default_provider = llm_config.defaults.provider or "google"
        last_event_time = time.monotonic()
        final_response_text = ""  # Track the last agent response for channel notification
        task_channel = submission.channel or "web_ui"
        event_count = 0

        async for event in runner.run_async(
            user_id="user", session_id=session_id, new_message=user_message,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        ):
            event_count += 1
            author = getattr(event, "author", None) or ""
            content = getattr(event, "content", None)
            is_partial = getattr(event, "partial", False)
            is_final = getattr(event, "is_final_response", lambda: False)()
            logger.info(
                "task_adk_event",
                task_id=task_id,
                n=event_count,
                author=author,
                partial=is_partial,
                final=is_final,
                has_content=bool(content and getattr(content, "parts", None)),
            )

            # Record cost from usage_metadata on non-partial events
            usage = getattr(event, "usage_metadata", None)
            if usage and not is_partial:
                now = time.monotonic()
                latency = int((now - last_event_time) * 1000)
                last_event_time = now
                input_tokens = usage.prompt_token_count or 0
                output_tokens = usage.candidates_token_count or 0
                model_version = getattr(event, "model_version", None) or default_model
                try:
                    await cost_tracker.record_llm_call(
                        task_id=task_id,
                        module=author or "root_agent",
                        agent=author or "root_agent",
                        model=model_version,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        latency_ms=latency,
                        provider=default_provider,
                    )
                except Exception as cost_err:
                    logger.warning("cost_tracking_failed", error=str(cost_err))

            if not content or not getattr(content, "parts", None):
                continue

            # Partial text — stream token chunks
            if is_partial:
                for part in content.parts:
                    if hasattr(part, "text") and part.text:
                        if hasattr(part, "function_call") and part.function_call:
                            continue  # skip partial function_call arg streaming
                        is_thought = getattr(part, "thought", False)
                        await event_bus.emit("task_event", {
                            "task_id": task_id,
                            "event_type": "streaming_text",
                            "agent": author,
                            "author": author,
                            "model": default_model,
                            "text": part.text,
                            "is_thought": bool(is_thought),
                        })
                        await asyncio.sleep(0)
                continue

            for part in content.parts:
                if hasattr(part, "text") and part.text:
                    is_thought = getattr(part, "thought", False)
                    if is_thought or not event.is_final_response():
                        await event_bus.emit("task_event", {
                            "task_id": task_id,
                            "event_type": "thinking",
                            "agent": author,
                            "author": author,
                            "model": default_model,
                            "text": part.text,
                            "is_thought": bool(is_thought),
                        })
                    else:
                        # Only capture human-readable text as final result
                        # (skip raw JSON from sub-agent tool responses)
                        stripped = part.text.strip()
                        if not (stripped.startswith("{") or stripped.startswith("[")):
                            final_response_text = part.text
                        await event_bus.emit("task_event", {
                            "task_id": task_id,
                            "event_type": "agent_response",
                            "agent": author,
                            "author": author,
                            "model": default_model,
                            "text": part.text,
                        })
                    await asyncio.sleep(0)
                elif hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    tool_event: dict = {
                        "task_id": task_id,
                        "event_type": "tool_call",
                        "agent": author,
                        "author": author,
                        "model": default_model,
                        "tool_name": fc.name,
                        "tool_args": dict(fc.args) if fc.args else {},
                    }
                    # Enrich transfer_to_ calls with full session context
                    if fc.name and fc.name.startswith("transfer_to_"):
                        try:
                            sess = await session_service.get_session(
                                app_name="agent_platform",
                                user_id="user",
                                session_id=session_id,
                            )
                            transfer_ctx: dict = {}
                            if sess:
                                # Session state (agent outputs, app state)
                                if sess.state:
                                    transfer_ctx["state"] = {
                                        k: (v[:3000] if isinstance(v, str) and len(v) > 3000 else v)
                                        for k, v in sess.state.items()
                                    }
                                # Conversation history (messages exchanged so far)
                                if hasattr(sess, "events") and sess.events:
                                    history = []
                                    for ev in sess.events:
                                        ev_content = getattr(ev, "content", None)
                                        ev_author = getattr(ev, "author", None) or ""
                                        if not ev_content or not getattr(ev_content, "parts", None):
                                            continue
                                        for p in ev_content.parts:
                                            if hasattr(p, "text") and p.text:
                                                text = p.text[:2000] if len(p.text) > 2000 else p.text
                                                history.append({"author": ev_author, "text": text})
                                            elif hasattr(p, "function_call") and p.function_call:
                                                history.append({
                                                    "author": ev_author,
                                                    "tool_call": p.function_call.name,
                                                    "args": dict(p.function_call.args) if p.function_call.args else {},
                                                })
                                            elif hasattr(p, "function_response") and p.function_response:
                                                fr_resp = p.function_response.response
                                                if hasattr(fr_resp, "model_dump"):
                                                    fr_resp = fr_resp.model_dump()
                                                elif not isinstance(fr_resp, (dict, list, str, int, float, bool, type(None))):
                                                    fr_resp = str(fr_resp)
                                                resp_str = str(fr_resp)
                                                history.append({
                                                    "author": ev_author,
                                                    "tool_result": p.function_response.name,
                                                    "response": resp_str[:1000] if len(resp_str) > 1000 else resp_str,
                                                })
                                    if history:
                                        transfer_ctx["history"] = history
                            logger.info(
                                "transfer_context_lookup",
                                tool=fc.name,
                                has_session=bool(sess),
                                state_keys=list((sess.state or {}).keys()) if sess else [],
                                history_count=len(transfer_ctx.get("history", [])),
                            )
                            if transfer_ctx:
                                tool_event["transfer_context"] = transfer_ctx
                        except Exception as exc:
                            logger.warning("transfer_context_error", error=str(exc), exc_info=True)
                    await event_bus.emit("task_event", tool_event)
                    await asyncio.sleep(0)
                elif hasattr(part, "function_response") and part.function_response:
                    fr = part.function_response
                    resp_data = fr.response
                    if hasattr(resp_data, "model_dump"):
                        resp_data = resp_data.model_dump()
                    elif not isinstance(resp_data, (dict, list, str, int, float, bool, type(None))):
                        resp_data = str(resp_data)
                    await event_bus.emit("task_event", {
                        "task_id": task_id,
                        "event_type": "tool_result",
                        "agent": author,
                        "author": author,
                        "model": default_model,
                        "tool_name": fr.name,
                        "tool_response": resp_data,
                    })
                    await asyncio.sleep(0)

        logger.info(
            "task_execution_completed",
            task_id=task_id,
            has_final_text=bool(final_response_text),
            final_text_len=len(final_response_text) if final_response_text else 0,
            channel=task_channel,
            has_broker=bool(interaction_broker),
        )
        await event_bus.emit("task_completed", {
            "task_id": task_id,
            "status": "success",
        })

        # Send final result to the task's channel
        if final_response_text and interaction_broker:
            logger.info("task_notify_channel", task_id=task_id, channel=task_channel, text_len=len(final_response_text))
            await interaction_broker.notify_channel(
                channel=task_channel,
                message=final_response_text,
                context_id=task_id,
                metadata={"task_id": task_id, "status": "completed", "notification_type": "result"},
            )
        else:
            logger.warning(
                "task_notify_skipped",
                task_id=task_id,
                reason="no_final_text" if not final_response_text else "no_broker",
            )

    except AgentSuspended as suspended:
        logger.info(
            "task_agent_suspended",
            task_id=task_id,
            interaction_id=suspended.interaction_id,
        )
        await event_bus.emit("task_event", {
            "task_id": task_id,
            "event_type": "agent_suspended",
            "interaction_id": suspended.interaction_id,
            "text": f"Agent suspended — waiting for response on interaction {suspended.interaction_id[:8]}...",
        })
        # Don't emit task_failed — task is paused, not failed
        # Session state is preserved; agent will resume when response arrives

    except Exception as e:
        tb = traceback.format_exc()
        error_type = type(e).__name__
        error_msg = str(e) or repr(e)
        logger.error(
            "task_execution_failed",
            task_id=task_id,
            error_type=error_type,
            error=error_msg,
            traceback=tb,
        )
        await event_bus.emit("task_failed", {
            "task_id": task_id,
            "status": "failed",
            "error": f"[{error_type}] {error_msg}",
        })
    finally:
        # Clean up any orphaned pending interactions
        orphaned = [iid for iid, f in _pending_interactions.items() if not f.done()]
        for iid in orphaned:
            future = _pending_interactions.pop(iid, None)
            if future and not future.done():
                future.cancel()
        # Note: session kept alive for potential multi-turn (not removed here)
