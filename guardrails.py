"""Input and output checks that run outside the model."""
import re

# Patterns for personal data that should not be sent to the model or written to a ticket.
PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "phone": re.compile(r"\b(?:\+?1[ -.]?)?\(?\d{3}\)?[ -.]?\d{3}[ -.]?\d{4}\b"),
    "card": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
}
# Matches requests such as "tell me the password". These are refused outright.
SECRET_REQUEST = re.compile(r"\b(what is|tell me|give me|share)\b.*\b(password|passcode|mfa code|one-time code)\b", re.I)


def redact(text):
    """Replace personal data with placeholders before text is sent to the model or logged."""
    for label, pattern in PATTERNS.items():
        text = pattern.sub(f"[{label.upper()} REMOVED]", text)
    return text


def blocked(text):
    """Return a refusal message if the request asks for someone's secret, otherwise None."""
    if SECRET_REQUEST.search(text):
        return "The help desk never shares or asks for passwords or MFA codes. Use the self-service reset portal."
    return None
