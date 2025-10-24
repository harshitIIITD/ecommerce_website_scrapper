"""
Comprehensive GUESS Product Scraper
====================================
A robust web scraper for GUESS brand products with advanced features:
- Single dataset with richer data fields
- Resume on failure functionality
- Rate limiting for requests
- Parallel processing
- Data deduplication
- Category filtering
- Database export (SQLite + CSV)
- Analytics and reporting
"""

import requests
import json
import csv
import sqlite3
import time
import random
import logging
import os
import argparse
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
import threading
import pickle

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('guessscrapper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class ProductData:
    """Data class for product information"""
    product_id: str
    name: str
    brand: str
    mrp: float
    discounted_price: Optional[float]
    discount_percent: Optional[float]
    category: str
    sub_category: str
    article_type: str
    gender: str
    color: str
    country_of_origin: Optional[str]
    manufacturer: Optional[str]
    in_stock: bool
    images: str  # pipe-separated URLs
    details: Optional[str]
    material_care: Optional[str]
    size_fit: Optional[str]
    available_sizes: str  # pipe-separated sizes
    average_rating: Optional[float]
    rating_count: Optional[int]
    scrape_date: str
    source_url: str
    
    def to_dict(self) -> Dict:
        """Convert dataclass to dictionary"""
        return asdict(self)


class RateLimiter:
    """Thread-safe rate limiter for API requests"""
    
    def __init__(self, min_delay: float = 1.0, max_delay: float = 3.0):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.lock = threading.Lock()
        self.last_request_time = 0
    
    def wait(self):
        """Wait for rate limit"""
        with self.lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            delay = random.uniform(self.min_delay, self.max_delay)
            
            if time_since_last < delay:
                sleep_time = delay - time_since_last
                time.sleep(sleep_time)
            
            self.last_request_time = time.time()


class CheckpointManager:
    """Manages checkpoints for resume functionality"""
    
    def __init__(self, checkpoint_file: str = "scraper_checkpoint.pkl"):
        self.checkpoint_file = checkpoint_file
        self.processed_ids: Set[str] = set()
        self.failed_ids: List[str] = []
        self.load_checkpoint()
    
    def load_checkpoint(self):
        """Load checkpoint from file"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'rb') as f:
                    data = pickle.load(f)
                    self.processed_ids = data.get('processed', set())
                    self.failed_ids = data.get('failed', [])
                logger.info(f"Loaded checkpoint: {len(self.processed_ids)} processed, {len(self.failed_ids)} failed")
            except Exception as e:
                logger.warning(f"Could not load checkpoint: {e}")
    
    def save_checkpoint(self):
        """Save checkpoint to file"""
        try:
            with open(self.checkpoint_file, 'wb') as f:
                pickle.dump({
                    'processed': self.processed_ids,
                    'failed': self.failed_ids
                }, f)
            logger.info(f"Checkpoint saved: {len(self.processed_ids)} processed")
        except Exception as e:
            logger.error(f"Could not save checkpoint: {e}")
    
    def mark_processed(self, product_id: str):
        """Mark a product as successfully processed"""
        self.processed_ids.add(product_id)
    
    def mark_failed(self, product_id: str):
        """Mark a product as failed"""
        if product_id not in self.failed_ids:
            self.failed_ids.append(product_id)
    
    def is_processed(self, product_id: str) -> bool:
        """Check if product was already processed"""
        return product_id in self.processed_ids


class DatabaseManager:
    """Manages SQLite database for product storage"""
    
    def __init__(self, db_path: str = "guess_products.db"):
        self.db_path = db_path
        self.conn = None
        self.init_database()
    
    def init_database(self):
        """Initialize database and create tables"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,
                name TEXT,
                brand TEXT,
                mrp REAL,
                discounted_price REAL,
                discount_percent REAL,
                category TEXT,
                sub_category TEXT,
                article_type TEXT,
                gender TEXT,
                color TEXT,
                country_of_origin TEXT,
                manufacturer TEXT,
                in_stock INTEGER,
                images TEXT,
                details TEXT,
                material_care TEXT,
                size_fit TEXT,
                available_sizes TEXT,
                average_rating REAL,
                rating_count INTEGER,
                scrape_date TEXT,
                source_url TEXT
            )
        ''')
        self.conn.commit()
        logger.info(f"Database initialized: {self.db_path}")
    
    def insert_product(self, product: ProductData) -> bool:
        """Insert or update product in database"""
        try:
            data = product.to_dict()
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?' for _ in data])
            query = f"INSERT OR REPLACE INTO products ({columns}) VALUES ({placeholders})"
            self.conn.execute(query, list(data.values()))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Database insert error: {e}")
            return False
    
    def get_product_count(self) -> int:
        """Get total number of products in database"""
        cursor = self.conn.execute("SELECT COUNT(*) FROM products")
        return cursor.fetchone()[0]
    
    def export_to_csv(self, output_file: str):
        """Export database to CSV"""
        cursor = self.conn.execute("SELECT * FROM products")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)
        
        logger.info(f"Exported {len(rows)} products to {output_file}")
    
    def get_analytics(self) -> Dict:
        """Generate analytics from database"""
        analytics = {}
        
        # Total products
        analytics['total_products'] = self.get_product_count()
        
        # In stock vs out of stock
        cursor = self.conn.execute("SELECT in_stock, COUNT(*) FROM products GROUP BY in_stock")
        stock_data = dict(cursor.fetchall())
        analytics['in_stock'] = stock_data.get(1, 0)
        analytics['out_of_stock'] = stock_data.get(0, 0)
        
        # Price statistics
        cursor = self.conn.execute("""
            SELECT 
                AVG(discounted_price) as avg_price,
                MIN(discounted_price) as min_price,
                MAX(discounted_price) as max_price,
                AVG(discount_percent) as avg_discount
            FROM products WHERE discounted_price IS NOT NULL
        """)
        price_stats = cursor.fetchone()
        analytics['avg_price'] = round(price_stats[0], 2) if price_stats[0] else 0
        analytics['min_price'] = price_stats[1]
        analytics['max_price'] = price_stats[2]
        analytics['avg_discount'] = round(price_stats[3], 2) if price_stats[3] else 0
        
        # Category breakdown
        cursor = self.conn.execute("SELECT category, COUNT(*) FROM products GROUP BY category")
        analytics['by_category'] = dict(cursor.fetchall())
        
        # Sub-category breakdown
        cursor = self.conn.execute("SELECT sub_category, COUNT(*) FROM products GROUP BY sub_category")
        analytics['by_sub_category'] = dict(cursor.fetchall())
        
        # Gender breakdown
        cursor = self.conn.execute("SELECT gender, COUNT(*) FROM products GROUP BY gender")
        analytics['by_gender'] = dict(cursor.fetchall())
        
        return analytics
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


class GuessScraper:
    """Main scraper class for GUESS products"""
    
    def __init__(self, 
                 rate_limit_min: float = 1.0,
                 rate_limit_max: float = 3.0,
                 max_workers: int = 3,
                 checkpoint_file: str = "scraper_checkpoint.pkl",
                 db_path: str = "guess_products.db",
                 category_filter: Optional[List[str]] = None):
        """
        Initialize the scraper
        
        Args:
            rate_limit_min: Minimum delay between requests (seconds)
            rate_limit_max: Maximum delay between requests (seconds)
            max_workers: Number of parallel workers
            checkpoint_file: Path to checkpoint file
            db_path: Path to SQLite database
            category_filter: List of categories to filter (e.g., ['Dresses', 'Tops'])
        """
        self.base_url = "https://www.myntra.com/gateway/v2/product/"
        self.session = requests.Session()
        self.session.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.myntra.com/",
            "Origin": "https://www.myntra.com",
            "Connection": "keep-alive",
            "DNT": "1",
            "Cache-Control": "max-age=0"
        }
        
        # Initialize components
        self.rate_limiter = RateLimiter(rate_limit_min, rate_limit_max)
        self.checkpoint = CheckpointManager(checkpoint_file)
        self.db = DatabaseManager(db_path)
        self.max_workers = max_workers
        self.category_filter = set(category_filter) if category_filter else None
        
        # Statistics
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'filtered': 0
        }
        
        # Visit homepage to get cookies
        try:
            self.session.get("https://www.myntra.com/", timeout=5)
        except Exception as e:
            logger.warning(f"Could not visit homepage (might be offline): {e}")
        logger.info("GuessScraper initialized")
    
    def get_product_details(self, product_id: str) -> Optional[Dict]:
        """Fetch product details from Myntra API"""
        url = f"{self.base_url}{product_id}"
        try:
            self.rate_limiter.wait()
            logger.info(f"Fetching product ID: {product_id}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching product {product_id}: {e}")
            return None
    
    def extract_product_info(self, data: Dict, product_id: str) -> Optional[ProductData]:
        """Extract and structure product information"""
        if not data or 'style' not in data:
            logger.warning(f"Invalid data for product {product_id}")
            return None
        
        style = data['style']
        
        # Check brand filter
        brand = style.get('brand', {}).get('name', '')
        if brand.upper() != 'GUESS':
            logger.info(f"Skipping non-GUESS product {product_id}: {brand}")
            return None
        
        # Check category filter
        article_type = style.get('analytics', {}).get('articleType', '')
        if self.category_filter and article_type not in self.category_filter:
            logger.info(f"Filtered out product {product_id}: {article_type} not in filter")
            self.stats['filtered'] += 1
            return None
        
        # Extract data
        flags = style.get('flags', {})
        is_out_of_stock = flags.get('outOfStock', False)
        
        # Extract images
        images = []
        media = style.get('media', {})
        albums = media.get('albums', [])
        for album in albums:
            if album.get('name') == 'default':
                for image in album.get('images', []):
                    if 'secureSrc' in image:
                        img_url = image['secureSrc'].replace('($height)', '1080').replace('($qualityPercentage)', '90').replace('($width)', '720')
                        images.append(img_url)
        
        # Extract sizes
        available_sizes = []
        for size in style.get('sizes', []):
            if size.get('available'):
                available_sizes.append(size.get('label'))
        
        # Extract details
        details = None
        material_care = None
        size_fit = None
        for detail in style.get('productDetails', []):
            title = detail.get('title', '')
            if title == 'Product Details':
                details = detail.get('description')
            elif title == 'MATERIAL & CARE':
                material_care = detail.get('description')
            elif title == 'SIZE & FIT':
                size_fit = detail.get('description')
        
        # Calculate discounted price
        mrp = style.get('mrp', 0)
        discounts = style.get('discounts', [])
        discount_percent = None
        discounted_price = None
        if discounts:
            discount_percent = discounts[0].get('discountPercent')
            if discount_percent and mrp:
                discounted_price = mrp * (1 - discount_percent / 100)
        
        # Extract ratings
        ratings = style.get('ratings', {})
        
        product = ProductData(
            product_id=str(product_id),
            name=style.get('name', ''),
            brand=brand,
            mrp=float(mrp) if mrp else 0.0,
            discounted_price=float(discounted_price) if discounted_price else None,
            discount_percent=float(discount_percent) if discount_percent else None,
            category=style.get('analytics', {}).get('masterCategory', ''),
            sub_category=style.get('analytics', {}).get('subCategory', ''),
            article_type=article_type,
            gender=style.get('analytics', {}).get('gender', ''),
            color=style.get('baseColour', ''),
            country_of_origin=style.get('countryOfOrigin'),
            manufacturer=style.get('manufacturer'),
            in_stock=not is_out_of_stock,
            images='|'.join(images),
            details=details,
            material_care=material_care,
            size_fit=size_fit,
            available_sizes='|'.join(available_sizes),
            average_rating=float(ratings.get('averageRating', 0)) if ratings.get('averageRating') else None,
            rating_count=int(ratings.get('totalCount', 0)) if ratings.get('totalCount') else None,
            scrape_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            source_url=f"https://www.myntra.com/{product_id}"
        )
        
        return product
    
    def process_single_product(self, product_id: str) -> bool:
        """Process a single product"""
        # Check if already processed
        if self.checkpoint.is_processed(product_id):
            logger.info(f"Skipping already processed product: {product_id}")
            self.stats['skipped'] += 1
            return True
        
        # Fetch and extract data
        data = self.get_product_details(product_id)
        if not data:
            self.checkpoint.mark_failed(product_id)
            self.stats['failed'] += 1
            return False
        
        product = self.extract_product_info(data, product_id)
        if not product:
            self.checkpoint.mark_failed(product_id)
            self.stats['failed'] += 1
            return False
        
        # Save to database
        if self.db.insert_product(product):
            self.checkpoint.mark_processed(product_id)
            self.stats['success'] += 1
            logger.info(f"Successfully processed: {product_id} - {product.name}")
            return True
        else:
            self.checkpoint.mark_failed(product_id)
            self.stats['failed'] += 1
            return False
    
    def scrape_from_csv(self, csv_file: str, id_column: str = 'style_id'):
        """Scrape products from a CSV file"""
        logger.info(f"Loading product IDs from {csv_file}")
        
        product_ids = []
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if id_column in row:
                        product_ids.append(str(row[id_column]))
        except Exception as e:
            logger.error(f"Error reading CSV: {e}")
            return
        
        logger.info(f"Found {len(product_ids)} product IDs")
        self.stats['total'] = len(product_ids)
        
        # Process in parallel
        self.process_products_parallel(product_ids)
    
    def scrape_from_multiple_csvs(self, csv_files: List[str], id_column: str = 'style_id'):
        """Scrape products from multiple CSV files"""
        all_product_ids = set()  # Use set for automatic deduplication
        
        for csv_file in csv_files:
            logger.info(f"Loading product IDs from {csv_file}")
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if id_column in row:
                            all_product_ids.add(str(row[id_column]))
            except Exception as e:
                logger.error(f"Error reading {csv_file}: {e}")
        
        product_ids = list(all_product_ids)
        logger.info(f"Found {len(product_ids)} unique product IDs from {len(csv_files)} files")
        self.stats['total'] = len(product_ids)
        
        # Process in parallel
        self.process_products_parallel(product_ids)
    
    def process_products_parallel(self, product_ids: List[str]):
        """Process products in parallel using ThreadPoolExecutor"""
        logger.info(f"Starting parallel processing with {self.max_workers} workers")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_id = {
                executor.submit(self.process_single_product, pid): pid 
                for pid in product_ids
            }
            
            # Process completed tasks
            for i, future in enumerate(as_completed(future_to_id), 1):
                product_id = future_to_id[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Exception processing {product_id}: {e}")
                    self.checkpoint.mark_failed(product_id)
                    self.stats['failed'] += 1
                
                # Save checkpoint periodically
                if i % 10 == 0:
                    self.checkpoint.save_checkpoint()
                    logger.info(f"Progress: {i}/{len(product_ids)} - Success: {self.stats['success']}, Failed: {self.stats['failed']}, Skipped: {self.stats['skipped']}")
        
        # Final checkpoint save
        self.checkpoint.save_checkpoint()
        logger.info("Processing complete!")
    
    def generate_report(self):
        """Generate and display a comprehensive report"""
        logger.info("\n" + "="*60)
        logger.info("SCRAPING REPORT")
        logger.info("="*60)
        logger.info(f"Total products to process: {self.stats['total']}")
        logger.info(f"Successfully scraped: {self.stats['success']}")
        logger.info(f"Failed: {self.stats['failed']}")
        logger.info(f"Skipped (already processed): {self.stats['skipped']}")
        logger.info(f"Filtered (category): {self.stats['filtered']}")
        logger.info("="*60)
        
        # Database analytics
        analytics = self.db.get_analytics()
        logger.info("\nDATABASE ANALYTICS")
        logger.info("="*60)
        logger.info(f"Total products in database: {analytics['total_products']}")
        logger.info(f"In stock: {analytics['in_stock']}")
        logger.info(f"Out of stock: {analytics['out_of_stock']}")
        logger.info(f"\nPrice Statistics:")
        logger.info(f"  Average price: ₹{analytics['avg_price']}")
        logger.info(f"  Min price: ₹{analytics['min_price']}")
        logger.info(f"  Max price: ₹{analytics['max_price']}")
        logger.info(f"  Average discount: {analytics['avg_discount']}%")
        
        logger.info(f"\nBy Category:")
        for category, count in analytics['by_category'].items():
            logger.info(f"  {category}: {count}")
        
        logger.info(f"\nBy Gender:")
        for gender, count in analytics['by_gender'].items():
            logger.info(f"  {gender}: {count}")
        
        logger.info("="*60 + "\n")
    
    def export_to_csv(self, output_file: str = None):
        """Export database to CSV"""
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"guess_products_{timestamp}.csv"
        
        self.db.export_to_csv(output_file)
        return output_file
    
    def cleanup(self):
        """Clean up resources"""
        self.db.close()
        logger.info("Cleanup complete")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Comprehensive GUESS Product Scraper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape from single CSV
  python guessscrapper.py --csv products.csv
  
  # Scrape from multiple CSVs
  python guessscrapper.py --csv file1.csv file2.csv file3.csv
  
  # Scrape with category filter
  python guessscrapper.py --csv products.csv --filter Dresses Tops
  
  # Scrape with custom rate limits and workers
  python guessscrapper.py --csv products.csv --min-delay 2 --max-delay 5 --workers 5
  
  # Export existing database to CSV
  python guessscrapper.py --export-only --output my_products.csv
        """
    )
    
    parser.add_argument('--csv', nargs='+', help='CSV file(s) containing product IDs')
    parser.add_argument('--id-column', default='style_id', help='Column name for product IDs (default: style_id)')
    parser.add_argument('--min-delay', type=float, default=1.0, help='Minimum delay between requests (default: 1.0)')
    parser.add_argument('--max-delay', type=float, default=3.0, help='Maximum delay between requests (default: 3.0)')
    parser.add_argument('--workers', type=int, default=3, help='Number of parallel workers (default: 3)')
    parser.add_argument('--filter', nargs='+', help='Filter by article types (e.g., Dresses Tops)')
    parser.add_argument('--checkpoint', default='scraper_checkpoint.pkl', help='Checkpoint file path')
    parser.add_argument('--database', default='guess_products.db', help='Database file path')
    parser.add_argument('--output', help='Output CSV file name')
    parser.add_argument('--export-only', action='store_true', help='Only export existing database to CSV')
    parser.add_argument('--reset', action='store_true', help='Reset checkpoint and start fresh')
    
    args = parser.parse_args()
    
    # Handle reset
    if args.reset:
        if os.path.exists(args.checkpoint):
            os.remove(args.checkpoint)
            logger.info("Checkpoint reset")
    
    # Initialize scraper
    scraper = GuessScraper(
        rate_limit_min=args.min_delay,
        rate_limit_max=args.max_delay,
        max_workers=args.workers,
        checkpoint_file=args.checkpoint,
        db_path=args.database,
        category_filter=args.filter
    )
    
    try:
        # Export only mode
        if args.export_only:
            output_file = scraper.export_to_csv(args.output)
            logger.info(f"Export complete: {output_file}")
            return
        
        # Require CSV files for scraping
        if not args.csv:
            parser.error("--csv is required unless using --export-only")
        
        # Scrape from CSV(s)
        if len(args.csv) == 1:
            scraper.scrape_from_csv(args.csv[0], args.id_column)
        else:
            scraper.scrape_from_multiple_csvs(args.csv, args.id_column)
        
        # Generate report
        scraper.generate_report()
        
        # Auto-export to CSV
        output_file = scraper.export_to_csv(args.output)
        logger.info(f"Data exported to: {output_file}")
        
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user. Saving checkpoint...")
        scraper.checkpoint.save_checkpoint()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        scraper.cleanup()


if __name__ == "__main__":
    main()
