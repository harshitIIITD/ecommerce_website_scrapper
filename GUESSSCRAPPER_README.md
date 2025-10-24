# GUESS Product Scraper - Comprehensive Documentation

## Overview

The GUESS Product Scraper is a robust, feature-rich web scraping tool designed specifically for scraping GUESS brand products from e-commerce platforms. It includes advanced features like resume on failure, rate limiting, parallel processing, deduplication, and comprehensive analytics.

## Features

### 1. **Single Dataset with Richer Data Fields**
The scraper extracts comprehensive product information including:
- Product ID, name, brand
- Pricing (MRP, discounted price, discount percentage)
- Category, sub-category, article type
- Gender, color, country of origin
- Stock availability
- Multiple product images (pipe-separated URLs)
- Detailed product descriptions
- Material and care information
- Size and fit details
- Available sizes
- Ratings and review counts
- Scrape date and source URL

### 2. **Resume on Failure Functionality**
- **Checkpoint System**: Automatically saves progress to a checkpoint file
- **Automatic Recovery**: Resume from where it left off if interrupted
- **Failed Product Tracking**: Keeps track of failed product IDs for retry
- **Manual Reset**: Use `--reset` flag to start fresh

### 3. **Rate Limiting**
- **Thread-Safe Rate Limiter**: Prevents overwhelming the server
- **Configurable Delays**: Set minimum and maximum delay between requests
- **Random Delays**: Adds randomness to appear more human-like
- Default: 1-3 seconds between requests (configurable)

### 4. **Parallel Processing**
- **ThreadPoolExecutor**: Processes multiple products simultaneously
- **Configurable Workers**: Set number of parallel workers (default: 3)
- **Progress Tracking**: Real-time progress updates during scraping
- **Efficient Resource Usage**: Optimal balance between speed and reliability

### 5. **Deduplication**
- **Automatic Deduplication**: Removes duplicate product IDs when loading from multiple CSVs
- **Database-Level Deduplication**: Uses product_id as primary key in SQLite
- **Checkpoint-Based Skipping**: Skips already processed products

### 6. **Category Filtering**
- **Article Type Filter**: Filter products by article types (e.g., Dresses, Tops, Jeans)
- **Brand Filter**: Automatically filters only GUESS brand products
- **Multiple Filters**: Apply multiple category filters simultaneously

### 7. **Database Export**
- **SQLite Database**: Stores all scraped data in a structured database
- **CSV Export**: Export database to CSV format anytime
- **Auto-Export**: Automatically exports to CSV after scraping completes
- **Persistent Storage**: Data remains available even after program exits

### 8. **Analytics Features**
Comprehensive analytics including:
- Total products count
- In-stock vs out-of-stock statistics
- Price statistics (average, min, max)
- Average discount percentage
- Category breakdown
- Sub-category breakdown
- Gender distribution

### 9. **Bulk CSV Processing**
- **Single CSV**: Process products from one CSV file
- **Multiple CSVs**: Process products from multiple CSV files simultaneously
- **Auto-Deduplication**: Automatically removes duplicates across files
- **Flexible ID Column**: Configure which column contains product IDs

### 10. **Comprehensive Logging**
- **Dual Output**: Logs to both file and console
- **Detailed Progress**: Track every step of the scraping process
- **Error Tracking**: Detailed error messages for debugging
- **Log File**: Persistent log saved to `guessscrapper.log`

## Installation

### Requirements
```bash
pip install requests
```

The scraper uses only standard Python libraries plus `requests`.

## Usage

### Basic Usage

#### 1. Scrape from Single CSV
```bash
python guessscrapper.py --csv products.csv
```

#### 2. Scrape from Multiple CSVs
```bash
python guessscrapper.py --csv file1.csv file2.csv file3.csv
```

#### 3. Scrape with Category Filter
```bash
python guessscrapper.py --csv products.csv --filter Dresses Tops Jeans
```

#### 4. Scrape with Custom Settings
```bash
python guessscrapper.py --csv products.csv \
    --min-delay 2 \
    --max-delay 5 \
    --workers 5 \
    --database my_products.db \
    --output my_export.csv
```

### Advanced Usage

#### Resume After Interruption
If the scraper is interrupted (Ctrl+C or error), simply run the same command again:
```bash
python guessscrapper.py --csv products.csv
```
It will automatically resume from the checkpoint.

#### Reset and Start Fresh
```bash
python guessscrapper.py --csv products.csv --reset
```

#### Export Existing Database
```bash
python guessscrapper.py --export-only --output products.csv
```

#### Custom Checkpoint and Database Files
```bash
python guessscrapper.py --csv products.csv \
    --checkpoint my_checkpoint.pkl \
    --database my_database.db
```

#### Custom ID Column Name
If your CSV uses a different column name for product IDs:
```bash
python guessscrapper.py --csv products.csv --id-column product_id
```

## Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--csv` | CSV file(s) containing product IDs (required unless --export-only) | - |
| `--id-column` | Column name for product IDs | `style_id` |
| `--min-delay` | Minimum delay between requests (seconds) | `1.0` |
| `--max-delay` | Maximum delay between requests (seconds) | `3.0` |
| `--workers` | Number of parallel workers | `3` |
| `--filter` | Filter by article types (space-separated) | `None` |
| `--checkpoint` | Checkpoint file path | `scraper_checkpoint.pkl` |
| `--database` | Database file path | `guess_products.db` |
| `--output` | Output CSV file name | Auto-generated |
| `--export-only` | Only export existing database to CSV | `False` |
| `--reset` | Reset checkpoint and start fresh | `False` |

## CSV Input Format

The input CSV should contain a column with product IDs. Example:

```csv
style_id
30540676
29821370
25746336
```

Or with custom column name:
```csv
product_id,category
30540676,Dresses
29821370,Tops
```

## Output Format

### CSV Output
The output CSV includes all scraped fields in a flat structure:

```csv
product_id,name,brand,mrp,discounted_price,discount_percent,category,sub_category,article_type,gender,color,country_of_origin,manufacturer,in_stock,images,details,material_care,size_fit,available_sizes,average_rating,rating_count,scrape_date,source_url
32839091,GUESS Floral Print Midi Dress,GUESS,13599.0,6799.0,50.0,Apparel,Dress,Dresses,Women,Blue,Sri Lanka,,1,https://...|https://...,Blue floral print dress,100% Polyester,Model wears size S,S|M|L,4.5,120,2025-03-19 01:23:08,https://www.myntra.com/32839091
```

### SQLite Database
The database has a single `products` table with all fields as columns. You can query it using any SQLite client:

```bash
sqlite3 guess_products.db "SELECT * FROM products WHERE gender='Women' LIMIT 5"
```

## Analytics Report

After scraping completes, the scraper generates a comprehensive report:

```
============================================================
SCRAPING REPORT
============================================================
Total products to process: 150
Successfully scraped: 142
Failed: 5
Skipped (already processed): 3
Filtered (category): 10
============================================================

DATABASE ANALYTICS
============================================================
Total products in database: 142
In stock: 128
Out of stock: 14

Price Statistics:
  Average price: ₹4567.89
  Min price: ₹1299.0
  Max price: ₹15999.0
  Average discount: 45.2%

By Category:
  Apparel: 142

By Gender:
  Women: 95
  Men: 47
============================================================
```

## Error Handling

The scraper handles various error scenarios gracefully:

1. **Network Errors**: Logs error and marks product as failed
2. **Invalid Data**: Skips invalid products and continues
3. **Interruption**: Saves checkpoint automatically
4. **Missing Data**: Handles missing fields with None/empty values
5. **Duplicate IDs**: Automatically deduplicates

## Performance Tips

1. **Optimal Workers**: Use 3-5 workers for best balance
2. **Rate Limiting**: Keep delays at 1-3 seconds to avoid being blocked
3. **Batch Processing**: Process large datasets in batches if needed
4. **Resume Feature**: Don't worry about interruptions, just resume
5. **Filtering**: Use category filters to reduce processing time

## Troubleshooting

### Products Being Skipped
- Check if they're already in the checkpoint (already processed)
- Use `--reset` to start fresh

### Connection Errors
- Increase delays with `--min-delay` and `--max-delay`
- Reduce workers with `--workers`

### Out of Memory
- Reduce number of workers
- Process smaller batches

### Wrong Product IDs
- Check your CSV column name
- Use `--id-column` to specify correct column

## Files Generated

1. **`guess_products.db`** - SQLite database with all products
2. **`scraper_checkpoint.pkl`** - Checkpoint file for resume functionality
3. **`guess_products_YYYYMMDD_HHMMSS.csv`** - Exported CSV (auto-generated name)
4. **`guessscrapper.log`** - Detailed log file

## Example Workflow

### Complete Workflow Example

```bash
# Step 1: Initial scrape
python guessscrapper.py --csv myntra_products.csv --workers 3

# Step 2: Interrupted? Just resume
python guessscrapper.py --csv myntra_products.csv

# Step 3: Add more products from another CSV
python guessscrapper.py --csv additional_products.csv

# Step 4: Export everything to custom CSV
python guessscrapper.py --export-only --output all_guess_products.csv

# Step 5: Start fresh for a different category
python guessscrapper.py --csv products.csv --filter Dresses --reset
```

## Best Practices

1. **Start Small**: Test with a small CSV first
2. **Monitor Logs**: Watch the log file for any issues
3. **Regular Exports**: Export to CSV periodically
4. **Backup Database**: Keep backups of your database file
5. **Respectful Scraping**: Use appropriate rate limits
6. **Category Filtering**: Filter early to save time
7. **Checkpoint Management**: Keep checkpoint files for resume capability

## Python API Usage

You can also use the scraper as a Python module:

```python
from guessscrapper import GuessScraper

# Initialize scraper
scraper = GuessScraper(
    rate_limit_min=1.0,
    rate_limit_max=3.0,
    max_workers=3,
    category_filter=['Dresses', 'Tops']
)

# Scrape from CSV
scraper.scrape_from_csv('products.csv', id_column='style_id')

# Generate report
scraper.generate_report()

# Export to CSV
scraper.export_to_csv('output.csv')

# Cleanup
scraper.cleanup()
```

## License

This scraper is provided as-is for educational and personal use. Please respect the terms of service of the websites you scrape.

## Support

For issues or questions:
1. Check the log file (`guessscrapper.log`)
2. Review this documentation
3. Verify your CSV format and column names
4. Test with a small dataset first
