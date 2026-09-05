import yfinance as yf

import requests
import resend
import os
import time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv() # Loads the .env file

# --- NEW GROQ INITIALIZATION ---
# We still use the OpenAI client, but we point it to Groq's servers!
try:
    client = OpenAI(
        api_key=os.getenv("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1"
    )
    AI_ENABLED = True
except Exception as e:
    print(f"Failed to initialize AI: {e}")
    AI_ENABLED = False


# --- SIMPLE TTL CACHE ---
# Stores data like: {"AAPL": {"data": {...}, "timestamp": 169000000}}
market_cache = {}
CACHE_TTL = 60 # Cache data for 60 seconds

def get_stock_data(ticker: str):
    """
    Fetches the latest price and volume. 
    Includes a 60-second TTL cache to prevent API rate limiting.
    """
    current_time = time.time()
    
    # 1. Check if we have valid cached data
    if ticker in market_cache:
        cached_entry = market_cache[ticker]
        if current_time - cached_entry["timestamp"] < CACHE_TTL:
            print(f"Serving {ticker} from cache!")
            return cached_entry["data"]

    # 2. If no cache or cache is expired, fetch from API
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        
        if hist.empty:
            return None
            
        latest_price = float(hist['Close'].iloc[-1])
        latest_volume = int(hist['Volume'].iloc[-1])
        
        data = {
            "ticker": ticker.upper(),
            "current_price": latest_price,
            "volume": latest_volume
        }
        
        # 3. Save to cache before returning
        market_cache[ticker] = {
            "data": data,
            "timestamp": current_time
        }
        print(f"Fetched {ticker} from Yahoo API")
        return data
        
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return None



def calculate_delta(current_price: float, last_seen_price: float) -> dict:
    """
    Calculates the percentage change safely.
    Returns a dictionary with the raw percentage and a boolean indicating if it's 'meaningful'.
    """
    if not last_seen_price or last_seen_price == 0:
        return {"percent_change": 0.0, "is_meaningful": False}
        
    # Standard percentage change formula
    diff = current_price - last_seen_price
    percent_change = (diff / last_seen_price) * 100
    
    # Define our threshold (e.g., 3%)
    # We use abs() because a -5% drop is just as meaningful as a +5% gain.
    is_meaningful = abs(percent_change) >= 3.0
    
    return {
        "percent_change": round(percent_change, 2),
        "is_meaningful": is_meaningful
    }

def get_recent_news(ticker: str) -> str:
    """Fetches recent news headlines for a ticker safely."""
    try:
        stock = yf.Ticker(ticker)
        news_items = stock.news
        if not news_items:
            return "No recent news found."
            
        # Safely extract titles in case Yahoo changes their dictionary structure again
        headlines = []
        for item in news_items[:5]:
            # Some versions use 'title', others nest it inside 'content'
            title = item.get('title') or item.get('content', {}).get('title') or "Untitled"
            headlines.append(title)
            
        return " | ".join(headlines)
    except Exception as e:
        print(f"Error fetching news for {ticker}: {e}")
        return "Error fetching news."

def generate_context_summary(ticker: str, percent_change: float, news_headlines: str) -> str:
    """Uses an LLM to explain the price movement."""
    
    if not AI_ENABLED or not os.getenv("GROQ_API_KEY"):
        return f"[Mock AI]: {ticker} moved {percent_change}% likely due to broader market conditions."

    prompt = f"""
    You are an expert financial analyst. 
    The stock {ticker} has moved {percent_change}% since the user last checked.
    Here are the most recent news headlines for {ticker}:
    {news_headlines}
    
    In ONE short sentence, explain why the stock likely moved this way based ONLY on the headlines. 
    If the headlines do not explain the movement, say: "Moved on market volatility without a clear news catalyst."
    Keep it under 20 words.
    """

    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b", # UPDATED to a currently active Groq model
            messages=[
                {"role": "system", "content": "You are a concise financial assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=50,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"AI Error: {e}")
        return "Explanation currently unavailable."

def get_user_email(user_id: str) -> str:
    """Fetches the user's email address directly from Clerk's Backend API."""
    clerk_secret = os.getenv("CLERK_SECRET_KEY")
    if not clerk_secret:
        return None
        
    try:
        headers = {"Authorization": f"Bearer {clerk_secret}"}
        response = requests.get(f"https://api.clerk.com/v1/users/{user_id}", headers=headers)
        
        if response.status_code == 200:
            user_data = response.json()
            # Clerk returns an array of email_addresses
            if user_data.get("email_addresses") and len(user_data["email_addresses"]) > 0:
                return user_data["email_addresses"][0]["email_address"]
    except Exception as e:
        print(f"Error fetching email from Clerk for user {user_id}: {e}")
        
    return None

def send_alert_email(ticker: str, current_price: float, percent_change: float, ai_context: str, to_email: str):
    """Sends an email alert using the Resend API to a dynamic user."""
    resend.api_key = os.getenv("RESEND_API_KEY")
    
    if not resend.api_key or not to_email:
        print("Email configuration or recipient missing. Skipping alert.")
        return

    direction = "Up" if percent_change > 0 else "Down"
    
    html_content = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden;">
        <div style="background-color: #0f172a; padding: 20px; color: white;">
            <h2 style="margin: 0;">🚨 Meaningful Change Alert</h2>
        </div>
        <div style="padding: 24px; background-color: #f8fafc;">
            <h1 style="margin-top: 0; color: #0f172a;">{ticker} is {direction} {abs(percent_change)}%</h1>
            <p style="font-size: 16px; color: #475569;">Current Price: <strong>${current_price:.2f}</strong></p>
            
            <div style="background-color: #e0e7ff; padding: 16px; border-left: 4px solid #4f46e5; border-radius: 4px; margin-top: 24px;">
                <p style="margin: 0; color: #3730a3; font-size: 14px; text-transform: uppercase; font-weight: bold;">AI Insight</p>
                <p style="margin: 8px 0 0 0; color: #1e1b4b; font-size: 16px;">{ai_context}</p>
            </div>
            
            <p style="margin-top: 24px; font-size: 14px; color: #64748b;">
                Your baseline has been automatically updated. Open your Smart Watchlist dashboard to see more.
            </p>
        </div>
    </div>
    """

    try:
        response = resend.Emails.send({
            "from": "Acme <onboarding@resend.dev>", # Change this when you buy a domain! e.g., "Alerts <alerts@yourdomain.com>"
            "to": to_email,
            "subject": f"Alert: {ticker} moved {percent_change}%",
            "html": html_content
        })
        print(f"Email sent successfully for {ticker} to {to_email}!")
    except Exception as e:
        print(f"Failed to send email: {e}")