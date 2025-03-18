# flipkartscrapper.py
import requests
import json
import time
import random
import os
import csv
from datetime import datetime
from bs4 import BeautifulSoup

class FlipkartScraper:
    """A scraper for extracting product details from Flipkart's API."""
    
    def __init__(self):
        self.base_url = "https://www.flipkart.com/"
        self.session = requests.Session()
        self.session.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.flipkart.com/",
            "Connection": "keep-alive"
        }
        
        # Get initial cookies
        self.session.get("https://www.flipkart.com/")
    
    def get_product_details(self, product_id):
        """Fetch product details from Flipkart API for a given product ID.
        
        Args:
            product_id (str): The Flipkart product ID
            
        Returns:
            dict: Product details data
        """
        # Flipkart product URL format
        url = f"{self.base_url}/product/{product_id}"
        
        try:
            # Add random delay
            time.sleep(2 + random.uniform(0, 2))
            response = self.session.get(url)
            response.raise_for_status()
            
            # Flipkart likely requires HTML parsing
            # Use the response.text to parse HTML
            return {"html": response.text, "url": response.url}
        except requests.exceptions.RequestException as e:
            print(f"Error fetching product details: {e}")
            return None
    
    def extract_product_info(self, data):
        """Extract relevant product information from the API response.
        
        Args:
            data (dict): The API response data
            
        Returns:
            dict: Extracted product information
        """
        if not data or "html" not in data:
            return None
        
        soup = BeautifulSoup(data["html"], "html.parser")
        
        # Extract product information from HTML
        # These selectors need to be adjusted based on Flipkart's actual HTML structure
        try:
            product_info = {
                "product_id": data["url"].split("/")[-1].split("?")[0],
                "name": soup.select_one("span.B_NuCI").text.strip() if soup.select_one("span.B_NuCI") else None,
                "brand": soup.select_one("span.G6XhRU").text.strip() if soup.select_one("span.G6XhRU") else None,
                "mrp": self._extract_price(soup.select_one("div._3I9_wc")),
                "selling_price": self._extract_price(soup.select_one("div._30jeq3")),
                "discount_percent": self._extract_discount(soup.select_one("div._3Ay6Sb")),
                "rating": float(soup.select_one("div._3LWZlK").text.strip()) if soup.select_one("div._3LWZlK") else None,
                "rating_count": self._extract_rating_count(soup.select_one("span._2_R_DZ")),
                "highlights": [li.text.strip() for li in soup.select("div._2cM9lP li")],
                "specifications": self._extract_specifications(soup),
                "images": [img.get("src").replace("/128/", "/832/") for img in soup.select("div.CXW8mj img")]
            }
            
            return product_info
        except Exception as e:
            print(f"Error extracting product info: {e}")
            return None
    
    def _extract_price(self, element):
        """Helper to extract price from an element"""
        if not element:
            return None
        price_text = element.text.strip()
        # Remove currency symbol and commas
        price_text = price_text.replace("₹", "").replace(",", "")
        try:
            return int(float(price_text))
        except ValueError:
            return None
    
    def _extract_discount(self, element):
        """Helper to extract discount percentage"""
        if not element:
            return None
        discount_text = element.text.strip()
        # Extract percentage value
        import re
        match = re.search(r'(\d+)%', discount_text)
        if match:
            return int(match.group(1))
        return None
    
    def _extract_rating_count(self, element):
        """Helper to extract rating count"""
        if not element:
            return None
        text = element.text.strip()
        # Extract rating count
        import re
        match = re.search(r'(\d+(?:,\d+)*)', text)
        if match:
            return int(match.group(1).replace(",", ""))
        return None
    
    def _extract_specifications(self, soup):
        """Helper to extract specifications table"""
        specs = {}
        tables = soup.select("div._14cfVK")
        
        for table in tables:
            category = table.select_one("div._2lzn0o").text.strip() if table.select_one("div._2lzn0o") else "General"
            spec_dict = {}
            
            rows = table.select("tr._1s_Smc")
            for row in rows:
                cols = row.select("td")
                if len(cols) >= 2:
                    key = cols[0].text.strip()
                    value = cols[1].text.strip()
                    spec_dict[key] = value
            
            specs[category] = spec_dict
        
        return specs
    
    # Implement save_to_json and save_to_csv methods similar to MyntraScraper
    def save_to_json(self, data, output_file=None):
        """Save the extracted product information to a JSON file."""
        # Implementation similar to MyntraScraper
        pass
        
    def save_to_csv(self, data, output_file=None):
        """Save the extracted product information to a CSV file."""
        # Implementation similar to MyntraScraper
        pass