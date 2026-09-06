# backend/seed_demo.py
import datetime
from database import SessionLocal
import models
import services

def seed_realistic_demo(user_id: str):
    db = SessionLocal()
    try:
        # Clear existing items for this user
        db.query(models.WatchlistItem).filter(models.WatchlistItem.user_id == user_id).delete()
        
        # Define realistic scenarios relative to live prices
        scenarios = [
            {"ticker": "NVDA", "multiplier": 0.952},  # ~ +5.0% (Meaningful Gain)
            {"ticker": "TSLA", "multiplier": 1.043},  # ~ -4.1% (Meaningful Drop)
            {"ticker": "AAPL", "multiplier": 0.995},  # ~ +0.5% (Noise / Stable)
            {"ticker": "MSFT", "multiplier": 1.008},  # ~ -0.8% (Noise / Stable)
        ]
        
        for s in scenarios:
            live = services.get_stock_data(s["ticker"])
            if not live:
                continue
            
            baseline = round(live["current_price"] * s["multiplier"], 2)
            item = models.WatchlistItem(
                user_id=user_id,
                ticker=s["ticker"],
                last_seen_price=baseline,
                last_seen_timestamp=datetime.datetime.utcnow() - datetime.timedelta(days=3)
            )
            db.add(item)
            
        db.commit()
        print("Demo data seeded successfully with realistic deltas!")
    finally:
        db.close()

if __name__ == "__main__":
    # Replace with your actual Clerk user ID from the database or JWT
    TARGET_USER_ID = "user_3IukE2NF0lAp9N9UITdS3Bknpqd" 
    seed_realistic_demo(TARGET_USER_ID)