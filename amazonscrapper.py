# amazonscrapper.py
import requests
import json
import time
import random
import os
import csv
from datetime import datetime
from bs4 import BeautifulSoup
import re
from requests.exceptions import RequestException, ProxyError
from fake_useragent import UserAgent  

class AmazonScraper:
    """A scraper for extracting product details from Amazon's website with advanced anti-ban features."""
    
    # List of common user agents to rotate (fallback if fake_useragent fails)
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
    ]
    
    # Amazon regional domains mapping
    AMAZON_DOMAINS = {
        "in": "amazon.in"
    }
    
    def __init__(self, use_proxies=False, proxy_list=None, region="us", captcha_service=None):
        """
        Initialize the Amazon scraper with advanced anti-ban features.
        
        Args:
            use_proxies (bool): Whether to use proxy rotation
            proxy_list (list): List of proxy URLs (if None, will attempt to load from proxies.txt)
            region (str): Amazon regional domain to use (us, uk, ca, etc.)
            captcha_service (object): Optional CAPTCHA solving service client
        """
        # Setup proxy rotation
        self.use_proxies = use_proxies
        self.proxies = self._load_proxies(proxy_list)
        self.current_proxy_index = 0
        self.failed_proxies = set()
        
        # Setup user agent rotation
        try:
            self.ua = UserAgent()
            self.use_fake_ua = True
        except:
            print("Warning: fake_useragent package failed to initialize. Using fallback user agents.")
            self.use_fake_ua = False
        
        # Setup regional domain
        self.region = region
        self.base_url = f"https://www.{self.AMAZON_DOMAINS.get(region, 'amazon.com')}"
        
        # Setup CAPTCHA solving
        self.captcha_service = captcha_service
        
        # Setup session with initial headers
        self.session = requests.Session()
        self._rotate_user_agent()
        
        # Initialize retry counts and backoff settings
        self.max_retries = 5
        self.base_backoff = 2  # Base delay for exponential backoff (seconds)
        
        # Attempt to visit the homepage to get cookies
        try:
            self._make_request(self.base_url)
            print(f"Successfully initialized Amazon scraper for {self.base_url}")
        except Exception as e:
            print(f"Warning: Error initializing Amazon scraper: {e}")
    
    def _load_proxies(self, proxy_list=None):
        """Load proxy list from provided list or file."""
        if not self.use_proxies:
            return []
            
        if proxy_list:
            return proxy_list
            
        # Try to load from proxies.txt
        try:
            with open('proxies.txt', 'r') as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print("Warning: proxies.txt not found. Proxy rotation disabled.")
            self.use_proxies = False
            return []
    
    def _rotate_user_agent(self):
        """Rotate the User-Agent to appear as different browsers."""
        if self.use_fake_ua:
            try:
                ua = self.ua.random
            except:
                ua = random.choice(self.USER_AGENTS)
        else:
            ua = random.choice(self.USER_AGENTS)
            
        self.session.headers.update({
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0"
        })
    
    def _get_next_proxy(self):
        """Get the next proxy from the rotation list."""
        if not self.use_proxies or not self.proxies:
            return None
            
        # Skip failed proxies
        for _ in range(len(self.proxies)):
            proxy = self.proxies[self.current_proxy_index]
            self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
            
            if proxy not in self.failed_proxies:
                return {"http": proxy, "https": proxy}
                
        # If all proxies have failed, retry with the first one
        if self.proxies:
            self.failed_proxies.clear()  # Reset failed list
            return {"http": self.proxies[0], "https": self.proxies[0]}
        return None
    
    def _make_request(self, url, params=None, retries=0):
        """
        Make a request with exponential backoff retry logic and proxy rotation.
        
        Args:
            url (str): URL to request
            params (dict): Optional query parameters
            retries (int): Current retry attempt number
            
        Returns:
            Response object or None on failure
        """
        if retries >= self.max_retries:
            print(f"Maximum retries reached for URL: {url}")
            return None
            
        # Exponential backoff delay
        if retries > 0:
            delay = self.base_backoff ** retries + random.uniform(0, 1)
            print(f"Retry attempt {retries}/{self.max_retries}, waiting {delay:.2f} seconds...")
            time.sleep(delay)
        
        # Rotate user agent
        self._rotate_user_agent()
        
        # Get proxy if using proxy rotation
        proxies = self._get_next_proxy() if self.use_proxies else None
        
        try:
            # Add jitter delay to mimic human behavior
            time.sleep(1 + random.uniform(0, 2))
            
            response = self.session.get(url, params=params, proxies=proxies, timeout=20)
            
            # Check for CAPTCHA
            if "captcha" in response.text.lower():
                if self.captcha_service:
                    return self._handle_captcha(response, url, params)
                else:
                    print(f"CAPTCHA detected but no solving service configured.")
                    # Mark this proxy as failed if using proxies
                    if proxies and proxies.get('http') not in self.failed_proxies:
                        self.failed_proxies.add(proxies.get('http'))
                    
                    # Retry with a different proxy/user-agent
                    return self._make_request(url, params, retries + 1)
            
            # Check for other failures
            if response.status_code != 200:
                print(f"Request failed with status code: {response.status_code}")
                return self._make_request(url, params, retries + 1)
                
            return response
            
        except ProxyError:
            # Mark this proxy as failed
            if proxies and proxies.get('http') not in self.failed_proxies:
                self.failed_proxies.add(proxies.get('http'))
            print(f"Proxy error. Rotating proxy and retrying...")
            return self._make_request(url, params, retries + 1)
            
        except RequestException as e:
            print(f"Request exception: {e}")
            return self._make_request(url, params, retries + 1)
            
        except Exception as e:
            print(f"Unexpected error: {e}")
            return self._make_request(url, params, retries + 1)
    
    def _handle_captcha(self, response, url, params):
        """
        Handle CAPTCHA challenge using the provided CAPTCHA solving service.
        This is a placeholder for implementation with your specific CAPTCHA service.
        
        Args:
            response (Response): The response containing CAPTCHA
            url (str): Original request URL
            params (dict): Original request parameters
            
        Returns:
            Response object from the retry after CAPTCHA solution
        """
        if not self.captcha_service:
            return None
            
        try:
            # Extract CAPTCHA image URL and form details (implementation depends on service)
            soup = BeautifulSoup(response.text, 'html.parser')
            captcha_img = soup.select_one('img[src*="captcha"]')
            
            if not captcha_img:
                print("Could not find CAPTCHA image")
                return None
                
            captcha_url = captcha_img['src']
            form_action = soup.select_one('form')['action']
            
            # Get CAPTCHA solution from service (implementation depends on service)
            captcha_solution = self.captcha_service.solve(captcha_url)
            
            if not captcha_solution:
                print("Failed to solve CAPTCHA")
                return None
                
            # Submit CAPTCHA solution (implementation depends on Amazon's form)
            # This is a placeholder - you'll need to customize for your CAPTCHA service
            form_data = {
                'captchaCharacters': captcha_solution
                # Other form fields needed
            }
            
            # Submit solution
            captcha_response = self.session.post(form_action, data=form_data)
            
            # Retry original request
            return self.session.get(url, params=params)
            
        except Exception as e:
            print(f"Error solving CAPTCHA: {e}")
            return None
    
    def get_product_details(self, product_id, region=None):
        """
        Fetch product details from Amazon for a given product ID.
        
        Args:
            product_id (str): The Amazon product ID (ASIN)
            region (str): Optional region override (us, uk, ca, etc.)
            
        Returns:
            dict: Raw HTML and URL for further processing
        """
        # Allow per-request region override
        if region and region != self.region:
            base_url = f"https://www.{self.AMAZON_DOMAINS.get(region, 'amazon.com')}"
        else:
            base_url = self.base_url
        
        # Amazon product URL format using the ASIN (product_id)
        url = f"{base_url}/dp/{product_id}"
        
        # Add random query parameter to avoid caching
        params = {'_': str(int(time.time()))}
        
        response = self._make_request(url, params)
        if not response:
            print(f"Failed to fetch product {product_id}")
            return None
        
        return {
            "html": response.text,
            "url": response.url
        }
    
    def extract_product_info(self, data):
        """
        Extract relevant product information from the Amazon page HTML.
        
        Args:
            data (dict): Raw HTML and URL
            
        Returns:
            dict: Extracted product information
        """
        if not data or "html" not in data:
            return None
        
        soup = BeautifulSoup(data["html"], "html.parser")
        
        # Initialize product_info dictionary
        product_info = {
            "product_id": self._extract_product_id(data["url"]),
            "source": "Amazon",
            "url": data["url"],
            "region": self._extract_region_from_url(data["url"])
        }
        
        # Extract product name
        product_name_elem = soup.select_one("#productTitle")
        if product_name_elem:
            product_info["name"] = product_name_elem.text.strip()
        
        # Extract brand
        brand_elem = soup.select_one("#bylineInfo") or soup.select_one(".a-link-normal.contributorNameID")
        if brand_elem:
            brand_text = brand_elem.text.strip()
            # Clean up brand text (e.g., "Visit the Brand Store" -> "Brand")
            brand = re.sub(r'^(Visit the|Brand:|by)\s+', '', brand_text)
            brand = re.sub(r'\s+Store$', '', brand)
            product_info["brand"] = brand
        
        # Extract price
        price_elem = soup.select_one(".a-price .a-offscreen")
        if price_elem:
            price_text = price_elem.text.strip()
            product_info["selling_price"] = self._extract_price(price_text)
        
        # Extract original price (if available)
        original_price_elem = soup.select_one("span.a-price.a-text-price span.a-offscreen")
        if original_price_elem:
            original_price_text = original_price_elem.text.strip()
            product_info["mrp"] = self._extract_price(original_price_text)
            
            # Calculate discount percentage if both prices are available
            if "selling_price" in product_info and "mrp" in product_info:
                if product_info["mrp"] > 0:
                    discount = ((product_info["mrp"] - product_info["selling_price"]) / product_info["mrp"]) * 100
                    product_info["discount_percent"] = round(discount, 2)
        
        # Extract rating
        rating_elem = soup.select_one("#acrPopover")
        if rating_elem and 'title' in rating_elem.attrs:
            rating_text = rating_elem['title']
            rating_match = re.search(r'(\d+(\.\d+)?)', rating_text)
            if rating_match:
                product_info["average_rating"] = float(rating_match.group(1))
        
        # Extract rating count
        rating_count_elem = soup.select_one("#acrCustomerReviewText")
        if rating_count_elem:
            count_text = rating_count_elem.text.strip()
            count_match = re.search(r'(\d+(\,\d+)*)', count_text)
            if count_match:
                product_info["rating_count"] = int(count_match.group(1).replace(',', ''))
        
        # Extract availability/stock status
        availability_elem = soup.select_one("#availability")
        if availability_elem:
            availability = availability_elem.text.strip()
            product_info["availability"] = availability
            product_info["in_stock"] = "in stock" in availability.lower()
        
        # Extract product description
        description_elem = soup.select_one("#productDescription")
        if description_elem:
            product_info["description"] = description_elem.text.strip()
        
        # Extract product features/bullet points
        feature_bullets = soup.select("#feature-bullets li")
        if feature_bullets:
            features = []
            for bullet in feature_bullets:
                bullet_text = bullet.text.strip()
                if bullet_text and not "hide" in bullet.get("class", []):
                    features.append(bullet_text)
            
            if features:
                product_info["features"] = features
        
        # Extract product images
        image_gallery = soup.select("#altImages img")
        images = []
        
        # Try to get the large image first
        main_image_elem = soup.select_one("#landingImage")
        if main_image_elem and 'data-old-hires' in main_image_elem.attrs:
            images.append(main_image_elem['data-old-hires'])
        elif main_image_elem and 'src' in main_image_elem.attrs:
            images.append(main_image_elem['src'])
        
        # Add gallery thumbnails (try to get larger versions)
        for img in image_gallery:
            if 'src' in img.attrs:
                # Replace thumbnail with large image URL
                img_url = img['src']
                # Convert thumbnail URL to high-res URL
                high_res_url = re.sub(r'._SS\d+_', '._SL1500_', img_url)
                if high_res_url not in images:
                    images.append(high_res_url)
        
        if images:
            product_info["images"] = images
        
        # Extract product details table
        details_table = {}
        detail_rows = soup.select(".prodDetTable tr") or soup.select(".a-expander-content table tr")
        
        for row in detail_rows:
            cells = row.select("td, th")
            if len(cells) >= 2:
                key = cells[0].text.strip()
                value = cells[1].text.strip()
                if key and value:
                    details_table[key] = value
        
        if details_table:
            product_info["specifications"] = details_table
        
        # Extract category information
        breadcrumbs = soup.select("#wayfinding-breadcrumbs_feature_div li")
        if breadcrumbs:
            categories = []
            for crumb in breadcrumbs:
                crumb_text = crumb.text.strip()
                if crumb_text and '›' not in crumb_text:
                    categories.append(crumb_text)
            
            if categories:
                product_info["categories"] = categories
                if categories:
                    product_info["category"] = categories[-1]  # Main category
        
        return product_info
    
    def save_to_json(self, data, output_file=None):
        """
        Save the extracted product information to a JSON file.
        
        Args:
            data (dict): The product information
            output_file (str, optional): Output file name. Defaults to None.
            
        Returns:
            str: Path to the saved file
        """
        if not data:
            return None
        
        if not output_file:
            product_id = data.get('product_id', 'unknown')
            region = data.get('region', 'us')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"amazon_{region}_product_{product_id}_{timestamp}.json"
        
        output_path = os.path.join(os.getcwd(), output_file)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"Product information saved to {output_path}")
        return output_path
    
    def save_to_csv(self, data, output_file=None):
        """
        Save the extracted product information to a CSV file.
        
        Args:
            data (dict): The product information
            output_file (str, optional): Output file name. Defaults to None.
            
        Returns:
            str: Path to the saved file
        """
        if not data:
            return None
        
        if not output_file:
            product_id = data.get('product_id', 'unknown')
            region = data.get('region', 'us')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"amazon_{region}_product_{product_id}_{timestamp}.csv"
        
        output_path = os.path.join(os.getcwd(), output_file)
        
        # Flatten the nested dictionary for CSV
        flat_data = {k: v for k, v in data.items() if not isinstance(v, (dict, list))}
        
        # Handle specific fields
        if 'images' in data and data['images']:
            flat_data['image_url'] = data['images'][0]  # Save first image URL
            flat_data['all_images'] = "|".join(data['images'])
        
        if 'specifications' in data and data['specifications']:
            for key, value in data['specifications'].items():
                # Create safe key names for CSV
                safe_key = re.sub(r'[^\w]', '_', key).lower()
                flat_data[f"spec_{safe_key}"] = value
        
        if 'features' in data and data['features']:
            flat_data['features'] = "|".join(data['features'])
        
        if 'categories' in data and data['categories']:
            flat_data['categories'] = "|".join(data['categories'])
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=flat_data.keys())
            writer.writeheader()
            writer.writerow(flat_data)
        
        print(f"Product information saved to {output_path}")
        return output_path
    
    def _extract_product_id(self, url):
        """Extract the ASIN (Amazon product ID) from the URL."""
        match = re.search(r'/dp/([A-Z0-9]{10})', url)
        if match:
            return match.group(1)
        return None
    
    def _extract_region_from_url(self, url):
        """Extract the region from the Amazon URL."""
        for region, domain in self.AMAZON_DOMAINS.items():
            if domain in url:
                return region
        return "us"  # Default
    
    def _extract_price(self, price_text):
        """Extract numerical price from text."""
        if not price_text:
            return None
        
        # Remove currency symbol and commas
        clean_price = re.sub(r'[^\d.]', '', price_text)
        
        try:
            return float(clean_price)
        except ValueError:
            return None