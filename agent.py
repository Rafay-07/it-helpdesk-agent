"""IT help desk agent: answers from the knowledge base with citations and opens tickets through tool calls.

Run: export ANTHROPIC_API_KEY=... then python agent.py "I lost my phone, how do I get back into MFA?"
"""
import json
import os
import sys
from datetime import datetime

import guardrails
from retriever import Retriever

# The model can be changed without editing code by setting ANTHROPIC_MODEL.
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
# Upper limit on model calls per question, so a confused agent cannot loop forever.
MAX_STEPS = 5

# The standing instructions sent with every request. They keep answers tied to the articles.
SYSTEM = (
    "You are an IT help desk assistant. Answer only from search_kb results and cite the source file in "
    "square brackets, for example [vpn.md]. If the articles do not cover the question, say so and offer to open "
    "a ticket. When an article says to open a ticket, call create_ticket with the priority it names. "
    "Never ask for or repeat passwords or MFA codes."
)

# The two tools the model may call. Each schema tells the model which arguments to send.
TOOLS = [
    {
        "name": "search_kb",
        "description": "Search the IT help desk knowledge base. Returns matching lines with their source file.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "create_ticket",
        "description": "Open a help desk ticket for an issue the user cannot fix with the articles.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "priority": {"type": "string", "enum": ["normal", "high"]},
            },
            "required": ["summary", "priority"],
        },
    },
]


class HelpDeskAgent:
    """Runs the question loop and carries out the tools the model asks for."""
    def __init__(self, client=None, docs_dir="docs", ticket_file="tickets.json"):
        # A fake client can be passed in. That is how the tests run without an API key.
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        self.client = client
        self.retriever = Retriever(docs_dir)
        self.ticket_file = ticket_file
        self.trace = []  # every tool call and result, for debugging and evals

    def run_tool(self, name, args):
        """Carry out one tool call and return its result as JSON text for the model."""
        if name == "search_kb":
            hits = self.retriever.search(args["query"])
            result = [{"source": s, "text": t, "score": sc} for s, t, sc in hits] or "No matching articles."
        elif name == "create_ticket":
            # Personal data is removed from the summary before the ticket is saved.
            ticket = {"summary": guardrails.redact(args["summary"]), "priority": args["priority"],
                      "created": datetime.now().isoformat(timespec="seconds")}
            # Tickets live in a JSON file: read what is there, add the new one, write it back.
            tickets = []
            if os.path.exists(self.ticket_file):
                with open(self.ticket_file) as f:
                    tickets = json.load(f)
            ticket["id"] = len(tickets) + 1
            tickets.append(ticket)
            with open(self.ticket_file, "w") as f:
                json.dump(tickets, f, indent=2)
            result = {"ticket_id": ticket["id"], "priority": ticket["priority"]}
        else:
            result = f"Unknown tool {name}"
        self.trace.append({"tool": name, "input": args, "result": result})
        return json.dumps(result)

    def ask(self, question):
        """Answer one question and return the final text."""
        # Guardrail first: a request for someone's password never reaches the model.
        refusal = guardrails.blocked(question)
        if refusal:
            return refusal
        messages = [{"role": "user", "content": guardrails.redact(question)}]
        # The agent loop: call the model, run any tools it asks for, send the results back, repeat.
        for _ in range(MAX_STEPS):
            response = self.client.messages.create(model=MODEL, max_tokens=800, system=SYSTEM,
                                                   tools=TOOLS, messages=messages)
            # No tool requested means the model has written its final answer.
            if response.stop_reason != "tool_use":
                return "".join(b.text for b in response.content if b.type == "text")
            # Keep the model's tool request in the conversation, then reply with each tool's result.
            messages.append({"role": "assistant", "content": response.content})
            results = [{"type": "tool_result", "tool_use_id": b.id, "content": self.run_tool(b.name, b.input)}
                       for b in response.content if b.type == "tool_use"]
            messages.append({"role": "user", "content": results})
        return "Stopped after too many steps. Please open a ticket."


if __name__ == "__main__":
    agent = HelpDeskAgent()
    print(agent.ask(" ".join(sys.argv[1:]) or "How do I reset my password?"))
