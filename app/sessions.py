"""Short-lived, in-memory, encrypted ERP sessions. The key lives only in memory,
so a server restart invalidates every session. ERP passwords are never stored."""
import json, secrets, time
from cryptography.fernet import Fernet

TTL = 30 * 60
_f = Fernet(Fernet.generate_key())
_S: dict[str, tuple[float, str, bytes]] = {}


def create(username: str, state: dict) -> str:
    sid = secrets.token_urlsafe(24)
    _S[sid] = (time.time() + TTL, username, _f.encrypt(json.dumps(state).encode()))
    return sid


def get(sid: str):
    item = _S.get(sid)
    if not item or item[0] < time.time():
        _S.pop(sid, None)
        return None
    return item[1], json.loads(_f.decrypt(item[2]))


def delete(sid: str):
    _S.pop(sid, None)
