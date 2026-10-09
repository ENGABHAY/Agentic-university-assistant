from datetime import datetime, timedelta, timezone
import bcrypt, jwt
from .config import JWT_SECRET


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    return bcrypt.checkpw(pw.encode(), hashed.encode())


def create_token(user_id: int, minutes: int = 60) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return jwt.encode({"sub": str(user_id), "exp": exp}, JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> int:
    return int(jwt.decode(token, JWT_SECRET, algorithms=["HS256"])["sub"])  # raises on expiry/tamper
