# IT Help Desk Agent

A small LLM agent that answers IT help desk questions from a knowledge base, cites the article it used, and opens tickets through tool calls. It uses the Claude API with tool use, a TF-IDF retriever, guardrails that run outside the model, offline unit tests and an evaluation script.

The knowledge base in `docs/` is four made-up articles: password reset, VPN, MFA and phishing.

## How it works

1. **Guardrails first.** `guardrails.py` refuses requests for passwords or MFA codes before anything reaches the model, and redacts emails, phone numbers and card-like numbers from the question and from saved tickets.
2. **Agent loop.** `agent.py` sends the question to the model with two tools: `search_kb` and `create_ticket`. The loop runs tool calls and returns results until the model gives a final answer, with a hard limit of 5 steps.
3. **Retrieval.** `retriever.py` splits articles into lines and ranks them with TF-IDF and cosine similarity. Results below a minimum score are dropped, so off-topic questions get no context and the model says it cannot answer.
4. **Grounded answers.** The system prompt requires a citation like `[vpn.md]` and tells the model to open a ticket only when an article says to, at the priority the article names.

## Run it

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key
python agent.py "I got a new phone and lost my authenticator"
```

Set `ANTHROPIC_MODEL` to use a different model.

## Tests and evals

```bash
python -m pytest tests      # 8 offline tests, no API key needed
python evals.py             # live evaluation, needs an API key
```

The unit tests replace the API client with a fake that replays scripted responses. They check retrieval, redaction, the secret-request block, that search results are passed back to the model, that tickets are saved with personal data removed, and the step limit.

`evals.py` runs five questions against the live model and checks two things for each: whether the answer cites the right article, and whether a ticket was opened only when it should be, with the right priority. One question is off-topic on purpose to check that the agent declines instead of guessing.

## Files

| File | Purpose |
|---|---|
| `agent.py` | Tool definitions, system prompt and the agent loop |
| `retriever.py` | TF-IDF search over the knowledge base |
| `guardrails.py` | Secret-request blocking and personal data redaction |
| `evals.py` | Live evaluation with pass/fail per question |
| `tests/test_agent.py` | Offline unit tests with a fake client |
