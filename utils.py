import re
import html
from typing import List, Optional

def validate_username(username: str) -> tuple[bool, str]:
    """Validate username format"""
    if not username or len(username.strip()) < 3:
        return False, "Username must be at least 3 characters"
    
    if len(username) > 50:
        return False, "Username must be less than 50 characters"
    
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return False, "Username can only contain letters, numbers, hyphens, and underscores"
    
    return True, "Valid username"

def validate_email(email: str) -> tuple[bool, str]:
    """Validate email format"""
    if not email:
        return True, "Email is optional"  # Email is optional
    
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return False, "Invalid email format"
    
    if len(email) > 254:
        return False, "Email is too long"
    
    return True, "Valid email"

def validate_password(password: str) -> tuple[bool, str]:
    """Validate password strength"""
    if not password:
        return False, "Password is required"
    
    if len(password) < 6:
        return False, "Password must be at least 6 characters"
    
    if len(password) > 128:
        return False, "Password is too long"
    
    return True, "Valid password"

def sanitize_text_input(text: str, max_length: int = 1000) -> str:
    """Sanitize text input to prevent XSS"""
    if not text:
        return ""
    
    # Remove HTML tags and escape special characters
    sanitized = html.escape(text.strip())
    
    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized

def validate_search_terms(terms: List[str]) -> tuple[bool, str, List[str]]:
    """Validate and clean search terms"""
    if not terms:
        return True, "No search terms provided", []
    
    if len(terms) > 20:  # Reasonable limit
        return False, "Too many search terms (max 20)", []
    
    clean_terms = []
    for term in terms:
        if isinstance(term, str):
            clean_term = sanitize_text_input(term, max_length=100)
            if clean_term and len(clean_term) >= 2:  # Minimum length
                clean_terms.append(clean_term)
    
    if len(clean_terms) == 0:
        return False, "No valid search terms found", []
    
    return True, f"Validated {len(clean_terms)} search terms", clean_terms

def validate_shop_names(shops: List[str]) -> tuple[bool, str, List[str]]:
    """Validate and clean shop names"""
    if not shops:
        return True, "No shop names provided", []
    
    if len(shops) > 50:  # Reasonable limit for watchlist
        return False, "Too many shops in watchlist (max 50)", []
    
    clean_shops = []
    for shop in shops:
        if isinstance(shop, str):
            # Shop names should be alphanumeric with some special chars
            clean_shop = re.sub(r'[^a-zA-Z0-9\s\-_]', '', shop.strip())
            if clean_shop and len(clean_shop) >= 2:
                clean_shops.append(clean_shop[:50])  # Max shop name length
    
    return True, f"Validated {len(clean_shops)} shop names", clean_shops

def format_currency(amount: float, currency: str = "GBP") -> str:
    """Format currency consistently"""
    try:
        if currency == "GBP":
            return f"£{amount:,.2f}"
        elif currency == "USD":
            return f"${amount:,.2f}"
        elif currency == "EUR":
            return f"€{amount:,.2f}"
        else:
            return f"{currency} {amount:,.2f}"
    except (ValueError, TypeError):
        return f"{currency} 0.00"

def safe_int(value, default: int = 0) -> int:
    """Safely convert to integer"""
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default

def safe_float(value, default: float = 0.0) -> float:
    """Safely convert to float"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Safely truncate text"""
    if not text or len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def is_safe_url(url: str) -> bool:
    """Check if URL is safe (basic validation)"""
    if not url:
        return False
    
    # Allow Etsy URLs and common safe domains
    safe_domains = [
        'etsy.com',
        'etsystatic.com',
        'www.etsy.com'
    ]
    
    return any(domain in url.lower() for domain in safe_domains)