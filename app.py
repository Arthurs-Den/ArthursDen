from flask import Flask, request, session, redirect, jsonify, render_template
import os
import secrets

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Simple credentials
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

@app.route('/')
def home():
    if not session.get('authenticated'):
        return redirect('/login')
    return render_template('dashboard.html', username=session.get('username', 'Admin'))

@app.route('/api/market-data')
def get_market_data():
    if not session.get('authenticated'):
        return jsonify({'error': 'Authentication required'}), 401
    
    # Premium market intelligence data
    market_data = {
        "products": [
            {
                "id": 1, "title": "Space Adventure Wall Art - Minimalist Kids Decor", 
                "shop": "RusticCharmDesigns", "price": 38.75, "views": 1420, "favorites": 56,
                "total_sales": 445, "weekly_sales": 35, "monthly_sales": 148, "sales_trend": "+35%",
                "revenue": 17244, "conversion": 31.3, "competition": "Low", "opportunity": "High",
                "theme": "Space Adventure", "market_trend": "Hot", "priority": "Critical"
            },
            {
                "id": 2, "title": "Floral Milestone Board - Monthly Photos Premium", 
                "shop": "BespokeBaby", "price": 52.00, "views": 2180, "favorites": 142,
                "total_sales": 1567, "weekly_sales": 42, "monthly_sales": 179, "sales_trend": "+28%",
                "revenue": 81484, "conversion": 11.4, "competition": "Low", "opportunity": "High",
                "theme": "Floral Milestone", "market_trend": "Hot", "priority": "Critical"
            },
            {
                "id": 3, "title": "Arctic Animals Growth Chart - Personalized Wooden", 
                "shop": "NurseryNameSigns", "price": 45.99, "views": 1340, "favorites": 78,
                "total_sales": 289, "weekly_sales": 28, "monthly_sales": 118, "sales_trend": "+33%",
                "revenue": 13290, "conversion": 21.6, "competition": "Low", "opportunity": "High",
                "theme": "Arctic Animals", "market_trend": "Trending", "priority": "High"
            },
            {
                "id": 4, "title": "Rustic Woodland Name Sign - Premium Handcrafted", 
                "shop": "WoodWorksStudio", "price": 34.99, "views": 1850, "favorites": 89,
                "total_sales": 847, "weekly_sales": 23, "monthly_sales": 98, "sales_trend": "+15%",
                "revenue": 29645, "conversion": 8.2, "competition": "High", "opportunity": "Medium",
                "theme": "Rustic Woodland", "market_trend": "Stable", "priority": "Medium"
            },
            {
                "id": 5, "title": "Modern Safari Nursery Collection - Custom Bundle", 
                "shop": "PersonalizedPerfection", "price": 68.50, "views": 1120, "favorites": 67,
                "total_sales": 234, "weekly_sales": 18, "monthly_sales": 76, "sales_trend": "+22%",
                "revenue": 16029, "conversion": 6.0, "competition": "Medium", "opportunity": "High",
                "theme": "Modern Safari", "market_trend": "Emerging", "priority": "High"
            }
        ],
        "insights": {
            "market_summary": {
                "total_revenue": "$157,692",
                "avg_weekly_sales": "29.2",
                "top_opportunity": "Space Adventure (+35% growth)",
                "critical_alerts": 3,
                "market_health": "Excellent"
            },
            "opportunities": [
                {
                    "niche": "Space/Adventure Theme",
                    "growth": "+35%",
                    "revenue_potential": "$25,000/month",
                    "action": "Enter immediately - Low competition window closing",
                    "urgency": "Critical"
                },
                {
                    "niche": "Arctic Animals Trend", 
                    "growth": "+33%",
                    "revenue_potential": "$15,000/month",
                    "action": "First-mover advantage available",
                    "urgency": "High"
                },
                {
                    "niche": "Premium Milestone Products",
                    "growth": "+28%", 
                    "revenue_potential": "$35,000/month",
                    "action": "Target luxury market segment",
                    "urgency": "High"
                }
            ],
            "alerts": [
                {
                    "type": "Critical Opportunity",
                    "message": "Space Adventure theme showing explosive 35% growth with minimal competition",
                    "action": "Launch premium space collection ($40-65 price range) within 7 days",
                    "revenue_impact": "$25K/month potential"
                },
                {
                    "type": "Competitive Threat", 
                    "message": "BespokeBaby dominates milestone market with 42 sales/week",
                    "action": "Develop competitive response or find alternative niche",
                    "revenue_impact": "$81K revenue at risk"
                },
                {
                    "type": "Emerging Trend",
                    "message": "Arctic Animals showing 33% growth - early adoption window",
                    "action": "Create comprehensive arctic collection before competitors",
                    "revenue_impact": "$15K/month opportunity"
                }
            ]
        }
    }
    
    return jsonify(market_data)

@app.route('/api/export')
def export_data():
    if not session.get('authenticated'):
        return jsonify({'error': 'Authentication required'}), 401
    
    # Simulate CSV export
    import io
    from flask import Response
    
    output = io.StringIO()
    output.write("Product,Shop,Price,Weekly Sales,Growth,Revenue,Priority\n")
    output.write("Space Adventure Wall Art,RusticCharmDesigns,$38.75,35,+35%,$17244,Critical\n")
    output.write("Floral Milestone Board,BespokeBaby,$52.00,42,+28%,$81484,Critical\n")
    output.write("Arctic Animals Chart,NurseryNameSigns,$45.99,28,+33%,$13290,High\n")
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=arthursden_intelligence_{session.get("username")}.csv'}
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