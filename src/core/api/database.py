"""Database session management for FastAPI."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.core.models.node import Base

DATABASE_URL = "postgresql://dc:dcpass@localhost:5432/decay_clocks"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
