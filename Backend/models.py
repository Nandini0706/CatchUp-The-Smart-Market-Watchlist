from sqlalchemy import Column, Integer, String, Float, DateTime
from database import Base
import datetime

class WatchlistItem(Base):
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, default="demo_user", index=True) # Hardcoded for hackathon MVP
    ticker = Column(String, index=True)
    
    # This is the core of our innovation: saving the snapshot!
    last_seen_price = Column(Float, nullable=True)
    last_seen_timestamp = Column(DateTime, default=datetime.datetime.utcnow)