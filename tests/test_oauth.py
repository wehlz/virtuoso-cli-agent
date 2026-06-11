import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from core.gemini_client import GeminiOAuthClient, load_oauth_credentials


def create_dummy_oauth_file(tmp_path: Path) -> Path:
    expiry = (datetime.utcnow() + timedelta(days=1)).isoformat() + "Z"
    credentials = {
        "token": "ya29.dummy_token",
        "refresh_token": "1//dummy_refresh",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "dummy-client-id.apps.googleusercontent.com",
        "client_secret": "dummy-client-secret",
        "scopes": ["https://www.googleapis.com/auth/cloud-platform"],
        "expiry": expiry,
    }
    file_path = tmp_path / "oauth_creds.json"
    file_path.write_text(json.dumps(credentials))
    return file_path


def test_load_oauth_credentials(tmp_path: Path):
    file_path = create_dummy_oauth_file(tmp_path)
    creds = load_oauth_credentials(str(file_path))
    assert creds.token == "ya29.dummy_token"
    assert creds.refresh_token == "1//dummy_refresh"


def test_gemini_oauth_client_headers(tmp_path: Path):
    file_path = create_dummy_oauth_file(tmp_path)
    client = GeminiOAuthClient(model="gemini-1.5-flash", oauth_creds_path=str(file_path), temperature=0.2)
    headers = client._headers()
    assert headers["Authorization"].startswith("Bearer ")
    assert headers["Content-Type"] == "application/json"
