"""
Prepare Product Dataset
Download and prepare Amazon products dataset from HuggingFace
"""

import logging
import pandas as pd
import json
from pathlib import Path
from typing import List, Dict
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from datasets import load_dataset
except ImportError:
    logger.error("datasets library not found. Install with: pip install datasets")
    sys.exit(1)


def download_dataset():
    """
    Download Amazon products dataset from HuggingFace
    
    Returns:
        Dataset object
    """
    logger.info("Downloading Amazon products dataset from HuggingFace...")
    try:
        dataset = load_dataset("ckandemir/amazon-products", split="train", revision="main")  # nosec B615
        logger.info(f"Downloaded dataset with {len(dataset)} products")
        return dataset
    except Exception as e:
        logger.error(f"Error downloading dataset: {e}")
        raise


def clean_product(product: Dict) -> Dict:
    """
    Clean and normalize a product
    
    Args:
        product: Raw product dictionary
        
    Returns:
        Cleaned product dictionary
    """
    cleaned = {}
    
    # Map fields (adjust based on actual dataset structure)
    cleaned['name'] = product.get('title') or product.get('name') or product.get('product_name', '')
    cleaned['description'] = product.get('description') or product.get('desc') or product.get('details', '')
    cleaned['category'] = product.get('category') or product.get('categories', '')
    cleaned['price'] = product.get('price') or product.get('cost') or product.get('list_price')
    cleaned['rating'] = product.get('rating') or product.get('stars') or product.get('avg_rating')
    cleaned['review_count'] = product.get('review_count') or product.get('reviews') or product.get('num_reviews')
    cleaned['image_url'] = product.get('image_url') or product.get('image') or product.get('img')
    cleaned['brand'] = product.get('brand') or product.get('manufacturer')
    
    # Generate ID if missing
    if not product.get('id') and not product.get('product_id'):
        import uuid
        cleaned['id'] = f"prod_{uuid.uuid4().hex[:12]}"
    else:
        cleaned['id'] = product.get('id') or product.get('product_id')
    
    # Clean price
    if cleaned['price']:
        try:
            if isinstance(cleaned['price'], str):
                # Remove currency symbols
                price_str = cleaned['price'].replace('$', '').replace(',', '').strip()
                cleaned['price'] = float(price_str) if price_str else None
            else:
                cleaned['price'] = float(cleaned['price'])
        except (ValueError, TypeError):
            cleaned['price'] = None
    
    # Clean rating (normalize to 0-5)
    if cleaned['rating']:
        try:
            rating = float(cleaned['rating'])
            if rating > 5:
                rating = rating / 2.0  # Assume out of 10
            cleaned['rating'] = rating if 0 <= rating <= 5 else None
        except (ValueError, TypeError):
            cleaned['rating'] = None
    
    # Clean review count
    if cleaned['review_count']:
        try:
            cleaned['review_count'] = int(cleaned['review_count'])
        except (ValueError, TypeError):
            cleaned['review_count'] = None
    
    # Ensure name is not empty
    if not cleaned['name']:
        cleaned['name'] = f"Product {cleaned['id']}"
    
    # Ensure description is not empty (use name as fallback)
    if not cleaned['description']:
        cleaned['description'] = cleaned['name']
    
    return cleaned


def create_test_subsets(dataset, output_dir: Path):
    """
    Create test subsets from dataset
    
    Args:
        dataset: Dataset object
        output_dir: Output directory
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Convert to list of dictionaries
    logger.info("Converting dataset to list...")
    products = []
    for item in dataset:
        cleaned = clean_product(item)
        # Only include products with name and description
        if cleaned['name'] and cleaned['description']:
            products.append(cleaned)
    
    logger.info(f"Cleaned {len(products)} valid products")
    
    # Create subsets
    subsets = {
        'test_100.csv': 100,
        'test_1000.csv': 1000,
        'test_10000.csv': 10000
    }
    
    for filename, count in subsets.items():
        if len(products) >= count:
            subset = products[:count]
            output_path = output_dir / filename
            
            # Save as CSV
            df = pd.DataFrame(subset)
            df.to_csv(output_path, index=False)
            logger.info(f"Created {filename} with {len(subset)} products")
        else:
            logger.warning(f"Not enough products for {filename} (have {len(products)}, need {count})")
    
    # Also save full dataset if requested
    if len(products) > 0:
        full_path = output_dir / "full_dataset.csv"
        df = pd.DataFrame(products)
        df.to_csv(full_path, index=False)
        logger.info(f"Created full_dataset.csv with {len(products)} products")


def main():
    """Main function"""
    # Set output directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    output_dir = project_root / "data" / "test_datasets"
    
    logger.info(f"Output directory: {output_dir}")
    
    try:
        # Download dataset
        dataset = download_dataset()
        
        # Create test subsets
        create_test_subsets(dataset, output_dir)
        
        logger.info("Dataset preparation complete!")
        logger.info(f"Test datasets saved to: {output_dir}")
        
    except Exception as e:
        logger.error(f"Error preparing dataset: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

