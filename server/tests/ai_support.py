"""A fake Gemini API for tests: scripted replies, and checks on every request like the real API's requirements."""

import json

import httpx

from app.core.config import settings
from app.services.ai import gemini

KEY = "AIza" + "S" * 35
MODEL = "gemini-2.5-flash"


class FakeGemini:
    """Answers generateContent from ``replies``: a dict or str becomes the model's JSON text; an int is an HTTP error
    status; {"status": n, "message": m} is an error with that message; {"raw": body} is returned as-is. With no
    scripted reply it answers 503, as an unavailable service would."""

    def __init__(self):
        self.replies: list = []
        self.requests: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append({"url": str(request.url), "headers": dict(request.headers), "body": body})
        assert request.headers.get("x-goog-api-key") == KEY
        assert KEY not in str(request.url)
        assert str(request.url).endswith(f"/models/{MODEL}:generateContent")
        roles = [c["role"] for c in body["contents"]]
        assert roles[0] == "user" and all(a != b for a, b in zip(roles, roles[1:], strict=False)), roles
        reply = self.replies.pop(0) if self.replies else 503
        if isinstance(reply, int):
            return httpx.Response(reply, json={"error": {"message": f"failure {reply} for key {KEY}"}})
        if isinstance(reply, dict) and "status" in reply:
            return httpx.Response(reply["status"], json={"error": {"message": reply["message"]}})
        if isinstance(reply, dict) and "raw" in reply:
            return httpx.Response(200, json=reply["raw"])
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": "STOP"}],
                "usageMetadata": {"promptTokenCount": 420, "candidatesTokenCount": 37},
                "modelVersion": MODEL,
            },
        )


def install(monkeypatch) -> FakeGemini:
    monkeypatch.setattr(settings, "GEMINI_API_KEY", KEY)
    monkeypatch.setattr(settings, "GEMINI_MODEL", MODEL)
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_PER_MINUTE", 100)
    monkeypatch.setattr(gemini, "last", gemini.Outcome())
    fake = FakeGemini()
    gemini.set_transport(httpx.MockTransport(fake.handler))
    return fake
