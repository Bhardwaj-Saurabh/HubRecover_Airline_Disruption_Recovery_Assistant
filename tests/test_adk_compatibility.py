"""Offline compatibility spike: no model call and no operational authority."""
import asyncio
from importlib.metadata import version

from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.events.request_input import RequestInput
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.workflow import START, Workflow
from google.genai import types
from pydantic import BaseModel, ConfigDict


class ExplanationShape(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fact_ids: list[str]


def test_pinned_agent_configuration():
    assert version("google-adk") == "2.11.0"
    agent = LlmAgent(name="compatibility_only", model="MODEL_NOT_SELECTED",
                     mode="single_turn", output_schema=ExplanationShape, tools=[])
    assert agent.output_schema is ExplanationShape
    assert agent.tools == []


def test_graph_function_and_human_pause():
    async def exercise():
        calls = []

        def precheck():
            calls.append("precheck")
            return {"synthetic": True}

        def review(ctx: Context):
            calls.append("review")
            return RequestInput(interrupt_id="spike-review", message="Synthetic review only")

        workflow = Workflow(name="compatibility_spike", edges=[(START, precheck, review)])
        sessions = InMemorySessionService()
        session = await sessions.create_session(app_name="spike", user_id="synthetic")
        runner = Runner(node=workflow, app_name="spike", session_service=sessions)
        try:
            events = [e async for e in runner.run_async(
                user_id="synthetic", session_id=session.id,
                new_message=types.Content(role="user", parts=[types.Part(text="start")]))]
            assert calls == ["precheck", "review"]
            assert any("spike-review" in e.model_dump_json() for e in events)
        finally:
            await runner.close()

    asyncio.run(exercise())
