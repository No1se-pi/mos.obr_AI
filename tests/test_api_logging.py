import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.web_transcript_store import WebTranscriptStore

try:
    from fastapi.testclient import TestClient

    from app.interfaces import api
except ModuleNotFoundError:
    TestClient = None
    api = None


class ApiLoggingTest(unittest.TestCase):
    def test_web_transcript_store_writes_jsonl_and_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = WebTranscriptStore(Path(tmp_dir))

            store.append_event(
                site_user_id="demo/user",
                session_id="session-1",
                role="assistant",
                text="Ответ по колледжам",
                mode="faq",
                extra={"expired_previous_session": False},
            )

            jsonl_path = Path(tmp_dir) / "demo_user.jsonl"
            txt_path = Path(tmp_dir) / "demo_user.txt"

            self.assertTrue(jsonl_path.exists())
            self.assertTrue(txt_path.exists())

            event = json.loads(jsonl_path.read_text(encoding="utf-8").strip())
            self.assertEqual(event["channel"], "web")
            self.assertEqual(event["mode"], "faq")
            self.assertEqual(event["text"], "Ответ по колледжам")
            self.assertIn("ASSISTANT", txt_path.read_text(encoding="utf-8"))

    def test_logs_api_is_disabled_by_default(self) -> None:
        if TestClient is None or api is None:
            self.skipTest("fastapi is not installed in this environment")

        with patch.dict(os.environ, {"API_LOGS_ENABLED": "false"}, clear=False):
            response = TestClient(api.app).get("/api/logs/list")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "API logs are disabled")

    def test_logs_api_allows_access_when_enabled_without_token(self) -> None:
        if TestClient is None or api is None:
            self.skipTest("fastapi is not installed in this environment")

        with patch.dict(os.environ, {"API_LOGS_ENABLED": "true", "API_LOGS_TOKEN": ""}, clear=False):
            response = TestClient(api.app).get("/api/logs/list")

        self.assertEqual(response.status_code, 200)
        self.assertIn("files", response.json())

    def test_logs_api_requires_bearer_token_when_configured(self) -> None:
        if TestClient is None or api is None:
            self.skipTest("fastapi is not installed in this environment")

        env = {"API_LOGS_ENABLED": "true", "API_LOGS_TOKEN": "secret-token"}
        client = TestClient(api.app)

        with patch.dict(os.environ, env, clear=False):
            missing = client.get("/api/logs/list")
            wrong = client.get("/api/logs/list", headers={"Authorization": "Bearer wrong"})
            correct = client.get("/api/logs/list", headers={"Authorization": "Bearer secret-token"})

        self.assertEqual(missing.status_code, 403)
        self.assertEqual(wrong.status_code, 403)
        self.assertEqual(correct.status_code, 200)

    def test_health_reports_rag_and_ollama_ready(self) -> None:
        if api is None:
            self.skipTest("fastapi is not installed in this environment")

        counts = {"total": 3, "faq": 1, "college": 1, "specialty": 1}

        with (
            patch.object(api, "check_database_ready", return_value=True),
            patch.object(api, "get_document_counts", return_value=counts),
            patch.object(api, "check_ollama_ready", return_value=True),
        ):
            result = api.health()

        self.assertTrue(result["database_ready"])
        self.assertTrue(result["documents_ready"])
        self.assertTrue(result["rag_ready"])
        self.assertTrue(result["ollama_ready"])
        self.assertEqual(result["documents_total"], 3)

    def test_health_does_not_fail_when_ollama_is_unavailable(self) -> None:
        if api is None:
            self.skipTest("fastapi is not installed in this environment")

        counts = {"total": 3, "faq": 1, "college": 1, "specialty": 1}

        with (
            patch.object(api, "check_database_ready", return_value=True),
            patch.object(api, "get_document_counts", return_value=counts),
            patch.object(api, "check_ollama_ready", return_value=False),
        ):
            result = api.health()

        self.assertTrue(result["rag_ready"])
        self.assertFalse(result["ollama_ready"])

    def test_public_dialog_path_exists_and_legacy_can_be_disabled(self) -> None:
        if TestClient is None or api is None:
            self.skipTest("fastapi is not installed in this environment")

        client = TestClient(api.app)
        public_response = client.post(api.PUBLIC_CHAT_PATH, json={})
        self.assertEqual(public_response.status_code, 422)

        payload = {"user_id": "u1", "message": "Привет"}
        with patch.dict(os.environ, {"API_LEGACY_CHAT_ENABLED": "false"}, clear=False):
            legacy_response = client.post("/api/chat", json=payload)

        self.assertEqual(legacy_response.status_code, 404)

    def test_rejects_disallowed_origin_before_processing(self) -> None:
        if TestClient is None or api is None:
            self.skipTest("fastapi is not installed in this environment")

        api.rate_limit_hits.clear()
        with patch.dict(os.environ, {"API_CORS_ORIGINS": "https://allowed.example"}, clear=False):
            response = TestClient(api.app).post(
                api.PUBLIC_CHAT_PATH,
                json={},
                headers={"Origin": "https://evil.example"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Origin is not allowed")

    def test_allows_same_origin_without_explicit_cors_entry(self) -> None:
        if TestClient is None or api is None:
            self.skipTest("fastapi is not installed in this environment")

        api.rate_limit_hits.clear()
        with patch.dict(os.environ, {"API_CORS_ORIGINS": "https://allowed.example"}, clear=False):
            response = TestClient(api.app).post(
                api.PUBLIC_CHAT_PATH,
                json={},
                headers={"Origin": "http://testserver", "Host": "testserver"},
            )

        self.assertEqual(response.status_code, 422)

    def test_rate_limits_dialog_posts(self) -> None:
        if TestClient is None or api is None:
            self.skipTest("fastapi is not installed in this environment")

        api.rate_limit_hits.clear()
        client = TestClient(api.app)
        with patch.dict(os.environ, {"API_RATE_LIMIT_PER_MINUTE": "1"}, clear=False):
            first = client.post(api.PUBLIC_CHAT_PATH, json={})
            second = client.post(api.PUBLIC_CHAT_PATH, json={})

        self.assertEqual(first.status_code, 422)
        self.assertEqual(second.status_code, 429)

    def test_rate_limit_does_not_trust_forwarded_for_by_default(self) -> None:
        if TestClient is None or api is None:
            self.skipTest("fastapi is not installed in this environment")

        api.rate_limit_hits.clear()
        client = TestClient(api.app)
        env = {"API_RATE_LIMIT_PER_MINUTE": "1", "API_TRUST_PROXY_HEADERS": "false"}
        with patch.dict(os.environ, env, clear=False):
            first = client.post(api.PUBLIC_CHAT_PATH, json={}, headers={"X-Forwarded-For": "10.0.0.1"})
            second = client.post(api.PUBLIC_CHAT_PATH, json={}, headers={"X-Forwarded-For": "10.0.0.2"})

        self.assertEqual(first.status_code, 422)
        self.assertEqual(second.status_code, 429)

    def test_rejects_oversized_body(self) -> None:
        if TestClient is None or api is None:
            self.skipTest("fastapi is not installed in this environment")

        with patch.object(api, "MAX_BODY_BYTES", 32):
            response = TestClient(api.app).post(api.PUBLIC_CHAT_PATH, json={"user_id": "u1", "message": "x" * 100})

        self.assertEqual(response.status_code, 413)


if __name__ == "__main__":
    unittest.main()
