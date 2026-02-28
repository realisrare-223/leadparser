#!/usr/bin/env python3
"""
LeadParser API Server (Run this on your local PC)
=================================================
This runs locally and handles scraping.
The frontend (on Vercel) connects to this API.

Usage:
  python api_server.py

Your PC must be on for the frontend to work.
For remote access, use ngrok: ngrok http 5001
"""

import argparse
import json
import logging
import sqlite3
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from flask import Flask, jsonify, request
from flask_cors import CORS

sys.path.insert(0, str(Path(__file__).parent))

from exporters.sqlite_handler import SQLiteHandler
from utils.lead_scorer import LeadScorer
from scrapers.google_maps import GoogleMapsScraper

app = Flask(__name__)
CORS(app)  # Allow cross-origin from Vercel

# Global state
scraping_status = {
    "is_running": False,
    "current_niche": "",
    "current_city": "",
    "progress": 0,
    "total": 100,
    "message": "Ready",
    "last_run": None,
    "leads_found": 0
}

DB_PATH = Path("data/leads.db")
CONFIG_PATH = Path("config.yaml")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f)
    return {}


@app.route('/api/status')
def get_status():
    return jsonify(scraping_status)


@app.route('/api/leads')
def get_leads():
    """Get all qualified leads (no website + has phone)."""
    filter_type = request.args.get("filter", "all")
    
    if not DB_PATH.exists():
        return jsonify([])
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    query = """
        SELECT * FROM leads 
        WHERE (website IS NULL OR website = '') 
        AND (phone IS NOT NULL AND phone != '')
    """
    
    if filter_type == "hot":
        query += " AND lead_score >= 18"
    elif filter_type == "warm":
        query += " AND lead_score >= 12 AND lead_score < 18"
    elif filter_type == "medium":
        query += " AND lead_score >= 7 AND lead_score < 12"
    
    query += " ORDER BY lead_score DESC, date_added DESC"
    
    rows = conn.execute(query).fetchall()
    conn.close()
    
    return jsonify([dict(row) for row in rows])


@app.route('/api/stats')
def get_stats():
    if not DB_PATH.exists():
        return jsonify({"total": 0, "hot": 0, "warm": 0, "new_this_session": 0})
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    total = conn.execute("""
        SELECT COUNT(*) FROM leads 
        WHERE (website IS NULL OR website = '') 
        AND (phone IS NOT NULL AND phone != '')
    """).fetchone()[0]
    
    hot = conn.execute("""
        SELECT COUNT(*) FROM leads 
        WHERE (website IS NULL OR website = '') 
        AND (phone IS NOT NULL AND phone != '')
        AND lead_score >= 18
    """).fetchone()[0]
    
    warm = conn.execute("""
        SELECT COUNT(*) FROM leads 
        WHERE (website IS NULL OR website = '') 
        AND (phone IS NOT NULL AND phone != '')
        AND lead_score >= 12 AND lead_score < 18
    """).fetchone()[0]
    
    today = datetime.now().strftime("%Y-%m-%d")
    new_today = conn.execute("SELECT COUNT(*) FROM leads WHERE date_added = ?", (today,)).fetchone()[0]
    
    conn.close()
    
    return jsonify({"total": total, "hot": hot, "warm": warm, "new_this_session": new_today})


@app.route('/api/scrape', methods=['POST'])
def start_scrape():
    global scraping_status
    
    if scraping_status["is_running"]:
        return jsonify({"success": False, "error": "Already scraping"})
    
    data = request.json
    niche = data.get("niche", "").strip()
    city = data.get("city", "").strip()
    state = data.get("state", "").strip().upper()
    limit = data.get("limit", 100)
    
    if not niche or not city or not state:
        return jsonify({"success": False, "error": "Missing fields"})
    
    config = load_config()
    config["location"]["city"] = city
    config["location"]["state"] = state
    config["niches"] = [niche]
    config["scraping"]["max_results_per_niche"] = limit
    
    thread = threading.Thread(target=run_scraper, args=(config, niche, city, state, limit))
    thread.daemon = True
    thread.start()
    
    return jsonify({"success": True})


def run_scraper(config, niche, city, state, limit):
    global scraping_status
    
    scraping_status.update({
        "is_running": True,
        "current_niche": niche,
        "current_city": city,
        "progress": 0,
        "total": limit,
        "message": f"Starting: {niche} in {city}, {state}",
        "leads_found": 0
    })
    
    try:
        db = SQLiteHandler(config)
        db.open()
        
        leads_before = db._conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        session_id = db.start_session([niche], config)
        
        scraper = GoogleMapsScraper(config)
        listings = []
        
        try:
            scraper.start_browser()
            from selenium.webdriver.common.by import By
            from selenium.webdriver.common.keys import Keys
            
            search_query = f"{niche} in {city}, {state}"
            scraper.driver.get("https://www.google.com/maps")
            time.sleep(2)
            
            search_box = scraper.driver.find_element(By.ID, "searchboxinput")
            search_box.clear()
            search_box.send_keys(search_query)
            search_box.send_keys(Keys.RETURN)
            time.sleep(5)
            
            attempts = 0
            max_attempts = min(limit * 3, 300)
            
            while len(listings) < limit and attempts < max_attempts:
                try:
                    cards = scraper.driver.find_elements(By.CSS_SELECTOR, "[data-result-index]")
                    
                    for card in cards[len(listings):limit]:
                        try:
                            card.click()
                            time.sleep(2)
                            
                            lead = extract_data(scraper.driver, niche, city, state)
                            
                            if lead and not lead.get("website") and lead.get("phone"):
                                scorer = LeadScorer(config)
                                lead["lead_score"] = scorer.score(lead, niche, config)
                                lead["date_added"] = datetime.now().strftime("%Y-%m-%d")
                                
                                inserted, _ = db.insert_lead(lead)
                                if inserted:
                                    listings.append(lead)
                                    scraping_status["leads_found"] = len(listings)
                                    scraping_status["progress"] = len(listings)
                                    scraping_status["message"] = f"Found: {lead['name'][:30]}..."
                            
                            if len(listings) >= limit:
                                break
                        except Exception as e:
                            continue
                    
                    scraper.driver.execute_script("window.scrollBy(0, 500)")
                    time.sleep(2)
                    attempts += 1
                    
                except Exception as e:
                    break
                    
        finally:
            scraper.stop_browser()
        
        leads_after = db._conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        new_leads = leads_after - leads_before
        
        db.end_session({"total": len(listings), "new": new_leads, "duplicates": len(listings) - new_leads, "errors": 0})
        db.close()
        
        scraping_status.update({
            "is_running": False,
            "message": f"Complete! {new_leads} new leads",
            "last_run": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "progress": limit,
            "leads_found": new_leads
        })
        
    except Exception as e:
        logger.exception("Scrape failed")
        scraping_status.update({"is_running": False, "message": f"Error: {str(e)}"})


def extract_data(driver, niche, city, state):
    from selenium.webdriver.common.by import By
    import re
    
    lead = {"niche": niche, "city": city, "state": state, "data_source": "Google Maps"}
    
    try:
        name_elem = driver.find_element(By.CSS_SELECTOR, "h1")
        lead["name"] = name_elem.text.strip()
    except:
        return None
    
    try:
        text = driver.find_element(By.TAG_NAME, "body").text
        phone_match = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
        if phone_match:
            lead["phone"] = phone_match.group(0)
    except:
        lead["phone"] = ""
    
    try:
        addr_elem = driver.find_element(By.CSS_SELECTOR, "[data-tooltip='Address']")
        lead["address"] = addr_elem.text.strip()
    except:
        lead["address"] = ""
    
    try:
        website_elem = driver.find_element(By.CSS_SELECTOR, "[data-tooltip='Website']")
        lead["website"] = website_elem.text.strip()
    except:
        lead["website"] = ""
    
    try:
        rating_elem = driver.find_element(By.CSS_SELECTOR, "[role='img'][aria-label*='star']")
        rating_text = rating_elem.get_attribute("aria-label")
        rating_match = re.search(r'(\d+\.?\d*)', rating_text)
        if rating_match:
            lead["rating"] = rating_match.group(1)
    except:
        lead["rating"] = ""
    
    try:
        review_elem = driver.find_element(By.XPATH, "//span[contains(text(), 'review')]")
        count_match = re.search(r'([\d,]+)', review_elem.text)
        if count_match:
            lead["review_count"] = int(count_match.group(1).replace(",", ""))
    except:
        lead["review_count"] = 0
    
    lead["gmb_link"] = driver.current_url
    
    return lead


@app.route('/api/export/csv')
def export_csv():
    import csv
    import io
    from flask import Response
    
    if not DB_PATH.exists():
        return "No data", 404
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM leads WHERE (website IS NULL OR website = '') 
        AND (phone IS NOT NULL AND phone != '') ORDER BY lead_score DESC
    """).fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["name", "phone", "niche", "city", "state", "rating", "review_count", "lead_score", "gmb_link"])
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row[k] for k in writer.fieldnames if k in row.keys()})
    
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=leads.csv"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--ngrok", action="store_true", help="Print ngrok command for remote access")
    args = parser.parse_args()
    
    Path("data").mkdir(exist_ok=True)
    
    print(f"""
============================================================
         LeadParser API Server (Local Backend)
============================================================
Local URL:  http://localhost:{args.port}

To access from Vercel/Internet:
  1. Install ngrok: https://ngrok.com/download
  2. Run: ngrok http {args.port}
  3. Copy the https://xxxx.ngrok.io URL
  4. Paste it in frontend/src/config.js

This server must stay running for the frontend to work!
============================================================
    """)
    
    if args.ngrok:
        print("\n👉 Run this in another terminal:")
        print(f"   ngrok http {args.port}\n")
    
    app.run(host="0.0.0.0", port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
