import time
import random
import logging
import json
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION ---
PORT = 5000
HOST = '0.0.0.0'  # Listen on all interfaces
DEBUG_MODE = True

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

def get_random_user_agent():
    """Returns a random user agent to help avoid detection."""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    ]
    return random.choice(user_agents)

def scrape_brickz(url):
    """
    Launches a stealth Chrome browser to scrape the given URL.
    Optimized for brickz.my transaction tables.
    """
    driver = None
    try:
        logger.info(f"Initializing Stealth Browser for: {url}")
        
        # Configure Chrome options for stealth
        options = uc.ChromeOptions()
        # options.add_argument('--headless=new') # NOTE: Headless sometimes triggers Cloudflare. 
        # If running on a server without a screen, use Xvfb or try '--headless=new'
        options.add_argument(f'--user-agent={get_random_user_agent()}')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        
        # Initialize the undetected_chromedriver
        # version_main allows you to pin a Chrome version if needed, usually auto is fine
        driver = uc.Chrome(options=options, use_subprocess=True)
        
        # Open URL
        driver.get(url)
        
        # RANDOM SLEEP: Essential for "Infinity" calls. 
        # Behaving like a human prevents IP bans.
        time.sleep(random.uniform(5, 8))
        
        # Wait for the table data to likely exist (checking for common table classes)
        # We assume there is a table with data
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "table"))
            )
        except Exception:
            logger.warning("Timeout waiting for table, page might have loaded differently or is empty.")

        # Get the HTML source
        page_source = driver.page_source
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # --- Custom Extraction Logic for Brickz ---
        # Attempting to find the transactions table
        data_extracted = []
        tables = soup.find_all('table')
        
        if tables:
            # Usually the main data table is the largest one or first relevant one
            main_table = tables[0] 
            
            # Extract headers
            headers = [th.get_text(strip=True) for th in main_table.find_all('th')]
            
            # Extract rows
            rows = main_table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if not cols:
                    continue # Skip header rows or empty rows
                
                # Create a dictionary for each row
                record = {}
                for i, col in enumerate(cols):
                    # Try to map to header if possible, else use index
                    field_name = headers[i] if i < len(headers) else f"column_{i}"
                    record[field_name] = col.get_text(strip=True)
                
                if record:
                    data_extracted.append(record)
        else:
            logger.warning("No tables found on the page.")
            
        result = {
            "status": "success",
            "url": url,
            "title": driver.title,
            "record_count": len(data_extracted),
            "data": data_extracted
        }
        
        return result

    except Exception as e:
        logger.error(f"Scraping failed: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }
    finally:
        # cleanup
        if driver:
            try:
                driver.quit()
            except:
                pass

@app.route('/scrape', methods=['POST'])
def handle_scrape_request():
    """
    API Endpoint callable by n8n.
    Expects JSON: { "link": "https://..." }
    """
    try:
        req_data = request.get_json()
        
        if not req_data or 'link' not in req_data:
            return jsonify({"status": "error", "message": "Missing 'link' parameter in JSON body"}), 400
            
        target_url = req_data['link']
        
        # Log the incoming request
        logger.info(f"Received scrape request for: {target_url}")
        
        # Run scraper
        data = scrape_brickz(target_url)
        
        return jsonify(data)

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    logger.info(f"Starting Scraper API on {HOST}:{PORT}")
    # Threaded=False is safer for Selenium in some contexts, but True handles concurrent requests better.
    # For Selenium, single-threaded or external queuing (like Redis) is usually safer to prevent browser crashes,
    # but for this simple example, we run directly.
    app.run(host=HOST, port=PORT)
