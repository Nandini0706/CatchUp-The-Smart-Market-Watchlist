import os
from fastapi import Request
from clerk_backend_api import authenticate_request, AuthenticateRequestOptions

import datetime
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler # NEW
from contextlib import asynccontextmanager # NEW

import models
from database import engine, get_db, SessionLocal # IMPORTANT: added SessionLocal
import services
from services import get_stock_data

models.Base.metadata.create_all(bind=engine)

def run_market_check_job():
    """The function that runs in the background to check for alerts."""
    print(f"[{datetime.datetime.now()}] Running background market check...")
    
    db = SessionLocal()
    try:
        # We fetch ALL items for ALL users. 
        # (We removed the .filter(user_id == "demo_user")!)
        watchlist_items = db.query(models.WatchlistItem).all()
        
        # A temporary cache for this specific job run
        user_emails_cache = {}
        
        for item in watchlist_items:
            live_data = services.get_stock_data(item.ticker)
            if not live_data:
                continue
                
            delta_info = services.calculate_delta(live_data["current_price"], item.last_seen_price)
            
            if delta_info["is_meaningful"]:
                print(f"TRIGGER: {item.ticker} moved {delta_info['percent_change']}%. Alerting user {item.user_id}.")
                
                # 1. Resolve the user's email address dynamically
                if item.user_id not in user_emails_cache:
                    user_emails_cache[item.user_id] = services.get_user_email(item.user_id)
                
                user_email = user_emails_cache[item.user_id]
                
                if not user_email:
                    print(f"Could not find email for user {item.user_id}. Skipping alert.")
                    continue

                # 2. Get AI Context
                news = services.get_recent_news(item.ticker)
                ai_context = services.generate_context_summary(item.ticker, delta_info["percent_change"], news)
                
                # 3. Send the Email to the dynamic address
                services.send_alert_email(
                    ticker=item.ticker,
                    current_price=live_data["current_price"],
                    percent_change=delta_info["percent_change"],
                    ai_context=ai_context,
                    to_email=user_email # Passing the dynamic email!
                )
                
                # 4. Auto-Acknowledge
                item.last_seen_price = live_data["current_price"]
                item.last_seen_timestamp = datetime.datetime.utcnow()
                db.commit()
                
    except Exception as e:
        print(f"Error in background job: {e}")
    finally:
        db.close()

        
# Configure the scheduler to run alongside FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting background scheduler...", flush=True)
    scheduler = BackgroundScheduler()
    # Set next_run_time so it fires immediately on startup, then every 1 minute
    scheduler.add_job(
        run_market_check_job, 
        'interval', 
        minutes=1, 
        next_run_time=datetime.datetime.now()
    )
    scheduler.start()
    yield
    scheduler.shutdown()

# Add the lifespan to the FastAPI initialization
app = FastAPI(title="Smart Watchlist API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# Pydantic schema for validating incoming requests
class WatchlistCreate(BaseModel):
    ticker: str

def get_current_user(request: Request):
    """
    Dependency to extract the user ID from the Clerk JWT.
    If no valid token is provided, it blocks the request.
    """
    secret_key = os.getenv("CLERK_SECRET_KEY")
    if not secret_key:
        print("WARNING: Clerk Secret Key missing. Defaulting to demo_user.")
        return "demo_user"
        
    # Verify the token attached to the request
    state = authenticate_request(
        request, 
        AuthenticateRequestOptions(secret_key=secret_key)
    )
    
    if not state.is_signed_in:
        raise HTTPException(status_code=401, detail="Unauthenticated. Please log in.")
        
    # 'sub' (Subject) is the standard JWT field containing the unique User ID
    return state.payload.get("sub")

@app.get("/")
def root():
    return {
        "message": "Smart Watchlist API is running!", 
        "docs": "Visit http://localhost:8000/docs to test the API endpoints."
    }

@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Backend is running successfully!"}

@app.post("/api/watchlist")
def add_to_watchlist(
    item: WatchlistCreate, 
    db: Session = Depends(get_db), 
    user_id: str = Depends(get_current_user)
    ):
    """Add a stock to the watchlist and save its initial snapshot."""
    ticker_upper = item.ticker.upper()
    
    # 1. Fetch current data to save as the initial "last seen" snapshot
    stock_data = get_stock_data(ticker_upper)
    if not stock_data:
        raise HTTPException(status_code=404, detail="Ticker not found or API failed")

    # 2. Save to database
    db_item = models.WatchlistItem(
        user_id=user_id,
        ticker=ticker_upper,
        last_seen_price=stock_data["current_price"]
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    
    return {"message": f"Added {ticker_upper}", "snapshot": db_item}


@app.get("/api/watchlist")
def get_watchlist(
    db: Session = Depends(get_db), 
    user_id: str = Depends(get_current_user) # <--- NEW INJECTION
):
    """Retrieve the logged-in user's specific watchlist."""
    # We now filter by the real user_id instead of "demo_user"
    items = db.query(models.WatchlistItem).filter(models.WatchlistItem.user_id == user_id).all()
    return items

@app.get("/api/catchup")
def generate_catchup_feed(db: Session = Depends(get_db), user_id: str = Depends(get_current_user)):
    """
    The core engine. Compares DB state to live market state, filters noise, 
    and generates AI context for meaningful changes.
    """
    watchlist_items = db.query(models.WatchlistItem).filter(models.WatchlistItem.user_id == user_id).all()
    
    meaningful_changes = []
    noise = []
    
    for item in watchlist_items:
        live_data = get_stock_data(item.ticker)
        if not live_data:
            continue
            
        current_price = live_data["current_price"]
        
        delta_info = services.calculate_delta(
            current_price=current_price, 
            last_seen_price=item.last_seen_price
        )
        
        feed_item = {
            "ticker": item.ticker,
            "last_seen_price": round(item.last_seen_price, 2) if item.last_seen_price else None,
            "current_price": round(current_price, 2),
            "percent_change": delta_info["percent_change"],
            "last_seen_date": item.last_seen_timestamp,
            "ai_context": None # Default to None
        }
        
        if delta_info["is_meaningful"]:
            # --- NEW AI LOGIC ---
            # 1. Fetch the news
            news = services.get_recent_news(item.ticker)
            # 2. Ask the AI to summarize
            ai_summary = services.generate_context_summary(
                ticker=item.ticker, 
                percent_change=delta_info["percent_change"], 
                news_headlines=news
            )
            feed_item["ai_context"] = ai_summary
            # --------------------
            
            meaningful_changes.append(feed_item)
        else:
            noise.append(feed_item)
            
    return {
        "meaningful_changes": meaningful_changes,
        "noise": noise
    }

import datetime # Make sure datetime is imported at the top!

@app.post("/api/acknowledge")
def acknowledge_feed(db: Session = Depends(get_db), user_id: str = Depends(get_current_user)):
    """
    Updates the user's 'last_seen_price' to the current market price.
    This acts as a 'Mark as Read' button, resetting the delta engine.
    """
    watchlist_items = db.query(models.WatchlistItem).filter(models.WatchlistItem.user_id == user_id).all()
    
    for item in watchlist_items:
        # Get current data (this will use our newly built cache!)
        live_data = services.get_stock_data(item.ticker)
        
        if live_data:
            item.last_seen_price = live_data["current_price"]
            item.last_seen_timestamp = datetime.datetime.utcnow()
            
    db.commit()
    return {"message": "Watchlist synced. Baseline updated."}

@app.delete("/api/watchlist/{ticker}")
def delete_from_watchlist(ticker: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user)):
    """Removes a stock from the user's watchlist."""
    ticker_upper = ticker.upper()
    
    # 1. Find the item in the database
    # (Again, hardcoding "demo_user" for the MVP)
    db_item = db.query(models.WatchlistItem).filter(
        models.WatchlistItem.user_id == user_id,
        models.WatchlistItem.ticker == ticker_upper
    ).first()
    
    # 2. If it doesn't exist, return an error
    if not db_item:
        raise HTTPException(status_code=404, detail="Ticker not found in watchlist")
        
    # 3. Delete it and save the changes
    db.delete(db_item)
    db.commit()
    
    return {"message": f"Successfully removed {ticker_upper}"}