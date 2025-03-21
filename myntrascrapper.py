import requests
import json
import argparse
from datetime import datetime
import os
import csv
import time
import random
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MyntraScraper:
    """A scraper for extracting product details from Myntra's API."""
    
    def __init__(self):
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
        
        
        # Visit the homepage first to get cookies
        self.session.get("https://www.myntra.com/")

    def get_product_details(self, product_id):
        """Fetch product details from Myntra API for a given product ID.
        
        Args:
            product_id (str): The Myntra product ID
            
        Returns:
            dict: Product details data
        """
        url = f"{self.base_url}{product_id}"
        try:
            # Add a random delay between 1-3 seconds
            time.sleep(1 + 2 * random.random())
            logger.info(f"Fetching details for product ID: {product_id}")
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching product details for ID {product_id}: {e}")
            return None    


    def extract_product_info(self, data):
        """Extract relevant product information from the API response.
        
        Args:
            data (dict): The API response data
            
        Returns:
            dict: Extracted product information
        """
        if not data or 'style' not in data:
            logger.warning("Invalid API response: 'style' not found in data")
            return None
        
        style = data['style']
        
        # Check if product is out of stock
        flags = style.get('flags', {})
        is_out_of_stock = flags.get('outOfStock', False)
        
        # Extract basic product information
        product_info = {
            "product_id": style.get('id'),
            "name": style.get('name'),
            "brand": style.get('brand', {}).get('name'),
            "mrp": style.get('mrp'),
            "category": style.get('analytics', {}).get('masterCategory'),
            "sub_category": style.get('analytics', {}).get('subCategory'),
            "article_type": style.get('analytics', {}).get('articleType'),
            "gender": style.get('analytics', {}).get('gender'),
            "color": style.get('baseColour'),
            "country_of_origin": style.get('countryOfOrigin'),
            "manufacturer": style.get('manufacturer'),
            "in_stock": not is_out_of_stock
        }
        
        # Extract discount information
        discounts = style.get('discounts', [])
        if discounts:
            product_info["discount_percent"] = discounts[0].get('discountPercent')
            product_info["discounted_price"] = int(style.get('mrp') * (1 - discounts[0].get('discountPercent', 0)/100))
        
        # Extract images
        images = []
        media = style.get('media', {})
        albums = media.get('albums', [])
        for album in albums:
            if album.get('name') == 'default':
                for image in album.get('images', []):
                    if 'secureSrc' in image:
                        # Replace placeholders with actual values
                        img_url = image['secureSrc'].replace('($height)', '1080').replace('($qualityPercentage)', '90').replace('($width)', '720')
                        images.append(img_url)
        
        product_info["images"] = images
        
        # Extract product details
        for detail in style.get('productDetails', []):
            if detail.get('title') == 'Product Details':
                product_info["details"] = detail.get('description')
            elif detail.get('title') == 'MATERIAL & CARE':
                product_info["material_care"] = detail.get('description')
            elif detail.get('title') == 'SIZE & FIT':
                product_info["size_fit"] = detail.get('description')
        
        # Extract sizes
        sizes = []
        for size in style.get('sizes', []):
            size_info = {
                "label": size.get('label'),
                "available": size.get('available'),
                "sku_id": size.get('skuId')
            }
            sizes.append(size_info)
        
        product_info["sizes"] = sizes
        
        # Extract rating information
        ratings = style.get('ratings', {})
        if ratings:
            product_info["average_rating"] = ratings.get('averageRating')
            product_info["rating_count"] = ratings.get('totalCount')
        
        return product_info
    
    def save_to_json(self, data, output_file=None):
        """Save the extracted product information to a JSON file.
        
        Args:
            data (dict): The product information
            output_file (str, optional): Output file name. Defaults to None.
            
        Returns:
            str: Path to the saved file
        """
        if not data:
            return None
        
        if not output_file:
            product_id = data.get('product_id')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"myntra_product_{product_id}_{timestamp}.json"
        
        output_path = os.path.join(os.getcwd(), output_file)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"Product information saved to {output_path}")
        return output_path
    
    def save_to_csv(self, data, output_file=None):
        """Save the extracted product information to a CSV file.
        
        Args:
            data (dict): The product information
            output_file (str, optional): Output file name. Defaults to None.
            
        Returns:
            str: Path to the saved file
        """
        if not data:
            return None
        
        if not output_file:
            product_id = data.get('product_id')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"myntra_product_{product_id}_{timestamp}.csv"
        
        output_path = os.path.join(os.getcwd(), output_file)
        
        # Flatten the nested dictionary for CSV
        flat_data = {k: v for k, v in data.items() if not isinstance(v, (dict, list))}
        
        # Handle special fields
        if 'images' in data and data['images']:
            flat_data['image_url'] = data['images'][0]  # Save the first image URL
            flat_data['all_images'] = "|".join(data['images'])
        
        if 'sizes' in data and data['sizes']:
            available_sizes = [size['label'] for size in data['sizes'] if size['available']]
            flat_data['available_sizes'] = "|".join(available_sizes)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=flat_data.keys())
            writer.writeheader()
            writer.writerow(flat_data)
        
        print(f"Product information saved to {output_path}")
        return output_path

def main():
    parser = argparse.ArgumentParser(description='Scrape product details from Myntra')
    parser.add_argument('product_id', help='Myntra product ID')
    parser.add_argument('--format', choices=['json', 'csv', 'both'], default='json',
                        help='Output format (default: json)')
    parser.add_argument('--output', help='Output file name (without extension)')
    parser.add_argument('--from-csv', help='Load product IDs from a CSV file')
    
    args = parser.parse_args()
    
    scraper = MyntraScraper()
    
    # Check if we're loading from a CSV file
    if args.from_csv:
        logger.info(f"Attempting to load product IDs from CSV file: {args.from_csv}")
        try:
            import pandas as pd
            df = pd.read_csv(args.from_csv)
            
            # Try to identify the ID column
            id_columns = ['product_id', 'style_id', 'id']
            id_column = None
            for col in id_columns:
                if col in df.columns:
                    id_column = col
                    logger.info(f"Found ID column in CSV: {col}")
                    break
                    
            if id_column is None:
                logger.error("CSV must contain a column named 'product_id', 'style_id', or 'id'")
                return
                
            # Get the list of product IDs
            product_ids = df[id_column].astype(str).tolist()
            logger.info(f"Successfully loaded {len(product_ids)} product IDs from CSV")
            logger.info(f"First 5 IDs for verification: {product_ids[:5]}")
            
            # Process each product ID
            for i, product_id in enumerate(product_ids):
                logger.info(f"Processing product {i+1}/{len(product_ids)}: {product_id}")
                data = scraper.get_product_details(product_id)
                
                if not data:
                    logger.warning(f"Failed to retrieve data for product ID: {product_id}")
                    continue
                
                product_info = scraper.extract_product_info(data)
                
                if not product_info:
                    logger.warning(f"Failed to extract information for product ID: {product_id}")
                    continue
                
                # Check if product is in stock
                if not product_info.get('in_stock', True):
                    logger.warning(f"Product ID {product_id} is out of stock, but extracting available information")
                
                # Set output filenames
                if args.output:
                    base_name = f"{args.output}_{product_id}"
                else:
                    base_name = None
                
                if args.format in ['json', 'both']:
                    scraper.save_to_json(product_info, f"{base_name}.json" if base_name else None)
                
                if args.format in ['csv', 'both']:
                    scraper.save_to_csv(product_info, f"{base_name}.csv" if base_name else None)

        except Exception as e:
            logger.error(f"Error processing CSV file: {e}")
            return
    else:
        # Original single product processing
        logger.info(f"Processing single product ID: {args.product_id}")
        data = scraper.get_product_details(args.product_id)
        
        if not data:
            logger.error("Failed to retrieve product data")
            return
        
        product_info = scraper.extract_product_info(data)
        
        if not product_info:
            logger.error("Failed to extract product information")
            return
        
        if args.output:
            json_output = f"{args.output}.json" if args.format in ['json', 'both'] else None
            csv_output = f"{args.output}.csv" if args.format in ['csv', 'both'] else None
        else:
            json_output = None
            csv_output = None
        
        if args.format in ['json', 'both']:
            scraper.save_to_json(product_info, json_output)
        
        if args.format in ['csv', 'both']:
            scraper.save_to_csv(product_info, csv_output)

if __name__ == "__main__":
    main()