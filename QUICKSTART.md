# GUESS Scraper - Quick Start Guide

## Installation

No additional packages needed beyond standard Python libraries and requests:
```bash
pip install requests
```

## Quick Start

### 1. Basic Usage - Scrape from CSV
```bash
python guessscrapper.py --csv temp_1742041949.csv
```

### 2. Resume if Interrupted
Just run the same command again - it will automatically resume:
```bash
python guessscrapper.py --csv temp_1742041949.csv
```

### 3. Process Multiple CSV Files
```bash
python guessscrapper.py --csv file1.csv file2.csv file3.csv
```

### 4. Export Database to CSV
```bash
python guessscrapper.py --export-only --output my_products.csv
```

## Common Options

- `--workers 5` - Use 5 parallel workers (default: 3)
- `--min-delay 2 --max-delay 4` - Set rate limits (default: 1-3 seconds)
- `--filter Dresses Tops` - Only scrape specific categories
- `--reset` - Start fresh, ignore checkpoint
- `--output myfile.csv` - Custom output filename

## Output Files

- `guess_products.db` - SQLite database with all scraped data
- `guess_products_TIMESTAMP.csv` - CSV export (auto-generated)
- `scraper_checkpoint.pkl` - Resume checkpoint
- `guessscrapper.log` - Detailed log file

## Example: Complete Workflow

```bash
# Scrape products
python guessscrapper.py --csv temp_1742041949.csv --workers 3

# View results
python guessscrapper.py --export-only --output results.csv

# Start fresh with filter
python guessscrapper.py --csv temp_1742041949.csv --filter Dresses --reset
```

## Key Features

✅ Automatic resume on failure  
✅ Deduplication of products  
✅ Parallel processing  
✅ Rate limiting  
✅ Comprehensive analytics  
✅ CSV and SQLite export  
✅ Category filtering  
✅ Detailed logging  

For full documentation, see GUESSSCRAPPER_README.md
