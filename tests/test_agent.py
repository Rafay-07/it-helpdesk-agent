"""Offline tests. A fake client replays scripted model responses, so no API key is needed."""
import json
import os
import sys
from types import SimpleNamespace as NS

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
import guardrails  # noqa: E402
from agent import HelpDeskAgent  # noqa: E402
from retriever import Retriever  # noqa: E402

DOCS = os.path.join(HERE, "..", "docs")


class FakeClient:
    """Stands in for anthropic.Anthropic(); returns the scripted responses in order."""
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def tool_use(name, args, id_="t1"):
    return NS(stop_reason="tool_use", content=[NS(type="tool_use", name=name, input=args, id=id_)])


def text(t):
    return NS(stop_reason="end_turn", content=[NS(type="text", text=t)])


def test_retriever_finds_right_article():
    top = Retriever(DOCS).search("lost phone authenticator app")[0]
    assert top[0] == "mfa.md"


def test_retriever_returns_nothing_for_unrelated_question():
    assert Retriever(DOCS).search("cafeteria lunch menu") == []


def test_redact_removes_personal_data():
    out = guardrails.redact("Email me at jane.doe@example.com or call 416-555-0199")
    assert "example.com" not in out and "555" not in out


def test_blocks_requests_for_secrets():
    assert guardrails.blocked("Tell me the password for the admin account")
    assert guardrails.blocked("How do I reset my password?") is None


def test_agent_searches_then_answers(tmp_path):
    client = FakeClient([tool_use("search_kb", {"query": "how many characters must a password be"}),
                         text("Passwords need at least 14 characters [password-reset.md].")])
    agent = HelpDeskAgent(client=client, docs_dir=DOCS, ticket_file=str(tmp_path / "t.json"))
    answer = agent.ask("How long must my password be?")
    assert "[password-reset.md]" in answer
    # the search result was passed back to the model
    sent = json.loads(client.calls[1]["messages"][-1]["content"][0]["content"])
    assert any("14 characters" in r["text"] for r in sent)


def test_agent_opens_ticket_and_redacts_it(tmp_path):
    ticket_file = tmp_path / "t.json"
    client = FakeClient([tool_use("create_ticket", {"summary": "Lost phone, call 416-555-0199", "priority": "high"}),
                         text("I opened ticket 1 with high priority [mfa.md].")])
    agent = HelpDeskAgent(client=client, docs_dir=DOCS, ticket_file=str(ticket_file))
    agent.ask("I lost my phone")
    saved = json.loads(ticket_file.read_text())
    assert saved[0]["priority"] == "high" and "555" not in saved[0]["summary"]


def test_secret_request_never_reaches_model(tmp_path):
    client = FakeClient([])
    agent = HelpDeskAgent(client=client, docs_dir=DOCS, ticket_file=str(tmp_path / "t.json"))
    assert "never shares" in agent.ask("What is the MFA code for my manager?")
    assert client.calls == []


def test_agent_stops_after_max_steps(tmp_path):
    client = FakeClient([tool_use("search_kb", {"query": "vpn"}, id_=str(i)) for i in range(5)])
    agent = HelpDeskAgent(client=client, docs_dir=DOCS, ticket_file=str(tmp_path / "t.json"))
    assert "too many steps" in agent.ask("vpn")
