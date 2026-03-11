"""
Generate a realistic e-commerce product dataset with images
"""
import csv
import random

# Product templates organized by category
PRODUCTS = {
    "Electronics": [
        {"name": "Wireless Bluetooth Headphones", "desc": "Premium noise-canceling headphones with 30-hour battery", "price_range": (49.99, 199.99), "brand": "SoundTech"},
        {"name": "Smartphone 5G", "desc": "Latest 5G smartphone with 6.5\" display and triple camera", "price_range": (399.99, 1299.99), "brand": "TechPro"},
        {"name": "Laptop 15.6 inch", "desc": "Powerful laptop with Intel i7, 16GB RAM, 512GB SSD", "price_range": (699.99, 1899.99), "brand": "CompuMax"},
        {"name": "Wireless Mouse", "desc": "Ergonomic wireless mouse with adjustable DPI", "price_range": (19.99, 79.99), "brand": "TechMouse"},
        {"name": "Mechanical Keyboard", "desc": "RGB backlit mechanical gaming keyboard", "price_range": (59.99, 199.99), "brand": "KeyMaster"},
        {"name": "USB-C Hub", "desc": "7-in-1 USB-C hub with HDMI, USB 3.0, SD card reader", "price_range": (29.99, 89.99), "brand": "ConnectPro"},
        {"name": "Wireless Earbuds", "desc": "True wireless earbuds with active noise cancellation", "price_range": (49.99, 299.99), "brand": "AudioMax"},
        {"name": "Smart Watch", "desc": "Fitness tracker smart watch with heart rate monitor", "price_range": (99.99, 499.99), "brand": "FitWatch"},
        {"name": "Portable Charger", "desc": "20000mAh power bank with fast charging", "price_range": (24.99, 79.99), "brand": "PowerBoost"},
        {"name": "Webcam HD", "desc": "1080p HD webcam with built-in microphone", "price_range": (39.99, 149.99), "brand": "CamPro"},
        {"name": "External SSD", "desc": "1TB portable external SSD with USB 3.2", "price_range": (89.99, 299.99), "brand": "StorageMax"},
        {"name": "Monitor 27 inch", "desc": "4K UHD monitor with HDR and 144Hz refresh rate", "price_range": (299.99, 799.99), "brand": "ViewPro"},
        {"name": "Laptop Backpack", "desc": "Water-resistant laptop backpack with USB charging port", "price_range": (29.99, 89.99), "brand": "TechPack"},
        {"name": "Wireless Charger", "desc": "Fast wireless charging pad for smartphones", "price_range": (19.99, 59.99), "brand": "ChargeFast"},
        {"name": "Bluetooth Speaker", "desc": "Portable waterproof Bluetooth speaker", "price_range": (39.99, 199.99), "brand": "SoundWave"},
    ],
    "Home & Kitchen": [
        {"name": "Coffee Maker", "desc": "Programmable drip coffee maker with thermal carafe", "price_range": (39.99, 199.99), "brand": "BrewMaster"},
        {"name": "Blender", "desc": "High-speed blender with multiple settings", "price_range": (49.99, 299.99), "brand": "BlendPro"},
        {"name": "Air Fryer", "desc": "6-quart digital air fryer with preset functions", "price_range": (59.99, 199.99), "brand": "CrispyChef"},
        {"name": "Knife Set", "desc": "Professional 15-piece stainless steel knife set", "price_range": (79.99, 299.99), "brand": "ChefPro"},
        {"name": "Vacuum Cleaner", "desc": "Cordless stick vacuum with HEPA filter", "price_range": (149.99, 599.99), "brand": "CleanMaster"},
        {"name": "Water Bottle", "desc": "Insulated stainless steel water bottle", "price_range": (19.99, 49.99), "brand": "HydroFlask"},
        {"name": "Cookware Set", "desc": "Non-stick 10-piece cookware set", "price_range": (99.99, 399.99), "brand": "CookPro"},
        {"name": "Food Processor", "desc": "12-cup food processor with multiple blades", "price_range": (79.99, 299.99), "brand": "ChopMaster"},
        {"name": "Toaster Oven", "desc": "6-slice convection toaster oven", "price_range": (49.99, 199.99), "brand": "ToastPro"},
        {"name": "Electric Kettle", "desc": "1.7L electric kettle with temperature control", "price_range": (29.99, 99.99), "brand": "BoilFast"},
        {"name": "Mixer Stand", "desc": "6-speed stand mixer with stainless steel bowl", "price_range": (149.99, 499.99), "brand": "MixMaster"},
        {"name": "Cutting Board Set", "desc": "Bamboo cutting board set of 3", "price_range": (24.99, 79.99), "brand": "ChopBoard"},
        {"name": "Storage Containers", "desc": "Glass food storage containers set of 10", "price_range": (29.99, 89.99), "brand": "StoreFresh"},
        {"name": "Dish Rack", "desc": "Stainless steel dish drying rack", "price_range": (24.99, 79.99), "brand": "DryWell"},
    ],
    "Sports & Outdoors": [
        {"name": "Yoga Mat", "desc": "Extra thick 6mm yoga mat with carrying strap", "price_range": (19.99, 79.99), "brand": "FitLife"},
        {"name": "Resistance Bands", "desc": "5-piece resistance band set for home workouts", "price_range": (14.99, 49.99), "brand": "FitGear"},
        {"name": "Dumbbells Set", "desc": "Adjustable dumbbell set 5-50 lbs", "price_range": (99.99, 399.99), "brand": "IronFit"},
        {"name": "Jump Rope", "desc": "Speed jump rope with adjustable length", "price_range": (9.99, 29.99), "brand": "FitJump"},
        {"name": "Camping Tent", "desc": "4-person waterproof camping tent", "price_range": (79.99, 299.99), "brand": "OutdoorPro"},
        {"name": "Sleeping Bag", "desc": "Lightweight sleeping bag for camping", "price_range": (39.99, 149.99), "brand": "SleepWell"},
        {"name": "Hiking Backpack", "desc": "50L hiking backpack with rain cover", "price_range": (59.99, 199.99), "brand": "TrailMaster"},
        {"name": "Water Filter", "desc": "Portable water filter for camping", "price_range": (24.99, 79.99), "brand": "PureWater"},
        {"name": "Bike Helmet", "desc": "Adjustable bike helmet with LED light", "price_range": (29.99, 99.99), "brand": "SafeRide"},
        {"name": "Tennis Racket", "desc": "Professional tennis racket with case", "price_range": (49.99, 249.99), "brand": "GamePro"},
        {"name": "Soccer Ball", "desc": "Official size 5 soccer ball", "price_range": (19.99, 59.99), "brand": "KickMaster"},
        {"name": "Swim Goggles", "desc": "Anti-fog swim goggles with UV protection", "price_range": (14.99, 49.99), "brand": "SwimPro"},
    ],
    "Clothing & Shoes": [
        {"name": "Running Shoes", "desc": "Lightweight breathable running shoes", "price_range": (59.99, 179.99), "brand": "RunFast"},
        {"name": "Athletic Shorts", "desc": "Quick-dry athletic shorts with pockets", "price_range": (19.99, 49.99), "brand": "FitWear"},
        {"name": "T-Shirt Pack", "desc": "Pack of 3 performance t-shirts", "price_range": (24.99, 79.99), "brand": "ComfortFit"},
        {"name": "Hoodie", "desc": "Fleece pullover hoodie with pockets", "price_range": (29.99, 89.99), "brand": "CozyWear"},
        {"name": "Jeans", "desc": "Slim fit stretch denim jeans", "price_range": (39.99, 129.99), "brand": "DenimPro"},
        {"name": "Sneakers", "desc": "Casual sneakers with memory foam insole", "price_range": (49.99, 149.99), "brand": "StepComfort"},
        {"name": "Winter Jacket", "desc": "Waterproof winter jacket with hood", "price_range": (79.99, 299.99), "brand": "WarmGuard"},
        {"name": "Baseball Cap", "desc": "Adjustable baseball cap with logo", "price_range": (14.99, 39.99), "brand": "CapPro"},
        {"name": "Socks Pack", "desc": "Pack of 6 athletic socks", "price_range": (14.99, 34.99), "brand": "ComfortSocks"},
        {"name": "Backpack", "desc": "School/work backpack with laptop compartment", "price_range": (29.99, 99.99), "brand": "PackPro"},
    ],
    "Books & Media": [
        {"name": "Fiction Novel", "desc": "Bestselling fiction novel paperback", "price_range": (9.99, 29.99), "brand": "ReadWell"},
        {"name": "Self-Help Book", "desc": "Personal development and productivity book", "price_range": (12.99, 34.99), "brand": "GrowMind"},
        {"name": "Cookbook", "desc": "Healthy cooking recipes cookbook", "price_range": (14.99, 39.99), "brand": "ChefBook"},
        {"name": "Journal", "desc": "Leather-bound journal with lined pages", "price_range": (12.99, 39.99), "brand": "WriteWell"},
        {"name": "Coloring Book", "desc": "Adult coloring book for relaxation", "price_range": (9.99, 24.99), "brand": "ColorJoy"},
        {"name": "Board Game", "desc": "Family board game for 2-6 players", "price_range": (19.99, 79.99), "brand": "GameNight"},
        {"name": "Puzzle 1000pc", "desc": "1000-piece jigsaw puzzle", "price_range": (14.99, 39.99), "brand": "PuzzleMaster"},
    ],
    "Beauty & Personal Care": [
        {"name": "Electric Toothbrush", "desc": "Rechargeable electric toothbrush with timer", "price_range": (29.99, 149.99), "brand": "SmilePro"},
        {"name": "Hair Dryer", "desc": "Ionic hair dryer with diffuser", "price_range": (39.99, 149.99), "brand": "StylePro"},
        {"name": "Moisturizer", "desc": "Daily facial moisturizer with SPF", "price_range": (14.99, 49.99), "brand": "GlowCare"},
        {"name": "Shampoo Set", "desc": "Shampoo and conditioner set", "price_range": (19.99, 59.99), "brand": "HairCare"},
        {"name": "Perfume", "desc": "Luxury eau de parfum spray", "price_range": (39.99, 199.99), "brand": "Essence"},
        {"name": "Makeup Brush Set", "desc": "Professional makeup brush set of 12", "price_range": (24.99, 89.99), "brand": "BeautyPro"},
        {"name": "Face Mask Set", "desc": "Variety pack of sheet face masks", "price_range": (14.99, 39.99), "brand": "SkinCare"},
        {"name": "Electric Shaver", "desc": "Cordless electric shaver for men", "price_range": (49.99, 199.99), "brand": "ShaveMaster"},
    ],
    "Toys & Games": [
        {"name": "Building Blocks", "desc": "Creative building blocks set 500 pieces", "price_range": (29.99, 99.99), "brand": "BuildIt"},
        {"name": "RC Car", "desc": "Remote control racing car with rechargeable battery", "price_range": (39.99, 149.99), "brand": "SpeedRacer"},
        {"name": "Doll House", "desc": "Wooden doll house with furniture", "price_range": (49.99, 199.99), "brand": "PlayHome"},
        {"name": "Action Figure", "desc": "Collectible action figure with accessories", "price_range": (14.99, 49.99), "brand": "HeroToys"},
        {"name": "Art Supplies", "desc": "Complete art supplies set for kids", "price_range": (24.99, 79.99), "brand": "ArtKids"},
        {"name": "Science Kit", "desc": "Educational science experiment kit", "price_range": (29.99, 89.99), "brand": "LearnScience"},
    ]
}

# Placeholder image service (using placeholder.com for realistic URLs)
def get_image_url(product_index, category):
    """Generate placeholder image URL"""
    colors = ["3498db", "e74c3c", "2ecc71", "f39c12", "9b59b6", "1abc9c"]
    color = colors[product_index % len(colors)]
    cat_short = category.replace(" & ", "-").replace(" ", "-").lower()
    return f"https://via.placeholder.com/400x400/{color}/ffffff?text={cat_short}"

def generate_dataset(output_file, num_products_per_category=10):
    """Generate e-commerce dataset"""
    products = []
    product_id = 1
    
    for category, product_templates in PRODUCTS.items():
        for i in range(num_products_per_category):
            # Select a product template and create variation
            template = product_templates[i % len(product_templates)]
            
            # Add variation to name if repeating
            variation_suffix = ""
            if i >= len(product_templates):
                variations = ["Pro", "Plus", "Max", "Ultra", "Premium", "Deluxe", "Elite"]
                variation_suffix = f" {variations[i % len(variations)]}"
            
            # Generate price within range
            price = round(random.uniform(*template["price_range"]), 2)
            
            # Generate rating (skewed toward 4-5 stars)
            rating = round(random.uniform(3.5, 5.0), 1)
            
            # Generate review count (higher rated products have more reviews)
            review_count = int(random.uniform(50, 2000) * (rating / 5.0))
            
            product = {
                "id": f"prod_{product_id:03d}",
                "name": template["name"] + variation_suffix,
                "description": template["desc"],
                "category": category,
                "price": price,
                "rating": rating,
                "review_count": review_count,
                "image_url": get_image_url(product_id, category),
                "brand": template["brand"]
            }
            
            products.append(product)
            product_id += 1
    
    # Write to CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'name', 'description', 'category', 'price', 'rating', 'review_count', 'image_url', 'brand'])
        writer.writeheader()
        writer.writerows(products)
    
    print(f"✅ Generated {len(products)} products across {len(PRODUCTS)} categories")
    print(f"📁 Saved to: {output_file}")
    print(f"💰 Price range: ${min(p['price'] for p in products):.2f} - ${max(p['price'] for p in products):.2f}")
    print(f"⭐ Rating range: {min(p['rating'] for p in products):.1f} - {max(p['rating'] for p in products):.1f}")
    print(f"📦 Categories: {', '.join(PRODUCTS.keys())}")

if __name__ == "__main__":
    output_file = "../data/test_datasets/ecommerce_products.csv"
    generate_dataset(output_file, num_products_per_category=10)

