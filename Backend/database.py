from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# We use a local SQLite file named sql_app.db
SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"

# Setting check_same_thread=False is needed only for SQLite in FastAPI
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get the database session in our API routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()