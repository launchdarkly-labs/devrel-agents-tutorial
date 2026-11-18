"""PII never reaches the support agent, and conversation history survives a PII turn."""
import agents.security_agent as security
import agents.supervisor_agent as supervisor
from agents.security_agent import WITHHELD_MESSAGE, PIIDetectionResponse
from agents.supervisor_agent import PIIPreScreening
from api.services.agent_service import AgentService
from tests.fakes import FakeConfigManager, FakeStructuredModel, FixedSecurityAgent, RecordingSupportAgent, served

RAW_MESSAGE = "My email is jane.roe@example.com. What did I ask before?"
REDACTED_MESSAGE = "My email is [REDACTED]. What did I ask before?"
HISTORY = [
    {"role": "user", "content": "What is Q-learning?"},
    {"role": "assistant", "content": "Q-learning is an off-policy TD method."},
]


def route_to_security():
    return FakeStructuredModel(PIIPreScreening(likely_contains_pii=True, confidence=1.0,
                                               reasoning="contains an email", recommended_route="security_agent"))


async def run_chat(monkeypatch, security_agent, history=None):
    """Run one /chat request through the real supervisor graph with fake agents."""
    support_agent = RecordingSupportAgent()
    monkeypatch.setattr(supervisor, "create_chat_model", lambda *args: route_to_security())
    monkeypatch.setattr(supervisor, "create_security_agent", lambda *args: security_agent)
    monkeypatch.setattr(supervisor, "create_support_agent", lambda *args: support_agent)

    service = AgentService()
    service.config_manager = FakeConfigManager({
        "supervisor-agent": served("supervisor-agent"),
        "security-agent": served("security-agent"),
        "support-agent": served("support-agent"),
    })
    response = await service.process_message("u1", RAW_MESSAGE, {"plan": "free"}, history)
    return response, support_agent.received


def support_saw(received):
    return [received["user_input"]] + [m.content for m in received["messages"]]


async def test_support_agent_gets_redacted_text(monkeypatch):
    _, received = await run_chat(monkeypatch, FixedSecurityAgent(REDACTED_MESSAGE))

    assert received["user_input"] == REDACTED_MESSAGE
    assert not any("jane.roe@example.com" in text for text in support_saw(received))


async def test_empty_redaction_withholds_the_message(monkeypatch):
    _, received = await run_chat(monkeypatch, FixedSecurityAgent(""))

    assert received["user_input"] == WITHHELD_MESSAGE
    assert not any("jane.roe@example.com" in text for text in support_saw(received))


async def test_history_survives_a_pii_turn(monkeypatch):
    _, received = await run_chat(monkeypatch, FixedSecurityAgent(REDACTED_MESSAGE), history=HISTORY)

    assert [m.content for m in received["messages"]] == [
        "What is Q-learning?",
        "Q-learning is an off-policy TD method.",
        REDACTED_MESSAGE,
    ]


async def run_security_agent(monkeypatch, model):
    monkeypatch.setattr(security, "create_chat_model", lambda *args: model)
    agent = security.create_security_agent(None, FakeConfigManager({"security-agent": served("security-agent")}))
    return await agent.ainvoke({"user_input": RAW_MESSAGE, "user_id": "u1", "messages": [("user", RAW_MESSAGE)]})


async def test_security_agent_fails_closed_on_error(monkeypatch):
    result = await run_security_agent(monkeypatch, FakeStructuredModel(error=RuntimeError("429 Too Many Requests")))
    assert result["redacted"] == WITHHELD_MESSAGE


async def test_security_agent_fails_closed_without_structured_output(monkeypatch):
    result = await run_security_agent(monkeypatch, FakeStructuredModel(parsed=None))
    assert result["redacted"] == WITHHELD_MESSAGE


async def test_security_agent_returns_the_redaction(monkeypatch):
    parsed = PIIDetectionResponse(detected=True, types=["email"], redacted=REDACTED_MESSAGE)
    result = await run_security_agent(monkeypatch, FakeStructuredModel(parsed=parsed))
    assert result["redacted"] == REDACTED_MESSAGE
