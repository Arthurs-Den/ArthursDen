from flask import Flask, request, session, redirect, jsonify, render_template
import os
import secrets
import requests
import json
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Simple credentials
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# Etsy API Configuration
ETSY_API_KEY = os.environ.get('ETSY_API_KEY', 'your-etsy-api-key')
ETSY_BASE_URL = 'https://openapi.etsy.com/v3'

def fetch_etsy_listings(keywords, limit=20):
    """Fetch real-time listings from Etsy API"""
    try:
        headers = {
            'x-api-key': ETSY_API_KEY,
            'Content-Type': 'application/json'
        }
        
        params = {
            'keywords': keywords,
            'limit': limit,
            'includes': 'Images,Shop,User',
            'sort_on': 'score',
            'sort_order': 'desc'
        }
        
        response = requests.get(
            f'{ETSY_BASE_URL}/application/listings/active',
            headers=headers,
            params=params,
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Etsy API Error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Error fetching Etsy data: {e}")
        return None

def process_etsy_data(listings_data, search_term):
    """Process Etsy API response into our format"""
    if not listings_data or 'results' not in listings_data:
        return []
    
    processed_products = []
    
    for i, listing in enumerate(listings_data['results'][:10]):  # Top 10 results
        try:
            # Calculate estimated metrics (Etsy doesn't provide all data publicly)
            price = float(listing.get('price', {}).get('amount', 0)) / 100  # Convert cents to dollars
            views = listing.get('views', 0)
            favorites = listing.get('num_favorers', 0)
            
            # Estimate sales based on views and favorites (industry averages)
            estimated_weekly_sales = max(1, int((views * 0.02) + (favorites * 0.1)))
            estimated_revenue = estimated_weekly_sales * price * 4  # Monthly estimate
            
            # Determine priority based on performance metrics
            if views > 1000 and favorites > 50:
                priority = "Critical"
                trend = "Hot"
            elif views > 500 and favorites > 25:
                priority = "High" 
                trend = "Trending"
            else:
                priority = "Medium"
                trend = "Stable"
            
            product = {
                "id": i + 1,
                "title": listing.get('title', 'Unknown Product')[:50] + "...",
                "shop": listing.get('Shop', {}).get('shop_name', 'Unknown Shop'),
                "price": price,
                "views": views,
                "favorites": favorites,
                "weekly_sales": estimated_weekly_sales,
                "revenue": int(estimated_revenue),
                "sales_trend": f"+{min(50, max(5, int(views/100)))}%",
                "market_trend": trend,
                "priority": priority,
                "etsy_url": listing.get('url', ''),
                "search_term": search_term
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
    return render_template('dashboard.html', username=session.get('username', 'Admin'))

@app.route('/api/market-data')
def get_market_data():
    if not session.get('authenticated'):
        return jsonify({'error': 'Authentication required'}), 401
    
    # Fetch real-time Etsy data for multiple search terms
    search_terms = [
        "nursery wall art",
        "personalized baby gifts", 
        "milestone baby blanket",
        "custom name sign",
        "baby shower decorations"
    ]
    
    all_products = []
    total_revenue = 0
    total_weekly_sales = 0
    critical_alerts = 0
    
    for term in search_terms:
        listings_data = fetch_etsy_listings(term, limit=5)  # Get 5 per category
        if listings_data:
            products = process_etsy_data(listings_data, term)
            all_products.extend(products)
            
            # Calculate totals
            for product in products:
                total_revenue += product['revenue']
                total_weekly_sales += product['weekly_sales']
                if product['priority'] == 'Critical':
                    critical_alerts += 1
    
    # If API fails, use fallback sample data
    if not all_products:
        all_products = [
            {
                "id": 1, "title": "API Connection Required - Using Sample Data",
                "shop": "Configure Etsy API", "price": 0.00, "views": 0, "favorites": 0,
                "weekly_sales": 0, "revenue": 0, "sales_trend": "0%",
                "market_trend": "Offline", "priority": "Critical", "etsy_url": "",
                "search_term": "API Setup Required"
            }
        ]
        total_revenue = 0
        total_weekly_sales = 0
        critical_alerts = 1
    
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
        output.write(f'"{product["title"]}","{product["shop"]}",${product["price"]:.2f},{product["views"]},{product["favorites"]},{product["weekly_sales"]},${product["revenue"]},{product["priority"]},{product["market_trend"]},"{product["search_term"]}","{product.get("etsy_url", "")}"\n')
    
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
    
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session['authenticated'] = True
        session['username'] = username
        return jsonify({'success': True, 'message': 'Login successful', 'redirect': '/'})
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/health')
def health():
    return {'status': 'healthy', 'app': 'ArthursDen', 'authenticated': session.get('authenticated', False)}

if __name__ == '__main__':
    app.run(debug=True)