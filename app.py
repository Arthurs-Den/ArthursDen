from flask import Flask, request, session, redirect, jsonify, render_template
import os
import secrets
import requests
import json
from datetime import datetime
import hashlib
import uuid
from utils import (
    validate_username, validate_email, validate_password,
    sanitize_text_input, validate_search_terms, validate_shop_names,
    format_currency, safe_int, safe_float, truncate_text, is_safe_url
)
import logging
import time
from functools import wraps

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)

# Legacy admin credentials for backward compatibility
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# Etsy API Configuration
ETSY_API_KEY = os.environ.get('ETSY_API_KEY', 'your-etsy-api-key')
ETSY_BASE_URL = 'https://openapi.etsy.com/v3'

# Simple in-memory user storage (keeps existing functionality)
USERS_DB = {
    'admin': {
        'password_hash': hashlib.sha256('admin123'.encode()).hexdigest(),
        'role': 'admin',
        'name': 'Administrator',
        'email': 'admin@arthursden.com',
        'created': datetime.now().isoformat(),
        'search_terms': [
            "nursery wall art uk",
            "personalised baby gifts",
            "custom name sign uk",
            "wooden name plaque",
            "baby room decor uk"
        ],
        'watchlist_shops': [],
        'settings': {
            'notifications': True,
            'auto_refresh': True,
            'export_format': 'csv'
        }
    }
}

# Rate limiting decorator
def rate_limit(max_requests=10, window=60):
    """Simple rate limiting decorator"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Simple in-memory rate limiting (use Redis in production)
            client_id = request.remote_addr
            current_time = time.time()
            
            if not hasattr(wrapper, 'requests'):
                wrapper.requests = {}
            
            if client_id not in wrapper.requests:
                wrapper.requests[client_id] = []
            
            # Clean old requests
            wrapper.requests[client_id] = [
                req_time for req_time in wrapper.requests[client_id]
                if current_time - req_time < window
            ]
            
            if len(wrapper.requests[client_id]) >= max_requests:
                logger.warning(f"Rate limit exceeded for {client_id}")
                return jsonify({'error': 'Rate limit exceeded'}), 429
            
            wrapper.requests[client_id].append(current_time)
            return f(*args, **kwargs)
        return wrapper
    return decorator

# API logging decorator
def log_api_call(f):
    """Log API calls for monitoring"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        user_id = session.get('username')
        
        try:
            result = f(*args, **kwargs)
            response_time = time.time() - start_time
            status_code = 200 if hasattr(result, 'status_code') else 200
            
            db.log_api_call(
                endpoint=request.endpoint,
                user_id=user_id,
                status_code=status_code,
                response_time=response_time
            )
            
            return result
        except Exception as e:
            response_time = time.time() - start_time
            db.log_api_call(
                endpoint=request.endpoint,
                user_id=user_id,
                status_code=500,
                response_time=response_time,
                error_message=str(e)
            )
            logger.error(f"API error in {request.endpoint}: {e}")
            raise
    return wrapper

def hash_password(password):
    """Hash password for secure storage"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hash_password):
    """Verify password against hash"""
    return hashlib.sha256(password.encode()).hexdigest() == hash_password

def create_user(username, password, name, email, role='user'):
    """Create new user account"""
    if username in USERS_DB:
        return False, "Username already exists"
    
    USERS_DB[username] = {
        'password_hash': hash_password(password),
        'role': role,
        'name': name,
        'email': email,
        'created': datetime.now().isoformat(),
        'search_terms': [
            "nursery wall art uk",
            "personalised baby gifts",
            "custom name sign uk",
            "wooden name plaque",
            "baby room decor uk"
        ],
        'watchlist_shops': [],
        'settings': {
            'notifications': True,
            'auto_refresh': True,
            'export_format': 'csv'
        }
    }
    return True, "User created successfully"

def get_user_data(username):
    """Get user data from database"""
    return USERS_DB.get(username, {})

def fetch_etsy_listings(keywords, limit=20):
    """Fetch real-time listings from Etsy API with comprehensive seller data"""
    # Validate and sanitize input
    if not keywords or not isinstance(keywords, str):
        logger.warning("Invalid keywords provided to fetch_etsy_listings")
        return None
    
    clean_keywords = sanitize_text_input(keywords, max_length=200)
    safe_limit = safe_int(limit, default=20)
    safe_limit = min(max(safe_limit, 1), 100)  # Clamp between 1-100
    
    try:
        # Skip API call if no valid API key (for demo mode)
        if not ETSY_API_KEY or ETSY_API_KEY == 'your-etsy-api-key':
            logger.info(f"Using demo mode for keywords: {clean_keywords}")
            return None  # This will trigger demo data
        
        headers = {
            'x-api-key': ETSY_API_KEY,
            'Authorization': f'Bearer {ETSY_API_KEY}'
        }
        
        params = {
            'keywords': clean_keywords,
            'limit': safe_limit,
            'includes': 'Images,Shop,User,Translations',
            'sort_on': 'created',
            'sort_order': 'desc'
        }
        
        logger.info(f"Fetching Etsy data for: {clean_keywords}")
        
        response = requests.get(
            f'{ETSY_BASE_URL}/application/listings/active',
            headers=headers,
            params=params,
            timeout=15
        )
        
        logger.info(f"Etsy API response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            result_count = len(data.get('results', []))
            logger.info(f"Successfully fetched {result_count} listings")
            return data
        elif response.status_code == 429:
            logger.warning("Etsy API rate limit exceeded, using demo data")
            return None
        elif response.status_code == 401:
            logger.error("Etsy API authentication failed, check API key")
            return None
        else:
            logger.error(f"Etsy API Error: {response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        logger.warning("Etsy API timeout, using demo data")
        return None
    except requests.exceptions.ConnectionError:
        logger.warning("Etsy API connection error, using demo data")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching Etsy data: {e}")
        return None

def process_etsy_data(listings_data, search_term):
    """Process Etsy API response with comprehensive seller intelligence"""
    if not listings_data or 'results' not in listings_data:
        return []
    
    processed_products = []
    
    for i, listing in enumerate(listings_data['results'][:10]):  # Top 10 results
        try:
            # Basic product data
            price = float(listing.get('price', {}).get('amount', 0)) / 100
            views = listing.get('views', 0)
            favorites = listing.get('num_favorers', 0)
            
            # Enhanced shop/seller data
            shop_data = listing.get('Shop', {})
            user_data = listing.get('User', {})
            images = listing.get('Images', [])
            
            # Extract comprehensive seller profile with UK preference
            seller_profile = {
                'shop_name': shop_data.get('shop_name', 'Unknown Shop'),
                'shop_id': shop_data.get('shop_id', ''),
                'shop_url': f"https://etsy.com/uk/shop/{shop_data.get('shop_name', '')}" if shop_data.get('shop_name') else '',
                'seller_location': shop_data.get('country_name', 'Unknown'),
                'shop_created': shop_data.get('create_date', ''),
                'total_sales': shop_data.get('total_sales', 0),
                'digital_sales': shop_data.get('digital_sales', 0),
                'shop_policy': shop_data.get('policy_welcome', ''),
                'seller_avatar': user_data.get('avatar_url_fullxfull', ''),
                'seller_bio': user_data.get('bio', ''),
                'is_vacation': shop_data.get('is_vacation', False),
                'vacation_message': shop_data.get('vacation_message', ''),
                'announcement': shop_data.get('announcement', ''),
                'shop_languages': shop_data.get('languages', []),
                'currency_code': shop_data.get('currency_code', 'GBP'),  # Default to GBP for UK
                'is_uk_seller': shop_data.get('country_name', '').lower() in ['united kingdom', 'uk', 'great britain', 'england', 'scotland', 'wales']
            }
            
            # Product images for visual analysis
            product_images = []
            for img in images[:3]:  # Get first 3 images
                product_images.append({
                    'thumbnail': img.get('url_170x135', ''),
                    'small': img.get('url_340x270', ''),
                    'medium': img.get('url_570xN', ''),
                    'large': img.get('url_fullxfull', '')
                })
            
            # Advanced metrics calculations
            estimated_weekly_sales = max(1, int((views * 0.02) + (favorites * 0.1)))
            estimated_revenue = estimated_weekly_sales * price * 4
            
            # Enhanced priority scoring
            shop_score = min(100, (seller_profile['total_sales'] or 0) / 100)
            engagement_score = min(100, (views + favorites * 2) / 50)
            priority_score = (shop_score + engagement_score) / 2
            
            if priority_score > 70:
                priority = "Critical"
                trend = "Hot"
            elif priority_score > 40:
                priority = "High" 
                trend = "Trending"
            else:
                priority = "Medium"
                trend = "Stable"
            
            product = {
                "id": i + 1,
                "listing_id": listing.get('listing_id', ''),
                "title": listing.get('title', 'Unknown Product'),
                "description": listing.get('description', '')[:200] + "..." if listing.get('description') else '',
                "price": price,
                "currency": seller_profile['currency_code'],
                "views": views,
                "favorites": favorites,
                "weekly_sales": estimated_weekly_sales,
                "revenue": int(estimated_revenue),
                "sales_trend": f"+{min(50, max(5, int(views/100)))}%",
                "market_trend": trend,
                "priority": priority,
                "priority_score": round(priority_score, 1),
                "etsy_url": listing.get('url', ''),
                "search_term": search_term,
                "tags": listing.get('tags', []),
                "materials": listing.get('materials', []),
                "category_path": listing.get('taxonomy_path', []),
                "created_date": listing.get('creation_date', ''),
                "last_modified": listing.get('last_modified_date', ''),
                "seller_profile": seller_profile,
                "product_images": product_images,
                "processing_time": listing.get('processing_min', 0),
                "shipping_profile": listing.get('shipping_profile', {}),
                "quantity": listing.get('quantity', 0),
                "state": listing.get('state', 'active')
            }
            
            processed_products.append(product)
            
        except Exception as e:
            print(f"Error processing listing: {e}")
            continue
    
    return processed_products

@app.route('/')
def home():
    if not session.get('authenticated'):
        return redirect('/login')
    return render_template('dashboard.html', 
                         username=session.get('user_name', session.get('username', 'Admin')),
                         user_role=session.get('user_role', 'user'))

@app.route('/api/market-data')
@rate_limit(max_requests=20, window=60)
@log_api_call
def get_market_data():
    if not session.get('authenticated'):
        return jsonify({'error': 'Authentication required'}), 401
    
    # Get custom search terms from session or use UK-focused defaults
    search_terms = session.get('search_terms', [
        "nursery wall art uk",
        "personalised baby gifts uk", 
        "milestone baby blanket",
        "custom name sign uk",
        "baby shower decorations uk",
        "wooden name plaque",
        "children's bedroom decor",
        "bespoke baby gifts"
    ])
    
    # Get shops to watch from session
    watchlist_shops = session.get('watchlist_shops', [])
    
    all_products = []
    total_revenue = 0
    total_weekly_sales = 0
    critical_alerts = 0
    
    for term in search_terms:
        listings_data = fetch_etsy_listings(term, limit=5)  # Get 5 per category
        if listings_data:
            products = process_etsy_data(listings_data, term)
            
            # Filter by watchlist shops if specified
            if watchlist_shops:
                filtered_products = []
                for product in products:
                    if any(shop.lower() in product['shop'].lower() for shop in watchlist_shops):
                        product['watchlist_match'] = True
                        filtered_products.append(product)
                products = filtered_products
            
            all_products.extend(products)
            
            # Calculate totals
            for product in products:
                total_revenue += product['revenue']
                total_weekly_sales += product['weekly_sales']
                if product['priority'] == 'Critical':
                    critical_alerts += 1
    
    # If API fails, use realistic UK-focused demo data showing what you'll get when approved
    if not all_products:
        all_products = [
            {
                "id": 1, "title": "Personalised Baby Milestone Blanket - Monthly...",
                "shop": "BabyMilestoneUK", "price": 34.99, "currency": "GBP", "views": 1850, "favorites": 127,
                "weekly_sales": 23, "revenue": 3218, "sales_trend": "+18%",
                "market_trend": "Hot", "priority": "Critical", 
                "etsy_url": "https://etsy.com/uk/listing/example1",
                "search_term": "milestone baby blanket",
                "seller_profile": {"shop_name": "BabyMilestoneUK", "seller_location": "United Kingdom", "is_uk_seller": True, "currency_code": "GBP"}
            },
            {
                "id": 2, "title": "Custom Nursery Name Sign - Wooden Laser Cut...",
                "shop": "WoodCraftStudioUK", "price": 29.50, "currency": "GBP", "views": 2140, "favorites": 89,
                "weekly_sales": 31, "revenue": 3658, "sales_trend": "+25%",
                "market_trend": "Trending", "priority": "High",
                "etsy_url": "https://etsy.com/uk/listing/example2", 
                "search_term": "custom name sign uk",
                "seller_profile": {"shop_name": "WoodCraftStudioUK", "seller_location": "England", "is_uk_seller": True, "currency_code": "GBP"}
            },
            {
                "id": 3, "title": "Baby Shower Decorations Set - Gender Neutral...",
                "shop": "PartyPerfectUK", "price": 22.99, "currency": "GBP", "views": 1230, "favorites": 67,
                "weekly_sales": 19, "revenue": 1747, "sales_trend": "+12%",
                "market_trend": "Stable", "priority": "Medium",
                "etsy_url": "https://etsy.com/uk/listing/example3",
                "search_term": "baby shower decorations uk",
                "seller_profile": {"shop_name": "PartyPerfectUK", "seller_location": "Scotland", "is_uk_seller": True, "currency_code": "GBP"}
            },
            {
                "id": 4, "title": "Nursery Wall Art Print Set - Safari Animals...",
                "shop": "ModernNurseryArtUK", "price": 12.99, "currency": "GBP", "views": 3450, "favorites": 234,
                "weekly_sales": 45, "revenue": 2338, "sales_trend": "+35%",
                "market_trend": "Hot", "priority": "Critical",
                "etsy_url": "https://etsy.com/uk/listing/example4",
                "search_term": "nursery wall art uk",
                "seller_profile": {"shop_name": "ModernNurseryArtUK", "seller_location": "Wales", "is_uk_seller": True, "currency_code": "GBP"}
            },
            {
                "id": 5, "title": "Bespoke Baby Gift Set - Personalised Bundle...",
                "shop": "BespokeBabyGiftsUK", "price": 52.50, "currency": "GBP", "views": 890, "favorites": 45,
                "weekly_sales": 12, "revenue": 2520, "sales_trend": "+8%",
                "market_trend": "Emerging", "priority": "Medium",
                "etsy_url": "https://etsy.com/uk/listing/example5",
                "search_term": "bespoke baby gifts",
                "seller_profile": {"shop_name": "BespokeBabyGiftsUK", "seller_location": "United Kingdom", "is_uk_seller": True, "currency_code": "GBP"}
            }
        ]
        total_revenue = sum(p['revenue'] for p in all_products)
        total_weekly_sales = sum(p['weekly_sales'] for p in all_products)
        critical_alerts = len([p for p in all_products if p['priority'] == 'Critical'])
    
    # Calculate averages
    avg_weekly_sales = round(total_weekly_sales / len(all_products), 1) if all_products else 0
    
    # Generate insights from real data
    top_products = sorted(all_products, key=lambda x: x['revenue'], reverse=True)[:3]
    
    opportunities = []
    alerts = []
    
    for product in top_products:
        if product['priority'] == 'Critical':
            opportunities.append({
                "niche": product['search_term'].title(),
                "growth": product['sales_trend'],
                "revenue_potential": f"${product['revenue']:,}/month",
                "action": f"Target {product['search_term']} niche - High demand detected",
                "urgency": "Critical"
            })
            
            alerts.append({
                "type": "High Opportunity",
                "message": f"{product['title']} showing strong performance in {product['search_term']}",
                "action": f"Analyze {product['shop']} strategy and create competing product",
                "revenue_impact": f"${product['revenue']:,}/month potential",
                "etsy_url": product['etsy_url']
            })
    
    market_data = {
        "products": all_products,
        "insights": {
            "market_summary": {
                "total_revenue": f"${total_revenue:,}",
                "avg_weekly_sales": str(avg_weekly_sales),
                "top_opportunity": top_products[0]['search_term'].title() if top_products else "No data",
                "critical_alerts": critical_alerts,
                "market_health": "Excellent" if critical_alerts > 0 else "Good",
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
            },
            "opportunities": opportunities,
            "alerts": alerts
        }
    }
    
    return jsonify(market_data)

@app.route('/api/export')
def export_data():
    if not session.get('authenticated'):
        return jsonify({'error': 'Authentication required'}), 401
    
    # Get current market data for export
    market_response = get_market_data()
    market_data = market_response.get_json()
    
    import io
    from flask import Response
    
    output = io.StringIO()
    output.write("Product,Shop,Price,Views,Favorites,Weekly Sales,Revenue,Priority,Trend,Search Term,Etsy URL\n")
    
    for product in market_data['products']:
        currency_symbol = '£' if product.get('currency', 'GBP') == 'GBP' else '$'
        output.write(f'"{product["title"]}","{product["shop"]}",{currency_symbol}{product["price"]:.2f},{product["views"]},{product["favorites"]},{product["weekly_sales"]},{currency_symbol}{product["revenue"]},{product["priority"]},{product["market_trend"]},"{product["search_term"]}","{product.get("etsy_url", "")}"\n')
    
    output.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=arthursden_realtime_data_{timestamp}.csv'}
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    
    # Handle login submission
    if request.is_json:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
    else:
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
    
    # Check multi-user database first
    if username in USERS_DB:
        user_data = USERS_DB[username]
        if verify_password(password, user_data['password_hash']):
            session['authenticated'] = True
            session['username'] = username
            session['user_role'] = user_data['role']
            session['user_name'] = user_data['name']
            # Load user's personal settings
            session['search_terms'] = user_data.get('search_terms', [])
            session['watchlist_shops'] = user_data.get('watchlist_shops', [])
            logger.info(f"User {username} logged in successfully")
            return jsonify({'success': True, 'message': 'Login successful', 'redirect': '/'})
    
    # Fallback to legacy admin credentials
    elif username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session['authenticated'] = True
        session['username'] = username
        session['user_role'] = 'admin'
        session['user_name'] = 'Administrator'
        return jsonify({'success': True, 'message': 'Login successful', 'redirect': '/'})
    
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/settings')
def settings():
    if not session.get('authenticated'):
        return redirect('/login')
    
    username = session.get('username')
    user_data = get_user_data(username)
    
    return render_template('settings.html', 
                         username=session.get('user_name', username),
                         user_role=session.get('user_role', 'user'),
                         search_terms=session.get('search_terms', []),
                         watchlist_shops=session.get('watchlist_shops', []),
                         user_settings=user_data.get('settings', {}))

@app.route('/users')
def user_management():
    if not session.get('authenticated') or session.get('user_role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    
    return render_template('users.html', 
                         username=session.get('user_name', 'Admin'),
                         users=USERS_DB)

@app.route('/api/create-user', methods=['POST'])
def api_create_user():
    if not session.get('authenticated') or session.get('user_role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON data'}), 400
        
        username = sanitize_text_input(data.get('username', '').strip(), max_length=50)
        password = data.get('password', '')
        name = sanitize_text_input(data.get('name', '').strip(), max_length=100)
        email = sanitize_text_input(data.get('email', '').strip(), max_length=254)
        role = data.get('role', 'user')
        
        # Validate role
        if role not in ['user', 'admin']:
            return jsonify({'error': 'Invalid role. Must be "user" or "admin"'}), 400
        
        # Validate username
        valid_username, username_msg = validate_username(username)
        if not valid_username:
            return jsonify({'error': username_msg}), 400
        
        # Validate password
        valid_password, password_msg = validate_password(password)
        if not valid_password:
            return jsonify({'error': password_msg}), 400
        
        # Validate name
        if not name or len(name) < 2:
            return jsonify({'error': 'Name must be at least 2 characters'}), 400
        
        # Validate email if provided
        if email:
            valid_email, email_msg = validate_email(email)
            if not valid_email:
                return jsonify({'error': email_msg}), 400
        
        success, message = create_user(username, password, name, email, role)
        if success:
            logger.info(f"User {username} created by admin {session.get('username')}")
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 400
            
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return jsonify({'error': 'Failed to create user. Please try again.'}), 500

@app.route('/api/delete-user', methods=['POST'])
def api_delete_user():
    if not session.get('authenticated') or session.get('user_role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    
    data = request.get_json()
    username = data.get('username', '').strip()
    
    if username == 'admin':
        return jsonify({'error': 'Cannot delete admin user'}), 400
    
    if username in USERS_DB:
        del USERS_DB[username]
        logger.info(f"User {username} deleted by admin {session.get('username')}")
        return jsonify({'success': True, 'message': 'User deleted successfully'})
    else:
        return jsonify({'error': 'User not found'}), 404

@app.route('/api/update-search-terms', methods=['POST'])
def update_search_terms():
    if not session.get('authenticated'):
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON data'}), 400
        
        search_terms = data.get('search_terms', [])
        username = session.get('username')
        
        # Validate and clean search terms
        valid, message, clean_terms = validate_search_terms(search_terms)
        if not valid:
            return jsonify({'error': message}), 400
        
        session['search_terms'] = clean_terms
        
        # Save to user profile
        if username in USERS_DB:
            USERS_DB[username]['search_terms'] = clean_terms
        
        logger.info(f"Updated {len(clean_terms)} search terms for user {username}")
        
        return jsonify({
            'success': True, 
            'search_terms': clean_terms,
            'message': f'Updated {len(clean_terms)} search terms'
        })
        
    except Exception as e:
        logger.error(f"Error updating search terms: {e}")
        return jsonify({'error': 'Failed to update search terms. Please try again.'}), 500

@app.route('/api/update-watchlist', methods=['POST'])
def update_watchlist():
    if not session.get('authenticated'):
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON data'}), 400
        
        shops = data.get('shops', [])
        username = session.get('username')
        
        # Validate and clean shop names
        valid, message, clean_shops = validate_shop_names(shops)
        if not valid:
            return jsonify({'error': message}), 400
        
        session['watchlist_shops'] = clean_shops
        
        # Save to user profile
        if username in USERS_DB:
            USERS_DB[username]['watchlist_shops'] = clean_shops
        
        logger.info(f"Updated watchlist with {len(clean_shops)} shops for user {username}")
        
        return jsonify({
            'success': True, 
            'watchlist_shops': clean_shops,
            'message': f'Updated watchlist with {len(clean_shops)} shops'
        })
        
    except Exception as e:
        logger.error(f"Error updating watchlist: {e}")
        return jsonify({'error': 'Failed to update watchlist. Please try again.'}), 500

@app.route('/api/product-details/<listing_id>')
def get_product_details(listing_id):
    """Get detailed product information including seller profile and images"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Authentication required'}), 401
    
    # In a real implementation, this would fetch from your stored data
    # For now, return UK-focused demo detailed data
    detailed_product = {
        'listing_id': listing_id,
        'title': 'Custom Wooden Name Sign - Personalised Nursery Decor',
        'description': 'Beautiful handcrafted wooden name sign perfect for nursery decoration. Made from premium birch wood with smooth finish. Customisable colours and fonts available. Made in the UK with free UK delivery.',
        'price': 29.99,
        'currency': 'GBP',
        'views': 2450,
        'favorites': 127,
        'tags': ['nursery', 'wooden sign', 'personalised', 'baby decor', 'custom', 'uk made'],
        'materials': ['birch wood', 'acrylic paint', 'protective finish'],
        'seller_profile': {
            'shop_name': 'CustomWoodCraftsUK',
            'shop_url': 'https://etsy.com/uk/shop/CustomWoodCraftsUK',
            'seller_location': 'United Kingdom',
            'total_sales': 1247,
            'shop_created': '2020-03-15',
            'seller_avatar': 'https://i.etsystatic.com/avatar.jpg',
            'seller_bio': 'Passionate UK woodworker creating beautiful custom pieces for your home. All items handmade in our workshop in England.',
            'announcement': 'New autumn collection now available! Custom orders welcome. Free UK delivery on orders over £25.',
            'is_vacation': False,
            'is_uk_seller': True,
            'currency_code': 'GBP'
        },
        'product_images': [
            {
                'thumbnail': 'https://i.etsystatic.com/123/thumb.jpg',
                'small': 'https://i.etsystatic.com/123/small.jpg',
                'medium': 'https://i.etsystatic.com/123/medium.jpg',
                'large': 'https://i.etsystatic.com/123/large.jpg'
            }
        ],
        'processing_time': 3,
        'shipping_info': 'Ships within 3-5 business days. Free UK delivery.',
        'quantity': 15,
        'created_date': '2024-01-15T10:30:00Z',
        'priority_score': 85.2
    }
    
    return jsonify(detailed_product)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/health')
def health():
    try:
        # Test in-memory database
        test_user = USERS_DB.get('admin')
        db_status = 'healthy' if test_user else 'unhealthy'
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = 'unhealthy'
    
    return {
        'status': 'healthy' if db_status == 'healthy' else 'degraded',
        'app': 'ArthursDen',
        'database': db_status,
        'authenticated': session.get('authenticated', False)
    }

# Error handlers
@app.errorhandler(404)
def not_found(error):
    logger.warning(f"404 error: {request.url}")
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(429)
def rate_limit_error(error):
    logger.warning(f"Rate limit exceeded: {request.remote_addr}")
    return jsonify({'error': 'Rate limit exceeded. Please try again later.'}), 429

# Simple request counter (for future use)
@app.before_request
def before_request():
    if hasattr(before_request, 'request_counter'):
        before_request.request_counter += 1
    else:
        before_request.request_counter = 1

@app.route('/api/debug-etsy')
def debug_etsy():
    if not session.get('authenticated'):
        return jsonify({'error': 'Authentication required'}), 401
    
    # Test API connection (safe - won't break demo)
    start_time = time.time()
    test_data = fetch_etsy_listings("baby", 1)
    response_time = time.time() - start_time
    
    return jsonify({
        'api_key_configured': ETSY_API_KEY != 'your-etsy-api-key',
        'api_key_preview': ETSY_API_KEY[:10] + "..." if ETSY_API_KEY != 'your-etsy-api-key' else 'Not set',
        'test_call_successful': test_data is not None,
        'response_time_ms': round(response_time * 1000, 2),
        'demo_mode': ETSY_API_KEY == 'your-etsy-api-key',
        'test_data_sample': test_data.get('results', [])[:1] if test_data else None,
        'base_url': ETSY_BASE_URL,
        'status': 'Demo mode - using sample data' if ETSY_API_KEY == 'your-etsy-api-key' else 'API ready'
    })

@app.route('/api/system-stats')
def system_stats():
    """Get system performance stats (admin only)"""
    if not session.get('authenticated') or session.get('user_role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    
    try:
        import psutil
        import os
        
        # Get system stats
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Get database stats (safe way)
        total_users = len(USERS_DB)
        
        return jsonify({
            'system': {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'disk_percent': disk.percent,
                'disk_free_gb': round(disk.free / (1024**3), 2)
            },
            'database': {
                'total_users': total_users,
                'storage_type': 'in-memory'
            },
            'application': {
                'demo_mode': ETSY_API_KEY == 'your-etsy-api-key',
                'debug_mode': app.debug,
                'environment': os.environ.get('FLASK_ENV', 'development')
            }
        })
    except ImportError:
        # Fallback if psutil not available
        total_users = len(USERS_DB)
        return jsonify({
            'system': {
                'status': 'System monitoring unavailable (install psutil for detailed stats)'
            },
            'database': {
                'total_users': total_users,
                'storage_type': 'in-memory'
            },
            'application': {
                'demo_mode': ETSY_API_KEY == 'your-etsy-api-key',
                'debug_mode': app.debug,
                'environment': os.environ.get('FLASK_ENV', 'development')
            }
        })
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        return jsonify({'error': 'Failed to get system stats'}), 500

if __name__ == '__main__':
    app.run(debug=True)