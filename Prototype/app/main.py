import logging
from contextlib import asynccontextmanager
import time
from collections import defaultdict, deque
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from .agent import run_agent
from .db import ChatMessage, ChatSession, SessionLocal, User, init_db
from .security import create_token, decode_token, verify_password

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("uniassistant")  # never log passwords, tokens, or ERP data


@asynccontextmanager
async def lifespan(_):
    init_db()
    yield


app = FastAPI(title="Agentic University Assistant", lifespan=lifespan)


def get_db():
    with SessionLocal() as db:
        yield db


def current_user(authorization: str = Header(default=""), db=Depends(get_db)) -> User:
    try:
        uid = decode_token(authorization.removeprefix("Bearer ").strip())
    except Exception:
        raise HTTPException(401, "Invalid or expired token")
    user = db.get(User, uid)
    if not user:
        raise HTTPException(401, "Unknown user")
    return user


class LoginIn(BaseModel):
    email: str
    password: str


class ChatIn(BaseModel):
    message: str
    session_id: int | None = None


@app.post("/login")
def login(body: LoginIn, db=Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    return {"access_token": create_token(user.id), "role": user.role}


@app.get("/profile")
def profile(user: User = Depends(current_user)):
    return {"email": user.email, "role": user.role}


@app.post("/chat")
async def chat(body: ChatIn, user: User = Depends(current_user), db=Depends(get_db)):
    sess = db.get(ChatSession, body.session_id) if body.session_id else None
    if sess is None:
        sess = ChatSession(user_id=user.id); db.add(sess); db.commit()
    if sess.user_id != user.id:
        raise HTTPException(403, "Not your chat session")

    rows = db.scalars(select(ChatMessage).where(ChatMessage.session_id == sess.id)
                      .order_by(ChatMessage.id.desc()).limit(10)).all()[::-1]
    history = [(m.role, m.message) for m in rows]  # only user/assistant text; no raw tool/ERP output

    out = await run_agent(body.message, user.erp_student_id, history)
    db.add_all([ChatMessage(session_id=sess.id, role="user", message=body.message),
                ChatMessage(session_id=sess.id, role="assistant", message=out["answer"])])
    db.commit()
    log.info("chat user=%s tools=%s", user.id, out["tools_used"])
    return {"session_id": sess.id, **out}


# ---------- Guest mode (no login, documents only) ----------
_guest_hits = defaultdict(deque)


def guest_rate_limit(request: Request):
    q, t = _guest_hits[request.client.host], time.time()
    while q and t - q[0] > 60:
        q.popleft()
    if len(q) >= 10:  # max 10 questions per minute per IP
        raise HTTPException(429, "Too many requests. Please wait a minute.")
    q.append(t)


class GuestChatIn(BaseModel):
    message: str
    history: list[dict] = []


@app.post("/chat/guest")
async def chat_guest(body: GuestChatIn, _=Depends(guest_rate_limit)):
    history = [(m["role"], str(m.get("content", ""))[:2000]) for m in body.history[-6:]
               if m.get("role") in ("user", "assistant")]
    out = await run_agent(body.message[:1000], None, history)  # None = no ERP tools
    return out