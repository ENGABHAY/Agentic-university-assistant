from datetime import datetime, timedelta, timezone
import jwt
from .config import JWT_SECRET


def create_token(user_id: int, sid: str, minutes: int = 30) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return jwt.encode({"sub": str(user_id), "sid": sid, "exp": exp}, JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> tuple[int, str]:
    p = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])  # raises on expiry/tamper
    return int(p["sub"]), p["sid"]
