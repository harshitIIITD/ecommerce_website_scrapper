import streamlit as st
import pandas as pd
import json
import time
import random
from io import StringIO
import base64
from myntrascrapper import MyntraScraper
import datetime
import os
import hashlib
from xlsxwriter import Workbook
import pickle
from pathlib import Path
import uuid

# Add these imports for user state management
import sqlite3
import json
import datetime
from datetime import timedelta
from datetime import datetime, timedelta

# Constants for supported platforms (unchanged)
PLATFORMS = {
    "myntra": {"name": "Myntra", "logo": "https://www.perficient.com/-/media/images/insights/research/case-study-logos/myntra_logo-min.ashx", "color": "#e91e63"}, 
    "flipkart": {"name": "Flipkart", "logo": "https://static-assets-web.flixcart.com/fk-p-linchpin-web/fk-cp-zion/img/flipkart-plus_8d85f4.png", "color": "#2874f0"},
    "amazon": {"name": "Amazon", "logo": "https://www.amazon.com/favicon.ico", "color": "#ff9900"},
    "tatacliq": {"name": "Tata CLiQ", "logo": "https://www.tatacliq.com/assets/images/favicon.ico", "color": "#da1c5c"},
    "ajio": {"name": "AJIO", "logo": "https://assets.ajio.com/static/img/favicon.ico", "color": "#2e73ab"}
}

# Cache configuration (unchanged)
CACHE_DIR = Path("cache")
CACHE_EXPIRY_DAYS = 7  # Cache entries expire after 7 days

# User state configuration
USER_STATE_DIR = Path("user_state")
USER_STATE_DB = USER_STATE_DIR / "user_state.db"
USER_STATE_EXPIRY_DAYS = 30  # User state expires after 30 days

# Create necessary directories
if not CACHE_DIR.exists():
    CACHE_DIR.mkdir()
    
if not USER_STATE_DIR.exists():
    USER_STATE_DIR.mkdir()
# Add after the imports section
def adapt_datetime(dt):
    """Convert datetime to ISO format for SQLite storage."""
    return dt.isoformat()

def convert_datetime(s):
    """Convert ISO format string from SQLite back to datetime."""
    return datetime.fromisoformat(s)

# Initialize the user state database
def init_user_state_db():
    """Initialize the user state database if it doesn't exist."""
    # Register datetime adapters for SQLite
    sqlite3.register_adapter(datetime, adapt_datetime)
    sqlite3.register_converter("timestamp", convert_datetime)
    
    conn = sqlite3.connect(str(USER_STATE_DB), detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = conn.cursor()
    
    
    # Create user state table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_state (
        user_id TEXT PRIMARY KEY,
        state_data TEXT,
        last_updated TIMESTAMP
    )
    ''')
    
    # Create history table for tracking user searches
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS search_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        platform TEXT,
        search_query TEXT,
        num_results INTEGER,
        timestamp TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES user_state(user_id)
    )
    ''')
    
    conn.commit()
    conn.close()

# Initialize the user state database
init_user_state_db()

# User state management functions
def get_user_id():
    """Get or create a unique user ID for the current session."""
    if 'user_id' not in st.session_state:
        # Check if user_id exists in query parameters
        user_id = st.query_params.get("user_id", None)
        
        if not user_id:
            # Generate a new user ID
            user_id = str(uuid.uuid4())
            st.query_params["user_id"] = user_id
        
        st.session_state['user_id'] = user_id
    
    return st.session_state['user_id']

def save_user_state(state_data):
    """Save user state to the database."""
    user_id = get_user_id()
    
    conn = sqlite3.connect(str(USER_STATE_DB), detect_types=sqlite3.PARSE_DECLTYPES)
    cursor = conn.cursor()
    
    # Convert the state data to JSON string
    state_json = json.dumps(state_data)
    
    # Insert or update the user state
    cursor.execute('''
    INSERT OR REPLACE INTO user_state (user_id, state_data, last_updated)
    VALUES (?, ?, ?)
    ''', (user_id, state_json, datetime.now()))
    
    conn.commit()
    conn.close()

def get_user_state():
    """Retrieve user state from the database."""
    user_id = get_user_id()
    
    conn = sqlite3.connect(str(USER_STATE_DB))
    cursor = conn.cursor()
    
    # Retrieve the user state
    cursor.execute('SELECT state_data FROM user_state WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    conn.close()
    
    if result:
        try:
            return json.loads(result[0])
        except json.JSONDecodeError:
            return {}
    
    return {}

def add_to_search_history(platform, search_query, num_results):
    """Add a search to the user's history."""
    user_id = get_user_id()
    
    conn = sqlite3.connect(str(USER_STATE_DB))
    cursor = conn.cursor()
    
    # Add the search to history
    cursor.execute('''
    INSERT INTO search_history (user_id, platform, search_query, num_results, timestamp)
    VALUES (?, ?, ?, ?, ?)
    ''', (user_id, platform, search_query, num_results, datetime.now()))
    
    conn.commit()
    conn.close()

def get_search_history(limit=10):
    """Get the user's search history."""
    user_id = get_user_id()
    
    conn = sqlite3.connect(str(USER_STATE_DB))
    cursor = conn.cursor()
    
    # Retrieve the search history
    cursor.execute('''
    SELECT platform, search_query, num_results, timestamp 
    FROM search_history 
    WHERE user_id = ? 
    ORDER BY timestamp DESC
    LIMIT ?
    ''', (user_id, limit))
    
    history = cursor.fetchall()
    conn.close()
    
    # Convert to list of dictionaries
    return [
        {
            "platform": item[0],
            "search_query": item[1],
            "num_results": item[2],
            "timestamp": item[3]
        }
        for item in history
    ]

def clear_expired_user_states():
    """Clear expired user states from the database."""
    conn = sqlite3.connect(str(USER_STATE_DB))
    cursor = conn.cursor()
    
    # Calculate the expiry date
    expiry_date = datetime.now() - timedelta(days=USER_STATE_EXPIRY_DAYS)
    
    # Delete expired user states
    cursor.execute('DELETE FROM user_state WHERE last_updated < ?', (expiry_date,))
    
    # Count deleted rows
    deleted_count = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    return deleted_count

# Existing cache functions (unchanged)
def get_cache_key(platform, product_id):
    """Generate a unique cache key for a product."""
    key = f"{platform}_{product_id}"
    return hashlib.md5(key.encode()).hexdigest()

def get_from_cache(platform, product_id):
    """Retrieve product data from cache if available and not expired."""
    cache_key = get_cache_key(platform, product_id)
    cache_file = CACHE_DIR / f"{cache_key}.pkl"
    
    if cache_file.exists():
        # Check if cache is expired
        file_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
        if file_age.days < CACHE_EXPIRY_DAYS:
            try:
                with open(cache_file, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"Error loading cache: {e}")
    
    return None

def save_to_cache(platform, product_id, data):
    """Save product data to cache."""
    if data:
        cache_key = get_cache_key(platform, product_id)
        cache_file = CACHE_DIR / f"{cache_key}.pkl"
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(data, f)
        except Exception as e:
            print(f"Error saving to cache: {e}")

def download_link(object_to_download, download_filename, download_link_text):
    """
    Generates a link to download the given object_to_download.
    """
    if isinstance(object_to_download, pd.DataFrame):
        object_to_download = object_to_download.to_csv(index=False)

    # some strings <-> bytes conversions necessary here
    b64 = base64.b64encode(object_to_download.encode()).decode()
    href = f'<a href="data:file/txt;base64,{b64}" download="{download_filename}" class="download-button">{download_link_text}</a>'
    return href

def clear_cache():
    """Clear all cached data or just expired items."""
    cache_files = list(CACHE_DIR.glob("*.pkl"))
    now = datetime.now()
    expired = 0
    total = len(cache_files)
    
    for cache_file in cache_files:
        file_age = now - datetime.fromtimestamp(cache_file.stat().st_mtime)
        if file_age.days >= CACHE_EXPIRY_DAYS:
            cache_file.unlink()
            expired += 1
            
    return total, expired

def get_scraper(platform):
    """Get appropriate scraper based on platform selection with cloud environment adaptations"""
    try:
        # Set cloud environment flag
        is_cloud = os.environ.get('IS_STREAMLIT_CLOUD', False)
        
        if platform == "myntra":
            from myntrascrapper import MyntraScraper
            scraper = MyntraScraper()
            
            # Always update Myntra headers for better reliability
            scraper.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.myntra.com/',
                'sec-ch-ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"'
            })
            
            # Ensure we have cookies by visiting the homepage
            try:
                scraper.session.get("https://www.myntra.com/")
            except:
                pass
                
            return scraper
            
        # Rest of the function remains the same
        elif platform == "flipkart":
            # Your existing code for Flipkart
            from flipkartscrapper import FlipkartScraper
            scraper = FlipkartScraper()
            # Cloud-specific settings for Flipkart
            if is_cloud:
                scraper.session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
                    'Accept-Language': 'en-US,en;q=0.9'
                })
            return scraper
            
        # Unchanged code for other platforms
        elif platform == "amazon":
            from amazonscrapper import AmazonScraper
            # For Amazon, we need to be more careful in cloud environments
            if is_cloud:
                # Use safer settings for cloud deployment
                return AmazonScraper(region="in", use_proxies=False)
            else:
                return AmazonScraper(region="in")
                
        elif platform == "tatacliq":
            from tatacliqscrapper import TataCliqScraper
            return TataCliqScraper()
            
        elif platform == "ajio":
            from ajioscrapper import AjioScraper
            return AjioScraper()
            
        else:
            st.error(f"Scraper for {platform} is not yet implemented")
            return None
            
    except Exception as e:
        st.error(f"Error initializing scraper: {str(e)}")
        return None


# Add this after your imports
def safe_scrape(scraper, product_id, platform):
    """Safe scraping wrapper with better error handling"""
    try:
        # First, try with standard approach
        data = scraper.get_product_details(str(product_id))
        
        if not data:
            # If no data returned, try with different user agent
            if hasattr(scraper, 'session'):
                # Save original headers
                original_headers = scraper.session.headers.copy()
                
                # Try with a different user agent
                scraper.session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    'Accept': 'application/json, text/javascript, */*; q=0.01',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Referer': 'https://www.myntra.com/',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Connection': 'keep-alive',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache'
                })
                
                # Add cookies if missing (which might help with Myntra)
                if platform == "myntra" and not scraper.session.cookies:
                    # Visit homepage first to get cookies
                    try:
                        scraper.session.get('https://www.myntra.com/')
                    except:
                        pass
                
                # Retry with new headers
                data = scraper.get_product_details(str(product_id))
                
                # Restore original headers
                scraper.session.headers = original_headers
        
        if data:
            # For Myntra specifically, check if the data is valid JSON
            if platform == "myntra" and isinstance(data, str):
                # Try to parse the string as JSON
                try:
                    import json
                    data = json.loads(data)
                except:
                    # If parsing fails, it's not valid JSON
                    return None
            
            # Extract product information
            product_info = scraper.extract_product_info(data)
            
            # If extraction failed but we have data, try fallback extraction
            if not product_info and platform == "myntra":
                # Try to extract with a simpler approach for Myntra
                product_info = fallback_myntra_extract(data)
            
            return product_info
        
        return None
    except Exception as e:
        st.warning(f"Error while scraping {platform} product {product_id}: {str(e)}")
        
        # If it's a JSON decode error for Myntra, try a different method
        if platform == "myntra" and "Expecting value" in str(e):
            try:
                # Try using requests directly with a fresh session
                import requests
                import json
                import random
                import time
                
                session = requests.Session()
                session.headers = {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                    "Accept": "application/json",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://www.myntra.com/",
                    "sec-ch-ua": '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"macOS"'
                }
                
                # First, visit homepage to get cookies
                session.get("https://www.myntra.com/")
                
                # Add delay to mimic human behavior
                time.sleep(1 + random.random())
                
                # Then try to get product
                api_url = f"https://www.myntra.com/gateway/v2/product/{product_id}"
                response = session.get(api_url)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        # Try to use the regular extract function
                        product_info = scraper.extract_product_info(data)
                        if not product_info:
                            product_info = fallback_myntra_extract(data)
                        return product_info
                    except:
                        pass
            except Exception as inner_e:
                st.warning(f"Alternative scraping method also failed: {str(inner_e)}")
        
        return None

def fallback_myntra_extract(data):
    """Fallback extraction for Myntra when normal extraction fails"""
    try:
        # Check if data has the expected format
        if not data:
            return None
            
        # Try to access with standard structure first
        if 'style' in data:
            style = data['style']
            basic_info = {
                "product_id": style.get('id'),
                "name": style.get('name'),
                "brand": style.get('brand', {}).get('name', 'Unknown'),
                "is_fallback": True  # Mark as fallback extraction
            }
            
            # Try to extract price info
            if 'price' in style:
                basic_info["mrp"] = style.get('price', {}).get('mrp')
                basic_info["price"] = style.get('price', {}).get('discounted')
                basic_info["discount"] = style.get('price', {}).get('discount')
            
            # Try to extract images
            images = []
            if 'media' in style:
                media = style.get('media', {})
                if 'albums' in media:
                    for album in media.get('albums', []):
                        for image in album.get('images', []):
                            if 'secureSrc' in image:
                                img_url = image['secureSrc']
                                # Replace placeholders with actual values if needed
                                img_url = img_url.replace('($height)', '1080').replace('($qualityPercentage)', '90').replace('($width)', '720')
                                images.append(img_url)
            
            basic_info["images"] = images
            return basic_info
        
        # Alternative format check
        if 'data' in data and 'style' in data['data']:
            style = data['data']['style']
            return {
                "product_id": style.get('id'),
                "name": style.get('name', 'Unknown Product'),
                "brand": style.get('brand', {}).get('name', 'Unknown'),
                "is_fallback": True
            }
            
        # Last resort: just return whatever product ID we can find
        if 'data' in data and isinstance(data['data'], dict):
            for key, value in data['data'].items():
                if isinstance(value, dict) and 'id' in value:
                    return {
                        "product_id": value.get('id'),
                        "name": value.get('name', 'Unknown Product'),
                        "is_fallback": True,
                        "partial_data": True
                    }
                    
        return None
    except Exception as e:
        print(f"Error in fallback extraction: {e}")
        return None

# Other existing functions (unchanged)
def create_price_monitoring():
    st.subheader("⏰ Price Monitoring")
    
    # Setup monitoring preferences
    with st.expander("Set Price Alerts"):
        alert_method = st.selectbox("Alert Method", ["Email", "Browser Notification", "Webhook"])
        price_threshold = st.number_input("Alert when price drops below:", min_value=0)
        percent_drop = st.slider("Or when price drops by percentage:", 0, 100, 10)
        
        # Frequency settings
        check_frequency = st.select_slider(
            "Check frequency", 
            options=["Hourly", "Daily", "Weekly"]
        )
        
        # Setup notification details based on method
        if alert_method == "Email":
            email = st.text_input("Email address for alerts")
        elif alert_method == "Webhook":
            webhook_url = st.text_input("Webhook URL")
            
        enable_button = st.button("Enable Price Monitoring")

def add_scheduled_scraping():
    st.subheader("⏲️ Scheduled Scraping")
    
    # Schedule settings
    frequency = st.select_slider(
        "Scraping Frequency", 
        options=["Once", "Daily", "Weekly", "Monthly"]
    )
    
    if frequency != "Once":
        # Use the time class correctly from datetime module
        from datetime import time as dt_time
        time_of_day = st.time_input("Time of day to run", value=dt_time(0, 0))
        
        if frequency == "Weekly":
            day_of_week = st.selectbox("Day of week", 
                                      ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
        elif frequency == "Monthly":
            day_of_month = st.slider("Day of month", 1, 28, 1)
    
    # Output options
    output_options = st.multiselect("Output Options", 
                                   ["Save to CSV", "Save to JSON", "Email Results", "Push to Database"])
    
    # Email notification
    notify = st.checkbox("Send notification when complete")
    if notify:
        email = st.text_input("Email for notifications")
    
    schedule_button = st.button("Schedule Task")

def add_advanced_export_options(results_df):
    st.subheader("🔄 Advanced Export & Integrations")
    
    export_format = st.selectbox(
        "Export Format", 
        ["CSV", "JSON", "Excel", "SQL", "Google Sheets", "Airtable"]
    )
    
    if export_format == "Excel":
        # Create Excel file with formatted data
        import io
        from xlsxwriter import Workbook
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            results_df.to_excel(writer, sheet_name='Products')
            workbook = writer.book
            worksheet = writer.sheets['Products']
            
            # Add formatting
            format_header = workbook.add_format({'bold': True, 'bg_color': '#AED6F1'})
            for col_num, value in enumerate(results_df.columns.values):
                worksheet.write(0, col_num + 1, value, format_header)
        
        buffer.seek(0)
        st.download_button(
            label="📥 Download Excel File",
            data=buffer,
            file_name="products_data.xlsx",
            mime="application/vnd.ms-excel"
        )
    
    elif export_format == "Google Sheets":
        st.write("Connect to Google Sheets:")
        sheets_url = st.text_input("Google Sheets URL (must be publicly editable)")
        api_key = st.text_input("Google API Key", type="password")

def create_enhanced_csv_export(results_df):
    """
    Creates an enhanced CSV export with all product details including images, brand, price, etc.
    
    Args:
        results_df (pd.DataFrame): DataFrame containing the scraped product information
        
    Returns:
        str: CSV string with all product information
    """
    # Make a copy of the DataFrame to avoid modifying the original
    export_df = results_df.copy()
    
    # Handle list columns by joining them with pipe separators
    for col in export_df.columns:
        if export_df[col].dtype == 'object':
            # Convert lists to pipe-separated strings
            export_df[col] = export_df[col].apply(
                lambda x: "|".join(str(item) for item in x) if isinstance(x, list) else x
            )
    
    # Add timestamp
    export_df['export_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create CSV string
    csv_str = export_df.to_csv(index=False)
    return csv_str

def main():
    # Set page config
    st.set_page_config(
        page_title="E-commerce Product Scraper",
        page_icon="🛒",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Load user state
    user_state = get_user_state()
    
    # Initialize session state for persistent UI state
    if 'selected_platform' not in st.session_state:
        st.session_state.selected_platform = user_state.get('selected_platform', 'myntra')
    
    if 'use_cache' not in st.session_state:
        st.session_state.use_cache = user_state.get('use_cache', True)
    
    if 'delay' not in st.session_state:
        st.session_state.delay = user_state.get('delay', 2)
    
    if 'max_retries' not in st.session_state:
        st.session_state.max_retries = user_state.get('max_retries', 2)
    
    # Custom CSS for better UI (unchanged)
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 1rem;
        padding-bottom: 1rem;
        border-bottom: 2px solid #f0f2f6;
    }
    .platform-selector {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
    }
    .info-box {
        background-color: #e3f2fd;
        padding: 1rem;
        border-radius: 5px;
        margin-bottom: 1rem;
    }
    .platform-logo {
        height: 30px;
        margin-right: 10px;
        vertical-align: middle;
    }
    .stProgress > div > div > div > div {
        background-color: #4CAF50;
    }
    .download-button {
        display: inline-block;
        padding: 0.5rem 1rem;
        background-color: #4CAF50;
        color: white;
        text-decoration: none;
        border-radius: 4px;
        margin: 0.5rem 0;
        text-align: center;
    }
    .download-button:hover {
        background-color: #45a049;
    }
    .results-container {
        margin-top: 2rem;
        padding: 1rem;
        border: 1px solid #ddd;
        border-radius: 10px;
    }
    .cache-stats {
        background-color: #f0f7ff;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .history-item {
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 8px;
        border-left: 4px solid #4CAF50;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown("<h1 class='main-header'>🛒 Multi-Platform E-commerce Product Scraper</h1>", unsafe_allow_html=True)
    
    # Sidebar for platform selection
    with st.sidebar:
        st.header("Platform Selection")
        
        # Use session state for platform selection
        selected_platform = st.selectbox(
            "Choose an e-commerce platform",
            options=list(PLATFORMS.keys()),
            format_func=lambda x: PLATFORMS[x]["name"],
            key="selected_platform"
        )
        
        # Display platform info
        st.markdown(f"""
        <div style="text-align: center; margin-top: 20px; padding: 15px; 
                 background-color: {PLATFORMS[selected_platform]['color']}20; 
                 border-radius: 10px;">
            <img src="{PLATFORMS[selected_platform]['logo']}" class="platform-logo" style="height: 40px;">
            <h3>{PLATFORMS[selected_platform]['name']} Scraper</h3>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Add user account section
        st.header("🔑 User Account")
        st.write(f"User ID: {get_user_id()[:8]}...")
        
        with st.expander("Recent Search History"):
            history = get_search_history(limit=5)
            if history:
                for item in history:
                    platform_name = PLATFORMS[item["platform"]]["name"] if item["platform"] in PLATFORMS else item["platform"]
                    st.markdown(f"""
                    <div class="history-item">
                        <strong>{platform_name}</strong><br>
                        Query: {item["search_query"]}<br>
                        Results: {item["num_results"]}<br>
                        <small>{item["timestamp"]}</small>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.write("No search history yet.")
        
        st.markdown("---")
        
        st.markdown("""
        ### Instructions
        1. Select the e-commerce platform
        2. Upload a CSV file with product IDs
        3. Click "Start Scraping" to begin
        
        ### Supported ID Columns
        - `product_id`
        - `style_id`
        - `id`
        """)
        
        # Add cache management options
        st.markdown("---")
        st.header("Cache Management")
        
        # Count total and expired cache files
        cache_files = list(CACHE_DIR.glob("*.pkl"))
        cache_size_mb = sum(f.stat().st_size for f in cache_files) / (1024 * 1024)
        
        st.markdown(f"""
        <div class="cache-stats">
            <p><strong>Cache Status:</strong></p>
            <p>📁 Cached items: {len(cache_files)}</p>
            <p>💾 Cache size: {cache_size_mb:.2f} MB</p>
        </div>
        """, unsafe_allow_html=True)
        
        cache_col1, cache_col2 = st.columns(2)
        with cache_col1:
            if st.button("Clear Expired Cache"):
                total, expired = clear_cache()
                st.success(f"Cleared {expired} expired items out of {total} total.")
                st.rerun()
        
        with cache_col2:
            if st.button("Clear All Cache"):
                for cache_file in cache_files:
                    cache_file.unlink()
                st.success(f"Cleared all {len(cache_files)} cached items.")
                st.rerun()
        
        # Use session state for cache checkbox
        use_cache = st.checkbox("Use cached results (faster)", value=st.session_state.use_cache, key="use_cache")
        
        with st.expander("About This Tool"):
            st.write("""
            This tool helps you scrape product information from various e-commerce platforms.
            The data is extracted ethically with reasonable delays between requests to avoid
            overwhelming the servers. All data is for personal use only.
            
            Caching helps to speed up repeated lookups and reduce server load.
            
            Developed with ❤️ using Python and Streamlit.
            """)
    
    # Main content area
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader(f"Upload Product IDs for {PLATFORMS[selected_platform]['name']}")
        st.markdown(f"""
        <div class="info-box">
        <strong>Note:</strong> This scraper extracts product details from {PLATFORMS[selected_platform]['name']}'s website. 
        Upload a CSV file with a column named 'product_id' or 'style_id' containing product IDs.
        </div>
        """, unsafe_allow_html=True)
        
        # File upload
        uploaded_file = st.file_uploader(f"Upload CSV with {PLATFORMS[selected_platform]['name']} product IDs", type="csv")
    
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(f"""
        <div style="text-align: center; padding: 10px; background-color: {PLATFORMS[selected_platform]['color']}10; border-radius: 5px;">
            <img src="{PLATFORMS[selected_platform]['logo']}" style="height: 60px; margin-bottom: 10px;">
            <p>Currently selected</p>
        </div>
        """, unsafe_allow_html=True)
    
    if uploaded_file is not None:
        # Read the CSV file
        try:
            df = pd.read_csv(uploaded_file)
            
            # Check if the required column exists
            id_column = None
            for col in ['product_id', 'style_id', 'id']:
                if col in df.columns:
                    id_column = col
                    break
            
            if id_column is None:
                st.error("CSV must contain a column named 'product_id', 'style_id', or 'id'")
                return
            
            # Display the uploaded data
            st.subheader("Uploaded Data Preview")
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.dataframe(df.head())
            with col2:
                st.write(f"**Total products:** {len(df)}")
                st.write(f"**ID column:** {id_column}")
                
                # Configuration options using session state
                st.subheader("Scraping Options")
                delay = st.slider("Delay between requests (seconds)", 1, 10, st.session_state.delay, key="delay")
                max_retries = st.number_input("Max retries for failed requests", 0, 5, st.session_state.max_retries, key="max_retries")
            
            # Scrape button with platform color
            scrape_button = st.button(
                f"Start Scraping {PLATFORMS[selected_platform]['name']} Products", 
                key="scrape_button",
                use_container_width=True
            )
            
            if scrape_button:
                # Get appropriate scraper
                scraper = get_scraper(selected_platform)
                
                if not scraper:
                    st.error(f"Scraping for {PLATFORMS[selected_platform]['name']} is not yet implemented")
                    return
                
                # Initialize progress tracking
                progress_bar = st.progress(0)
                status_col1, status_col2 = st.columns([3, 1])
                status_text = status_col1.empty()
                timer_text = status_col2.empty()
                
                # Initialize results container
                all_results = []
                failed_ids = []
                cache_hits = 0
                
                # Process each product ID
                total_products = len(df)
                start_time = time.time()
                
                for i, product_id in enumerate(df[id_column]):
                    # Update progress
                    progress = (i) / total_products
                    progress_bar.progress(progress)
                    
                    # Update status
                    elapsed = time.time() - start_time
                    estimated_total = (elapsed / (i + 1)) * total_products if i > 0 else 0
                    remaining = max(0, estimated_total - elapsed)
                    
                    status_text.text(f"Scraping product {i+1} of {total_products}: ID {product_id}")
                    timer_text.text(f"⏱️ {int(elapsed//60)}m {int(elapsed%60)}s elapsed | ~{int(remaining//60)}m {int(remaining%60)}s remaining")
                    
                    try:
                        product_info = None
                        
                        # Check cache if enabled
                        if use_cache:
                            product_info = get_from_cache(selected_platform, str(product_id))
                            if product_info:
                                cache_hits += 1
                                status_text.text(f"Found in cache: product {i+1} of {total_products}: ID {product_id}")
                        
                        # If not in cache or cache disabled, scrape from website
                        if not product_info:
                            # Use safe scraping with fallbacks
                            product_info = safe_scrape(scraper, str(product_id), selected_platform)
                            
                            # Save to cache if successful
                            if product_info:
                                # Add to results
                                all_results.append(product_info)
                                save_to_cache(selected_platform, str(product_id), product_info)
                            else:
                                # Add diagnostic info to the failure record
                                error_info = {
                                    "product_id": product_id, 
                                    "reason": "Failed to extract information",
                                    "platform": selected_platform
                                }
                                failed_ids.append(error_info)
                        else:
                            # Add cached data to results
                            all_results.append(product_info)
                    
                    except Exception as e:
                        failed_ids.append({"product_id": product_id, "reason": str(e)})
                    
                    # Add random delay between requests (only if not from cache)
                    if not (use_cache and get_from_cache(selected_platform, str(product_id))):
                        time.sleep(delay + random.uniform(0, 1))
                
                # Update progress to completion
                progress_bar.progress(1.0)
                status_text.text("✅ Scraping completed!")
                
                # Calculate total time
                total_time = time.time() - start_time
                timer_text.text(f"⏱️ Total time: {int(total_time//60)}m {int(total_time%60)}s")
                
                # Save to search history
                search_query = f"{len(df)} products from {id_column}"
                add_to_search_history(selected_platform, search_query, len(all_results))
                
                # Display results
                st.markdown("<div class='results-container'>", unsafe_allow_html=True)
                st.subheader("📊 Scraping Results")
                
                success_rate = len(all_results) / total_products * 100
                
                metrics_col1, metrics_col2, metrics_col3, metrics_col4 = st.columns(4)
                metrics_col1.metric("Successfully Scraped", f"{len(all_results)} products", f"{success_rate:.1f}%")
                metrics_col2.metric("Failed", f"{len(failed_ids)} products", f"{100-success_rate:.1f}%")
                metrics_col3.metric("Cache Hits", f"{cache_hits}", f"{cache_hits/total_products*100:.1f}%")
                metrics_col4.metric("Total Time", f"{int(total_time//60)}m {int(total_time%60)}s")
                
                if failed_ids:
                    with st.expander(f"View {len(failed_ids)} Failed Products"):
                        st.dataframe(pd.DataFrame(failed_ids))
                
                # Prepare download links
                if all_results:
                    st.subheader("📥 Download Results")
                    
                    # Create JSON string
                    json_str = json.dumps(all_results, indent=2)
                    
                    # Create CSV from the results
                    results_df = pd.DataFrame(all_results)
                    
                    # Display download links
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown(download_link(json_str, f"{selected_platform}_products.json", "📥 Download JSON"), unsafe_allow_html=True)
                    
                    with col2:
                        # Basic CSV download
                        csv = results_df.to_csv(index=False)
                        st.markdown(download_link(csv, f"{selected_platform}_products.csv", "📥 Download CSV"), unsafe_allow_html=True)
                    
                    with col3:
                        # Enhanced CSV with all details
                        enhanced_csv = create_enhanced_csv_export(results_df)
                        st.markdown(download_link(enhanced_csv, f"{selected_platform}_products_detailed.csv", "📥 Download Detailed CSV"), 
                                    unsafe_allow_html=True)
                    
                    # Show sample of data
                    with st.expander("Preview Sample of Scraped Data"):
                        st.json(all_results[0])
                        
                    # Data overview
                    st.subheader("Data Overview")
                    
                    try:
                        # Display basic stats
                        if 'mrp' in results_df.columns:
                            price_stats = results_df['mrp'].describe()
                            st.write("Price Statistics:")
                            st.dataframe(price_stats)
                        
                        # Most common brands
                        if 'brand' in results_df.columns:
                            st.write("Most Common Brands:")
                            st.dataframe(results_df['brand'].value_counts().head(10).reset_index().rename(columns={'index': 'Brand', 'brand': 'Count'}))
                        
                        # Most common categories
                        if 'category' in results_df.columns:
                            st.write("Categories Distribution:")
                            st.dataframe(results_df['category'].value_counts().reset_index().rename(columns={'index': 'Category', 'category': 'Count'}))
                    except Exception as e:
                        st.warning(f"Could not generate statistics: {str(e)}")
                
                st.markdown("</div>", unsafe_allow_html=True)
                
                # Call advanced export options
                if all_results:
                    add_advanced_export_options(results_df)
                    enhanced_csv = create_enhanced_csv_export(results_df)
                    st.markdown(download_link(enhanced_csv, f"{selected_platform}_enhanced_products.csv", "📥 Download Enhanced CSV"), unsafe_allow_html=True)
                    
                    # Add export format options
                    export_format_container = st.expander("Export Options")
                    with export_format_container:
                        st.write("Configure your export format:")
                        
                        # Select which columns to include
                        if not results_df.empty:
                            available_columns = results_df.columns.tolist()
                            selected_columns = st.multiselect(
                                "Select columns to include (leave empty for all columns):",
                                available_columns,
                                default=[]
                            )
                            
                            # Image options
                            include_images = st.checkbox("Include image URLs", value=True)
                            max_images = st.slider("Maximum number of images per product", 1, 10, 3) if include_images else 1
                            
                            # Create custom export button
                            if st.button("Generate Custom Export"):
                                # Create custom DataFrame
                                custom_df = results_df.copy()
                                
                                # Filter columns if specified
                                if selected_columns:
                                    custom_df = custom_df[selected_columns]
                                    
                                # Handle image columns
                                if 'images' in custom_df.columns and include_images:
                                    # Keep only specified number of images
                                    custom_df['images'] = custom_df['images'].apply(
                                        lambda x: x[:max_images] if isinstance(x, list) else x
                                    )
                                    
                                    # Add individual image columns
                                    for i in range(max_images):
                                        custom_df[f'image_url_{i+1}'] = custom_df['images'].apply(
                                            lambda x: x[i] if isinstance(x, list) and len(x) > i else None
                                        )
                                
                                # Create CSV string
                                custom_csv = custom_df.to_csv(index=False)
                                
                                # Display download link
                                st.markdown(download_link(custom_csv, f"{selected_platform}_products_custom.csv", 
                                                        "📥 Download Custom CSV"), unsafe_allow_html=True)
        
        except Exception as e:
            st.error(f"Error processing the file: {str(e)}")

    # Add additional features
    create_price_monitoring()
    add_scheduled_scraping()
    
    # Save user state before exiting
    current_state = {
        'selected_platform': selected_platform,
        'use_cache': use_cache,
        'delay': delay if 'delay' in locals() else st.session_state.delay,
        'max_retries': max_retries if 'max_retries' in locals() else st.session_state.max_retries,
        'last_visit': datetime.now().isoformat()
    }
    save_user_state(current_state)
    
    # Periodically clean up expired user states (once a day)
    if random.random() < 0.1:  # 10% chance to run cleanup on each page load
        clear_expired_user_states()

if __name__ == "__main__":
    main()