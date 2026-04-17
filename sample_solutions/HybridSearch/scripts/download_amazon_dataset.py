"""
Download and prepare Amazon Products dataset from HuggingFace
"""
import pandas as pd
import re
import random
from datasets import load_dataset

def clean_price(price_str):
    """Extract numeric price from string"""
    if not price_str or pd.isna(price_str):
        return None
    
    # Remove currency symbols and extract first number
    match = re.search(r'[\d,]+\.?\d*', str(price_str))
    if match:
        price = match.group().replace(',', '')
        try:
            return float(price)
        except:
            return None
    return None

def extract_brand(text):
    """Try to extract brand from text"""
    if not text or pd.isna(text):
        return "Generic"
    
    # Common brand patterns
    text_str = str(text)
    words = text_str.split()
    if len(words) > 0:
        # Take first word as brand (often the brand name)
        brand = words[0].strip('.,;:-')
        if len(brand) > 2:
            return brand
    return "Generic"

def generate_rating():
    """Generate realistic ratings (skewed toward 4-5 stars)"""
    weights = [0.05, 0.1, 0.15, 0.35, 0.35]  # More 4s and 5s
    return round(random.choices([1.0, 2.0, 3.0, 4.0, 5.0], weights=weights)[0] + random.uniform(0, 0.9), 1)

def generate_review_count(rating):
    """Generate review count based on rating"""
    # Higher rated products tend to have more reviews
    base = random.randint(10, 1000)
    multiplier = rating / 5.0
    return int(base * multiplier)

def clean_text(text):
    """Clean text fields"""
    if not text or pd.isna(text):
        return ""
    text_str = str(text).strip()
    # Remove excessive whitespace
    text_str = ' '.join(text_str.split())
    return text_str[:500]  # Limit length

def simplify_category(category):
    """Simplify category to main category"""
    if not category or pd.isna(category):
        return "General"
    
    cat_str = str(category)
    # Take first category if multiple
    if '|' in cat_str:
        return cat_str.split('|')[0].strip()
    if '>' in cat_str:
        return cat_str.split('>')[0].strip()
    return cat_str.strip()[:50]

def download_and_prepare(output_file='../data/test_datasets/amazon_products.csv', max_products=200):
    """Download and prepare Amazon dataset"""
    
    print("📥 Downloading Amazon Products dataset from HuggingFace...")
    print("This may take a few minutes...")
    
    try:
        # Load dataset (train split has 24k products)
        dataset = load_dataset("ckandemir/amazon-products", split="train", revision="main")  # nosec B615
        
        print(f"✅ Downloaded {len(dataset)} products")
        print("🔄 Converting to DataFrame...")
        
        # Convert to pandas DataFrame
        df = pd.DataFrame(dataset)
        
        print(f"📊 Columns: {df.columns.tolist()}")
        
        # Map columns to our schema
        products = []
        
        print(f"🔄 Processing products (taking first {max_products})...")
        
        for idx, row in df.head(max_products).iterrows():
            # Extract and clean data
            name = clean_text(row.get('Product Name', ''))
            if not name or len(name) < 3:
                continue
                
            description = clean_text(row.get('Description', ''))
            category = simplify_category(row.get('Category', ''))
            price = clean_price(row.get('Selling Price', ''))
            
            # Skip if no valid price
            if not price or price <= 0 or price > 10000:
                continue
            
            image_url = row.get('Image', '')
            if not image_url or pd.isna(image_url):
                # Use placeholder
                image_url = f"https://via.placeholder.com/400x400/3b82f6/ffffff?text=Product"
            else:
                image_url = str(image_url).strip()
            
            # Extract or generate additional fields
            brand = extract_brand(name)
            rating = generate_rating()
            review_count = generate_review_count(rating)
            
            product = {
                'id': f'amz_{idx:05d}',
                'name': name,
                'description': description if description else name,
                'category': category,
                'price': round(price, 2),
                'rating': rating,
                'review_count': review_count,
                'image_url': image_url,
                'brand': brand
            }
            
            products.append(product)
            
            if (idx + 1) % 50 == 0:
                print(f"  Processed {idx + 1}/{max_products}...")
        
        # Create DataFrame and save
        products_df = pd.DataFrame(products)
        products_df.to_csv(output_file, index=False)
        
        # Print statistics
        print(f"\n✅ Successfully prepared {len(products_df)} products!")
        print(f"📁 Saved to: {output_file}")
        print(f"\n📊 Statistics:")
        print(f"  Categories: {products_df['category'].nunique()}")
        print(f"  Price range: ${products_df['price'].min():.2f} - ${products_df['price'].max():.2f}")
        print(f"  Avg price: ${products_df['price'].mean():.2f}")
        print(f"  Rating range: {products_df['rating'].min():.1f} - {products_df['rating'].max():.1f}")
        print(f"\n🏷️ Top 10 Categories:")
        print(products_df['category'].value_counts().head(10))
        
        return products_df
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"Make sure you have the required packages:")
        print(f"  pip install datasets pandas")
        raise

if __name__ == "__main__":
    # Download 200 products for testing (you can increase this)
    download_and_prepare(max_products=200)

