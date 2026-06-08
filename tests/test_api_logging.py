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


if __name__ == "__main__":
    unittest.main()
