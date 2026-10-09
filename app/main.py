import logging, time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from mcp_server.erp import ERPLoginError, login as erp_login, start_login
from . import sessions
from .agent import run_agent
from .db import ChatMessage, ChatSession, SessionLocal, User, init_db
from .security import create_token, decode_token

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("uniassistant")  # never log passwords, tokens, cookies or ERP data


@asynccontextmanager
async def lifespan(_):
    init_db()
    yield


app = FastAPI(title="Agentic University Assistant", lifespan=lifespan)
_hits = defaultdict(deque)


def limiter(bucket: str, limit: int):
    def dep(request: Request):
        q, t = _hits[(bucket, request.client.host)], time.time()
        while q and t - q[0] > 60:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(429, "Too many requests. Please wait a minute.")
        q.append(t)
    return dep


def get_db():
    with SessionLocal() as db:
        yield db


def current_user(authorization: str = Header(default=""), db=Depends(get_db)) -> User:
    try:
        uid, sid = decode_token(authorization.removeprefix("Bearer ").strip())
    except Exception:
        raise HTTPException(401, "Invalid or expired token")
    sess = sessions.get(sid)
    if not sess:
        raise HTTPException(401, "ERP session expired. Please log in again.")
    user = db.get(User, uid)
    if not user or user.email != sess[0]:
        raise HTTPException(401, "Session does not match user")
    user.erp_state, user.sid = sess[1], sid  # transient, not stored in DB
    return user


class LoginIn(BaseModel):
    username: str
    password: str
    pending_id: str | None = None
    captcha: str = ""


class ChatIn(BaseModel):
    message: str
    session_id: int | None = None


class GuestChatIn(BaseModel):
    message: str
    history: list[dict] = []


@app.post("/login/start", dependencies=[Depends(limiter("start", 10))])
async def login_start():
    try:
        pid, img = await start_login()
    except Exception as e:
        log.error("ERP start error: %s: %s", type(e).__name__, str(e)[:200])
        raise HTTPException(502, "Could not reach the ERP. Please try again later.")
    return {"pending_id": pid, "captcha_image": img}


@app.post("/login", dependencies=[Depends(limiter("login", 5))])
async def login(body: LoginIn, db=Depends(get_db)):
    key = body.username.strip().lower()
    try:
        state = await erp_login(key, body.password, body.pending_id, body.captcha.strip())  # real ERP verifies the credentials; password discarded after
    except ERPLoginError as e:
        raise HTTPException(401, str(e))
    except Exception as e:
        log.error("ERP login error: %s: %s", type(e).__name__, str(e)[:200])
        raise HTTPException(502, "Could not reach the ERP. Please try again later.")
    user = db.scalar(select(User).where(User.email == key))
    if not user:
        user = User(email=key, password_hash="!erp-managed", erp_student_id=key)
        db.add(user); db.commit()
    return {"access_token": create_token(user.id, sessions.create(key, state))}


@app.post("/logout")
def logout(user: User = Depends(current_user)):
    sessions.delete(user.sid)
    return {"ok": True}


@app.post("/chat")
async def chat(body: ChatIn, user: User = Depends(current_user), db=Depends(get_db)):
    sess = db.get(ChatSession, body.session_id) if body.session_id else None
    if sess is None:
        sess = ChatSession(user_id=user.id); db.add(sess); db.commit()
    if sess.user_id != user.id:
        raise HTTPException(403, "Not your chat session")
    rows = db.scalars(select(ChatMessage).where(ChatMessage.session_id == sess.id)
                      .order_by(ChatMessage.id.desc()).limit(10)).all()[::-1]
    history = [(m.role, m.message) for m in rows]  # only user/assistant text; no raw ERP output
    try:
        out = await run_agent(body.message, user.erp_state, history)
    except Exception as e:
        if "ERPSessionExpired" in repr(e) or "session expired" in repr(e).lower():
            sessions.delete(user.sid)
            raise HTTPException(401, "ERP session expired. Please log in again.")
        raise
    db.add_all([ChatMessage(session_id=sess.id, role="user", message=body.message),
                ChatMessage(session_id=sess.id, role="assistant", message=out["answer"])])
    db.commit()
    log.info("chat user=%s tools=%s", user.id, out["tools_used"])
    return {"session_id": sess.id, **out}


@app.post("/chat/guest", dependencies=[Depends(limiter("guest", 10))])
async def chat_guest(body: GuestChatIn):
    history = [(m["role"], str(m.get("content", ""))[:2000]) for m in body.history[-6:]
               if m.get("role") in ("user", "assistant")]
    return await run_agent(body.message[:1000], None, history)
