"""Run a fixed question set against the live model and score the answers.

Checks: the answer cites the expected article, a ticket is opened only when the article says to,
and the priority matches. Needs ANTHROPIC_API_KEY.
"""
import os
import re
import tempfile

from agent import HelpDeskAgent

# Each case names the article the answer should cite and the ticket priority expected, if any.
# The last case is off topic: the right behaviour is no citation and no ticket.
CASES = [
    {"q": "How long does my new password need to be?", "source": "password-reset.md", "ticket": None},
    {"q": "My VPN says certificate expired, what do I do?", "source": "vpn.md", "ticket": None},
    {"q": "I got a new phone and my authenticator is gone. Please open a ticket.", "source": "mfa.md", "ticket": "high"},
    {"q": "I typed my password into a weird login page from an email. Help!", "source": "phishing.md", "ticket": "high"},
    {"q": "What is the cafeteria menu today?", "source": None, "ticket": None},
]


def main():
    passed = 0
    for case in CASES:
        # Each case gets its own empty ticket file, so cases cannot affect each other.
        tickets = os.path.join(tempfile.mkdtemp(), "tickets.json")
        agent = HelpDeskAgent(ticket_file=tickets)
        answer = agent.ask(case["q"])
        # Pull the cited file names out of the answer, and the ticket priorities out of the tool trace.
        cited = re.findall(r"\[([\w-]+\.md)\]", answer)
        made = [t["input"]["priority"] for t in agent.trace if t["tool"] == "create_ticket"]
        ok_source = (case["source"] in cited) if case["source"] else not cited
        ok_ticket = (made == [case["ticket"]]) if case["ticket"] else not made
        status = "PASS" if ok_source and ok_ticket else "FAIL"
        passed += status == "PASS"
        print(f"{status}  {case['q'][:50]:<50} cited={cited} tickets={made}")
    print(f"\n{passed}/{len(CASES)} passed")


if __name__ == "__main__":
    main()
