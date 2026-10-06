import json
import os
import webbrowser
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Browser paths on Windows — register them with webbrowser module
_BROWSER_PATHS = {
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "brave": r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
}

for name, path in _BROWSER_PATHS.items():
    if os.path.exists(path):
        webbrowser.register(name, None, webbrowser.BackgroundBrowser(path))

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/tasks",
]

_config = None
_base_dir = Path(__file__).parent


def _load_config():
    global _config
    if _config is None:
        with open(_base_dir / "config.json") as f:
            _config = json.load(f)
    return _config


def get_account_names() -> list[str]:
    return list(_load_config()["accounts"].keys())


def get_account_email(account: str) -> str:
    config = _load_config()
    if account not in config["accounts"]:
        raise ValueError(f"Account '{account}' not found. Available: {list(config['accounts'].keys())}")
    return config["accounts"][account]["email"]


def _is_revoked(e: Exception) -> bool:
    msg = str(e)
    return "invalid_grant" in msg or "Token has been expired or revoked" in msg


class _ReauthCredentials(Credentials):
    """Credentials that recover from a revoked refresh token on their own.

    googleapiclient refreshes credentials *inside* .execute() when Google
    answers 401 (e.g. the access token looked valid locally but Google had
    already revoked the grant). That refresh never goes through
    get_credentials(), so an invalid_grant there used to surface as a tool
    error. Overriding refresh() covers every call site: on invalid_grant it
    re-runs the OAuth consent flow, swaps the new tokens into this object
    (so the in-flight request is retried with them) and persists them.
    """

    _account: str = ""
    _token_path: Path | None = None
    _client_secret_path: Path | None = None

    def refresh(self, request):
        try:
            super().refresh(request)
        except RefreshError as e:
            if not (_is_revoked(e) and self._account and self._token_path):
                raise
            new = _run_oauth_flow(self._account, self._client_secret_path)
            self.token = new.token
            self._refresh_token = new.refresh_token
            self.expiry = new.expiry
        if self._token_path:
            _save_token(self._token_path, self)


def _save_token(token_path: Path, creds: Credentials) -> None:
    token_path.parent.mkdir(parents=True, exist_ok=True)
    with open(token_path, "w") as f:
        f.write(creds.to_json())


def _wrap(creds: Credentials, account: str, token_path: Path,
          client_secret_path: Path) -> _ReauthCredentials:
    wrapped = _ReauthCredentials.from_authorized_user_info(json.loads(creds.to_json()), SCOPES)
    wrapped._account = account
    wrapped._token_path = token_path
    wrapped._client_secret_path = client_secret_path
    return wrapped


def _run_oauth_flow(account: str, client_secret_path: Path) -> Credentials:
    config = _load_config()
    browser_pref = config["accounts"][account].get("browser", "default")
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
    browser_arg = None if browser_pref == "default" else browser_pref
    return flow.run_local_server(port=0, open_browser=True, browser=browser_arg)


def get_credentials(account: str) -> Credentials:
    config = _load_config()
    if account not in config["accounts"]:
        raise ValueError(f"Account '{account}' not found. Available: {list(config['accounts'].keys())}")

    creds_dir = _base_dir / config["credentials_dir"]
    token_path = creds_dir / "tokens" / f"{account}.json"
    client_secret_path = creds_dir / "client_secret.json"

    creds = None
    if token_path.exists():
        # Read the scopes Google actually granted straight from the stored file —
        # Credentials.from_authorized_user_file(path, SCOPES) silently overwrites
        # .scopes with whatever SCOPES we pass it, so checking creds.scopes here
        # would always look "sufficient" even when the real grant is narrower.
        try:
            with open(token_path) as f:
                stored_scopes = set(json.load(f).get("scopes", []))
        except Exception:
            stored_scopes = set()

        if not set(SCOPES).issubset(stored_scopes):
            # Missing a scope we now require (e.g. drive.file added after the
            # token was first issued). A refresh_token can't be upgraded in
            # place — asking Google to refresh with a wider scope than was
            # granted fails with invalid_scope. Force a fresh consent instead.
            token_path.unlink(missing_ok=True)
        else:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.valid:
        return _wrap(creds, account, token_path, client_secret_path)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as e:
            # Token revoked or expired — delete it and re-authenticate
            if _is_revoked(e):
                token_path.unlink(missing_ok=True)
                creds = _run_oauth_flow(account, client_secret_path)
            else:
                raise
    else:
        creds = _run_oauth_flow(account, client_secret_path)

    _save_token(token_path, creds)
    return _wrap(creds, account, token_path, client_secret_path)
