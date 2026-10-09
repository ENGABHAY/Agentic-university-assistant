from datetime import datetime, timezone
from sqlalchemy import ForeignKey, String, Text, DateTime, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
now = lambda: datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="student")  # student | admin
    erp_student_id: Mapped[str | None] = mapped_column(String(50), nullable=True)  # set server-side only
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"))
    role: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


def init_db():
    from .security import hash_password
    Base.metadata.create_all(engine)
    demo = [("abhay@example.com", "abhay123", "101", "student"),
            ("riya@example.com", "riya123", "202", "student"),
            ("admin@example.com", "admin123", None, "admin")]
    with SessionLocal() as db:
        for email, pw, erp_id, role in demo:
            if not db.scalar(select(User).where(User.email == email)):
                db.add(User(email=email, password_hash=hash_password(pw), erp_student_id=erp_id, role=role))
        db.commit()
