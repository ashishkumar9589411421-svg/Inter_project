import os, sqlite3, json, uuid, math, hmac, hashlib, datetime, secrets, re, io, smtplib, traceback, logging
import urllib.request
from functools import wraps
from flask import Flask, request, jsonify, send_file, g
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import bcrypt, jwt, razorpay
from dotenv import load_dotenv
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors

try:
    import psycopg2
    from psycopg2.extras import DictCursor
except ImportError:
    psycopg2 = None

class PostgresCursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor
        self.lastrowid = None
        self.description = None
    
    def execute(self, query, params=()):
        is_insert = query.strip().upper().startswith("INSERT")
        pg_query = query.replace('?', '%s')
        if is_insert and "RETURNING " not in pg_query.upper():
            pg_query = pg_query.rstrip(" ;") + " RETURNING id"
        try:
            self.cursor.execute(pg_query, params)
        except Exception as e:
            app.logger.error(f"DB Error: {e} | Query: {pg_query}")
            raise e
        self.description = self.cursor.description
        if is_insert:
            try:
                res = self.cursor.fetchone()
                if res:
                    self.lastrowid = res['id']
            except: pass
        return self

    def executemany(self, query, params_list):
        pg_query = query.replace('?', '%s')
        try:
            self.cursor.executemany(pg_query, params_list)
        except Exception as e:
            app.logger.error(f"DB Error: {e} | Query: {pg_query}")
            raise e
        self.description = self.cursor.description
        return self
        
    def fetchone(self): return self.cursor.fetchone()
    def fetchall(self): return self.cursor.fetchall()
    def fetchmany(self, size): return self.cursor.fetchmany(size)

class PostgresConnectionWrapper:
    def __init__(self, conn):
        self.conn = conn
    
    def execute(self, query, params=()):
        cursor = self.cursor()
        return cursor.execute(query, params)
        
    def executescript(self, script):
        self.cursor().cursor.execute(script)
        self.conn.commit()
        
    def cursor(self):
        return PostgresCursorWrapper(self.conn.cursor(cursor_factory=DictCursor))
        
    def commit(self): self.conn.commit()
    def rollback(self): self.conn.rollback()
    def close(self): self.conn.close()

# Enable detailed logging
logging.basicConfig(level=logging.DEBUG)

# ─── App Setup ───────────────────────────────────────────────────────────────
load_dotenv()
app = Flask(__name__)
app.logger.setLevel(logging.DEBUG)
CORS(app, supports_credentials=True)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
DATABASE = os.environ.get('DATABASE_URL', 'shop.db')
app.config['DATABASE'] = DATABASE
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')

if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
else:
    razorpay_client = None

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    if os.environ.get('DEBUG') == 'False':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

limiter = Limiter(get_remote_address, app=app, default_limits=["200 per minute"])

# ─── DB Helpers ──────────────────────────────────────────────────────────────
def get_db():
    if 'db' not in g:
        db_url = app.config['DATABASE']
        if db_url.startswith('postgres'):
            if psycopg2 is None: raise Exception("psycopg2 is not installed!")
            conn = psycopg2.connect(db_url)
            g.db = PostgresConnectionWrapper(conn)
        else:
            g.db = sqlite3.connect(db_url)
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA journal_mode=WAL")
            g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db: db.close()

def dict_row(row):
    return dict(row) if row else None

def dict_rows(rows):
    return [dict(r) for r in rows]

def sanitize(val):
    if val is None: return None
    if isinstance(val, str):
        return re.sub(r'[<>]', '', val.strip())
    return val

# ─── Database Schema (22 Tables) ────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mobile_number TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT DEFAULT 'customer' CHECK(role IN ('customer','admin')),
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,
    dob TEXT, gender TEXT, photo_url TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS addresses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    label TEXT DEFAULT 'Home',
    full_name TEXT, phone TEXT,
    line1 TEXT NOT NULL, line2 TEXT, city TEXT NOT NULL,
    state TEXT NOT NULL, pincode TEXT NOT NULL, country TEXT DEFAULT 'India',
    is_default INTEGER DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL, slug TEXT UNIQUE NOT NULL,
    image_url TEXT, description TEXT, sort_order INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
    description TEXT, brand TEXT, sku TEXT UNIQUE,
    category_id INTEGER,
    base_price REAL NOT NULL, sale_price REAL,
    fabric TEXT, material TEXT, weight TEXT, care_instructions TEXT,
    image_url TEXT, images TEXT DEFAULT '[]', video_url TEXT,
    seo_title TEXT, seo_description TEXT,
    is_active INTEGER DEFAULT 1, is_featured INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(category_id) REFERENCES categories(id)
);
CREATE TABLE IF NOT EXISTS product_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    size TEXT, color TEXT, color_hex TEXT,
    stock INTEGER DEFAULT 0, sku_variant TEXT,
    price_override REAL,
    FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS cart (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
    variant_id INTEGER, quantity INTEGER DEFAULT 1,
    saved_for_later INTEGER DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(product_id) REFERENCES products(id),
    FOREIGN KEY(variant_id) REFERENCES product_variants(id)
);
CREATE TABLE IF NOT EXISTS wishlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, product_id),
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(product_id) REFERENCES products(id)
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_number TEXT UNIQUE NOT NULL,
    user_id INTEGER NOT NULL,
    address_id INTEGER,
    subtotal REAL, discount REAL DEFAULT 0,
    shipping REAL DEFAULT 0, total REAL NOT NULL,
    status TEXT DEFAULT 'PENDING',
    payment_method TEXT DEFAULT 'COD',
    payment_id TEXT, razorpay_order_id TEXT,
    coupon_code TEXT, notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
    variant_id INTEGER,
    product_name TEXT, product_image TEXT,
    size TEXT, color TEXT,
    price REAL NOT NULL, quantity INTEGER NOT NULL,
    FOREIGN KEY(order_id) REFERENCES orders(id),
    FOREIGN KEY(product_id) REFERENCES products(id)
);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
    order_id INTEGER,
    rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
    title TEXT, body TEXT, images TEXT DEFAULT '[]',
    is_approved INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(product_id) REFERENCES products(id)
);
CREATE TABLE IF NOT EXISTS coupons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    discount_type TEXT DEFAULT 'percentage' CHECK(discount_type IN ('percentage','flat')),
    discount_value REAL NOT NULL,
    min_order REAL DEFAULT 0, max_discount REAL,
    usage_limit INTEGER DEFAULT 100, used_count INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1, 
    expires_at TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL, message TEXT NOT NULL,
    type TEXT DEFAULT 'info',
    is_read INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS wallets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,
    balance REAL DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS wallet_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    type TEXT CHECK(type IN ('credit','debit')),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS referrals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    referrer_id INTEGER NOT NULL,
    referred_id INTEGER,
    referral_code TEXT UNIQUE NOT NULL,
    reward_given INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(referrer_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS loyalty_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    points INTEGER NOT NULL,
    type TEXT CHECK(type IN ('earn','redeem')),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS support_tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    subject TEXT NOT NULL, message TEXT NOT NULL,
    status TEXT DEFAULT 'open' CHECK(status IN ('open','in_progress','resolved','closed')),
    admin_reply TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS inventory_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_id INTEGER NOT NULL,
    change INTEGER NOT NULL,
    reason TEXT, admin_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(variant_id) REFERENCES product_variants(id)
);
CREATE TABLE IF NOT EXISTS banners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT, subtitle TEXT,
    image_url TEXT NOT NULL, link TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS blog_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
    content TEXT, excerpt TEXT,
    image_url TEXT, category TEXT,
    author_id INTEGER, is_published INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(author_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    value TEXT
);
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER, action TEXT NOT NULL,
    target TEXT, details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS product_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    image_url TEXT NOT NULL,
    is_primary INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(product_id) REFERENCES products(id)
);
CREATE TABLE IF NOT EXISTS product_videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    video_url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(product_id) REFERENCES products(id)
);
CREATE TABLE IF NOT EXISTS returns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','refunded')),
    admin_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(order_id) REFERENCES orders(id),
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS otp_verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mobile TEXT NOT NULL,
    otp TEXT NOT NULL,
    verified INTEGER DEFAULT 0,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS newsletter_subscribers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    location TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(order_id) REFERENCES orders(id)
);
CREATE TABLE IF NOT EXISTS coupon_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coupon_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    order_id INTEGER NOT NULL,
    discount_applied REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(coupon_id) REFERENCES coupons(id),
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(order_id) REFERENCES orders(id)
);
CREATE TABLE IF NOT EXISTS delivery_partners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    tracking_url_template TEXT,
    contact_number TEXT,
    is_active INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS product_views (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    user_id INTEGER,
    ip_address TEXT,
    viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(product_id) REFERENCES products(id),
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS recently_viewed (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, product_id),
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(product_id) REFERENCES products(id)
);
CREATE TABLE IF NOT EXISTS abandoned_cart (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    cart_data TEXT NOT NULL,
    recovered INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS referral_earnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    referral_id INTEGER NOT NULL,
    referrer_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(referral_id) REFERENCES referrals(id),
    FOREIGN KEY(referrer_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS seo_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_route TEXT UNIQUE NOT NULL,
    meta_title TEXT,
    meta_description TEXT,
    meta_keywords TEXT,
    og_image TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS email_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    email TEXT NOT NULL,
    subject TEXT,
    status TEXT DEFAULT 'sent',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS whatsapp_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    mobile TEXT NOT NULL,
    message TEXT,
    status TEXT DEFAULT 'sent',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS ticket_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    sender_type TEXT NOT NULL CHECK(sender_type IN ('user','admin')),
    sender_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(ticket_id) REFERENCES support_tickets(id)
);
CREATE TABLE IF NOT EXISTS luxe_club_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,
    payment_id TEXT,
    razorpay_order_id TEXT,
    amount REAL DEFAULT 499,
    is_active INTEGER DEFAULT 1,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_slug ON products(slug);
CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_cart_user ON cart(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_reviews_product ON reviews(product_id);
CREATE INDEX IF NOT EXISTS idx_variants_product ON product_variants(product_id);
CREATE INDEX IF NOT EXISTS idx_users_mobile ON users(mobile_number);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_ticket_messages ON ticket_messages(ticket_id);
"""

def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')

def init_db():
    db_url = app.config['DATABASE']
    if db_url.startswith('postgres'):
        if psycopg2 is None: raise Exception("psycopg2 is not installed!")
        conn = psycopg2.connect(db_url)
        db = PostgresConnectionWrapper(conn)
        # PostgreSQL doesn't use AUTOINCREMENT
        script = SCHEMA.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        db.executescript(script)
        cur = db.cursor()
        cur.execute("SELECT id FROM users WHERE role='admin'")
    else:
        conn = sqlite3.connect(db_url)
        conn.executescript(SCHEMA)
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE role='admin'")
        db = conn
        
    # Seed admin
    if not cur.fetchone():
        admin_pw = os.environ.get('ADMIN_PASSWORD', 'admin123')
        pw = bcrypt.hashpw(admin_pw.encode(), bcrypt.gensalt()).decode()
        
        cur.execute("INSERT INTO users (mobile_number,email,password_hash,name,role) VALUES (?,?,?,?,?)",
                    ('9999999999','ashishadmin', pw, 'Ashish Admin', 'admin'))
        admin_id = cur.lastrowid
        cur.execute("INSERT INTO profiles (user_id) VALUES (?)", (admin_id,))
        cur.execute("INSERT INTO wallets (user_id) VALUES (?)", (admin_id,))
        ref_code = 'LUXE' + secrets.token_hex(3).upper()
        cur.execute("INSERT INTO referrals (referrer_id, referral_code) VALUES (?,?)", (admin_id, ref_code))

    # Seed settings
    cur.execute("SELECT COUNT(*) FROM settings")
        
    if cur.fetchone()[0] == 0:
        default_settings = [
            ('brand_name', 'LUXE'),
            ('primary_color', '#121212'),
            ('accent_color', '#C5A880'),
            ('developer_name', 'Ashish Kumar'),
            ('developer_linkedin', 'https://www.linkedin.com/in/ashish-kumar-445964324/'),
            ('developer_portfolio', 'https://ashishkumar9589411421-svg.github.io/portfolio_v27-11-25/'),
            ('show_developer_credit', '1')
        ]
        for k, v in default_settings:
            cur.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (k, v))
                
    db.commit()

    # Seed categories
    cur.execute("SELECT COUNT(*) FROM categories")
    if cur.fetchone()[0] == 0:
        cats = [
            ('Oversized T-Shirts','oversized-t-shirts','https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=400&q=80','Premium oversized comfort',1),
            ('Kurtis','kurtis','https://images.unsplash.com/photo-1617627143750-d86bc21e42bb?w=400&q=80','Elegant ethnic wear',2),
            ('Tops','tops','https://images.unsplash.com/photo-1485968579580-b6d095142e6e?w=400&q=80','Stylish everyday tops',3),
            ('Korean Tops','korean-tops','https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=400&q=80','K-fashion inspired',4),
            ('Jeans','jeans','https://images.unsplash.com/photo-1542272604-787c3835535d?w=400&q=80','Premium denim',5),
            ('Cargo Pants','cargo-pants','https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?w=400&q=80','Street style cargo',6),
            ('Co-ord Sets','co-ord-sets','https://images.unsplash.com/photo-1509631179647-0177331693ae?w=400&q=80','Matching sets',7),
            ('Dresses','dresses','https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=400&q=80','Elegant dresses',8),
            ('Ethnic Wear','ethnic-wear','https://images.unsplash.com/photo-1583391733956-6c78276477e2?w=400&q=80','Traditional fashion',9),
            ('Western Wear','western-wear','https://images.unsplash.com/photo-1434389677669-e08b4cda3a02?w=400&q=80','Modern western styles',10),
            ('Accessories','accessories','https://images.unsplash.com/photo-1611085583191-a3b181a88401?w=400&q=80','Complete your look',11),
        ]
        cur.executemany("INSERT INTO categories (name,slug,image_url,description,sort_order) VALUES (?,?,?,?,?)", cats)

    # Seed products
    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] == 0:
        products = [
            ('Midnight Oversized Tee','midnight-oversized-tee','Ultra-soft premium cotton oversized t-shirt with drop shoulders and a relaxed silhouette.','LUXE Originals','LX-OT-001',1,2999,2499,'100% Cotton','Cotton','250g','Machine wash cold',
             'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=600&q=80','[]','',1,1),
            ('Cloud White Oversized','cloud-white-oversized','Crisp white oversized tee crafted from Egyptian cotton for unmatched softness.','LUXE Originals','LX-OT-002',1,2799,2299,'Egyptian Cotton','Cotton','240g','Machine wash cold',
             'https://images.unsplash.com/photo-1622445275576-721325763afe?w=600&q=80','[]','',1,0),
            ('Embroidered Silk Kurti','embroidered-silk-kurti','Hand-embroidered silk kurti with intricate thread work and mirror detailing.','LUXE Ethnic','LX-KU-001',2,5999,4599,'Pure Silk','Silk','300g','Dry clean only',
             'https://images.unsplash.com/photo-1617627143750-d86bc21e42bb?w=600&q=80','[]','',1,1),
            ('Pastel Cotton Kurti','pastel-cotton-kurti','Lightweight cotton kurti in pastel shades, perfect for everyday elegance.','LUXE Ethnic','LX-KU-002',2,3499,2799,'Cotton Blend','Cotton','200g','Machine wash',
             'https://images.unsplash.com/photo-1583391733956-6c78276477e2?w=600&q=80','[]','',1,0),
            ('Seoul Puff Sleeve Top','seoul-puff-sleeve','Trendy Korean-style puff sleeve top with square neckline.','K-Style','LX-KT-001',4,1999,1599,'Polyester Blend','Polyester','180g','Hand wash',
             'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=600&q=80','[]','',1,1),
            ('Ribbed Crop Top','ribbed-crop-top','Form-fitting ribbed crop top in neutral tones.','LUXE Basics','LX-TP-001',3,1499,1199,'Ribbed Knit','Cotton','150g','Machine wash',
             'https://images.unsplash.com/photo-1485968579580-b6d095142e6e?w=600&q=80','[]','',1,0),
            ('Vintage Wash Denim','vintage-wash-denim','Classic straight-fit jeans with vintage wash and premium selvedge denim.','Denim Co','LX-JN-001',5,4499,3499,'Selvedge Denim','Denim','450g','Machine wash cold',
             'https://images.unsplash.com/photo-1542272604-787c3835535d?w=600&q=80','[]','',1,1),
            ('High Waist Mom Jeans','high-waist-mom-jeans','Comfortable high-waist mom jeans with tapered leg and stretch.','Denim Co','LX-JN-002',5,3999,3199,'Stretch Denim','Denim','400g','Machine wash',
             'https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=600&q=80','[]','',1,0),
            ('Tactical Cargo Pants','tactical-cargo','Utility-style cargo pants with multiple pockets and adjustable cuffs.','Street LUXE','LX-CP-001',6,3299,2699,'Cotton Twill','Cotton','350g','Machine wash',
             'https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?w=600&q=80','[]','',1,0),
            ('Sage Co-ord Set','sage-coord-set','Matching crop top and wide-leg pants in sage green linen.','LUXE Studio','LX-CS-001',7,4999,3999,'Pure Linen','Linen','300g','Dry clean recommended',
             'https://images.unsplash.com/photo-1509631179647-0177331693ae?w=600&q=80','[]','',1,1),
            ('Satin Slip Dress','satin-slip-dress','Luxurious satin slip dress with cowl neckline and adjustable straps.','LUXE Evening','LX-DR-001',8,5499,4299,'Satin','Polyester Satin','220g','Hand wash',
             'https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=600&q=80','[]','',1,1),
            ('Boho Maxi Dress','boho-maxi-dress','Flowy bohemian maxi dress with floral print and ruffle details.','LUXE Boho','LX-DR-002',8,4799,3799,'Chiffon','Polyester','280g','Hand wash',
             'https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?w=600&q=80','[]','',1,0),
        ]
        for p in products:
            cur.execute("""INSERT INTO products (name,slug,description,brand,sku,category_id,base_price,sale_price,
                fabric,material,weight,care_instructions,image_url,images,video_url,is_active,is_featured)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", p)
            pid = cur.lastrowid
            sizes = ['XS','S','M','L','XL','XXL']
            colors = [('Black','#000000'),('White','#FFFFFF'),('Navy','#1B2A4A')]
            for s in sizes:
                for c_name, c_hex in colors:
                    stock = 25 if s in ['M','L','XL'] else 10
                    vsku = f"{p[4]}-{s}-{c_name[:2].upper()}"
                    cur.execute("INSERT INTO product_variants (product_id,size,color,color_hex,stock,sku_variant) VALUES (?,?,?,?,?,?)",
                                (pid, s, c_name, c_hex, stock, vsku))

    # Seed banners
    cur.execute("SELECT COUNT(*) FROM banners")
    if cur.fetchone()[0] == 0:
        banners = [
            ('Summer Collection 2026','Up to 50% Off','https://images.unsplash.com/photo-1445205170230-053b83016050?w=1200&q=80','#shop',1,1),
            ('New Arrivals','Fresh Drops Weekly','https://images.unsplash.com/photo-1490481651871-ab68de25d43d?w=1200&q=80','#shop',2,1),
        ]
        cur.executemany("INSERT INTO banners (title,subtitle,image_url,link,sort_order,is_active) VALUES (?,?,?,?,?,?)", banners)

    # Seed coupons
    cur.execute("SELECT COUNT(*) FROM coupons")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO coupons (code,discount_type,discount_value,min_order,max_discount,usage_limit) VALUES (?,?,?,?,?,?)",
                    ('WELCOME10','percentage',10,999,500,1000))
        cur.execute("INSERT INTO coupons (code,discount_type,discount_value,min_order,max_discount,usage_limit) VALUES (?,?,?,?,?,?)",
                    ('FLAT200','flat',200,1499,200,500))

    conn.commit()
    conn.close()

# ─── Auth Helpers ────────────────────────────────────────────────────────────
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id, role='customer'):
    return jwt.encode({
        'user_id': user_id, 'role': role,
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=48)
    }, app.config['SECRET_KEY'], algorithm='HS256')

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '')
        if not token.startswith('Bearer '):
            return jsonify({'error': 'Token missing'}), 401
        try:
            data = jwt.decode(token.split(' ')[1], app.config['SECRET_KEY'], algorithms=['HS256'])
            user = get_db().execute('SELECT * FROM users WHERE id=? AND is_active=1', (data['user_id'],)).fetchone()
            if not user: raise Exception()
        except:
            return jsonify({'error': 'Invalid or expired token'}), 401
        return f(dict_row(user), *args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '')
        if not token.startswith('Bearer '):
            return jsonify({'error': 'Token missing'}), 401
        try:
            data = jwt.decode(token.split(' ')[1], app.config['SECRET_KEY'], algorithms=['HS256'])
            user = get_db().execute('SELECT * FROM users WHERE id=? AND role=? AND is_active=1', (data['user_id'], 'admin')).fetchone()
            if not user: raise Exception()
        except:
            return jsonify({'error': 'Admin access required'}), 403
        return f(dict_row(user), *args, **kwargs)
    return decorated

def log_audit(admin_id, action, target='', details=''):
    get_db().execute("INSERT INTO audit_logs (admin_id,action,target,details) VALUES (?,?,?,?)",
                     (admin_id, action, target, details))
    get_db().commit()

def notify(user_id, title, message, ntype='info'):
    db = get_db()
    db.execute("INSERT INTO notifications (user_id,title,message,type) VALUES (?,?,?,?)",
                     (user_id, title, message, ntype))
    
    u = db.execute("SELECT email, mobile_number FROM users WHERE id=?", (user_id,)).fetchone()
    if u:
        if u['email']:
            db.execute("INSERT INTO email_logs (user_id, email, subject, status) VALUES (?, ?, ?, ?)",
                       (user_id, u['email'], title, 'sent'))
            app.logger.info(f"EMAIL to {u['email']}: [{title}] {message}")
        if u['mobile_number']:
            db.execute("INSERT INTO whatsapp_logs (user_id, mobile, message, status) VALUES (?, ?, ?, ?)",
                       (user_id, u['mobile_number'], message, 'sent'))
            app.logger.info(f"WHATSAPP to {u['mobile_number']}: [{title}] {message}")
            
    db.commit()

# ─── Static File Routes ─────────────────────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))

@app.route('/')
def serve_index():
    with open(os.path.join(BASE, 'index.html'), 'r', encoding='utf-8') as f:
        return f.read(), 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/style.css')
def serve_css():
    with open(os.path.join(BASE, 'style.css'), 'r', encoding='utf-8') as f:
        return f.read(), 200, {'Content-Type': 'text/css; charset=utf-8'}

@app.route('/script.js')
def serve_js():
    with open(os.path.join(BASE, 'script.js'), 'r', encoding='utf-8') as f:
        return f.read(), 200, {'Content-Type': 'application/javascript; charset=utf-8'}

# ─── AUTH APIS ───────────────────────────────────────────────────────────────

@app.route('/api/auth/send-otp', methods=['POST'])
@limiter.limit("5 per minute")
def send_otp():
    d = request.json or {}
    mobile = sanitize(d.get('mobile_number', ''))
    if not re.match(r'^\d{10}$', mobile):
        return jsonify({'error': 'Enter valid 10-digit mobile number'}), 400
    
    otp = '1234' # Mock OTP for all testing
    exp = (datetime.datetime.now() + datetime.timedelta(minutes=10)).isoformat()
    
    db = get_db()
    db.execute("INSERT INTO otp_verifications (mobile, otp, expires_at) VALUES (?, ?, ?)", (mobile, otp, exp))
    db.commit()
    
    # Normally we would integrate MSG91 Send OTP API here
    app.logger.info(f"MOCK OTP for {mobile}: {otp}")
    return jsonify({'message': f'OTP sent successfully (Mock: {otp})'})

@app.route('/api/auth/verify-otp', methods=['POST'])
@limiter.limit("10 per minute")
def verify_otp():
    d = request.json or {}
    mobile = sanitize(d.get('mobile_number', ''))
    otp = sanitize(d.get('otp', ''))
    if not mobile or not otp:
        return jsonify({'error': 'Mobile and OTP required'}), 400
        
    db = get_db()
    record = dict_row(db.execute("SELECT * FROM otp_verifications WHERE mobile=? ORDER BY id DESC LIMIT 1", (mobile,)).fetchone())
    
    if not record or record['verified'] == 2:
        return jsonify({'error': 'Please request a new OTP'}), 400
    if record['expires_at'] < datetime.datetime.now().isoformat():
        return jsonify({'error': 'OTP expired'}), 400
    if record['otp'] != otp:
        return jsonify({'error': 'Invalid OTP'}), 400
        
    db.execute("UPDATE otp_verifications SET verified=1 WHERE id=?", (record['id'],))
    
    user = db.execute("SELECT * FROM users WHERE mobile_number=?", (mobile,)).fetchone()
    is_new = False
    if not user:
        # Create a new user instantly if they only provided OTP
        pw = hash_password(secrets.token_hex(8))
        cur = db.execute("INSERT INTO users (mobile_number, name, password_hash) VALUES (?, ?, ?)", (mobile, 'New User', pw))
        user_id = cur.lastrowid
        db.execute("INSERT INTO profiles (user_id) VALUES (?)", (user_id,))
        db.execute("INSERT INTO wallets (user_id) VALUES (?)", (user_id,))
        ref_code = 'LUXE' + secrets.token_hex(3).upper()
        db.execute("INSERT INTO referrals (referrer_id, referral_code) VALUES (?,?)", (user_id, ref_code))
        db.execute("UPDATE otp_verifications SET verified=2 WHERE id=?", (record['id'],))
        user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        is_new = True

    db.commit()
    token = create_token(user['id'], user['role'])
    return jsonify({'token': token, 'user': dict_row(user), 'is_new': is_new})

@app.route('/api/auth/verify-msg91', methods=['POST'])
@limiter.limit("10 per minute")
def verify_msg91():
    d = request.json or {}
    access_token = sanitize(d.get('access_token', ''))
    if not access_token:
        return jsonify({'error': 'Access token missing'}), 400
        
    auth_key = os.environ.get('MSG91_AUTH_KEY')
    if not auth_key:
        return jsonify({'error': 'MSG91 not configured'}), 500

    url = 'https://control.msg91.com/api/v5/widget/verifyAccessToken'
    payload = json.dumps({
        "authkey": auth_key,
        "access-token": access_token
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
    
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode())
    except Exception as e:
        return jsonify({'error': 'Failed to communicate with MSG91'}), 500
        
    if res_data.get('type') == 'error':
        return jsonify({'error': res_data.get('message', 'Invalid OTP')}), 400
        
    mobile = res_data.get('message', '')
    if mobile.startswith('91') and len(mobile) == 12:
        mobile = mobile[2:]
    
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE mobile_number=?", (mobile,)).fetchone()
    is_new = False
    if not user:
        pw = hash_password(secrets.token_hex(8)) # Dummy password
        cur = db.execute("INSERT INTO users (mobile_number, name, password_hash) VALUES (?, ?, ?)", (mobile, 'New User', pw))
        user_id = cur.lastrowid
        db.execute("INSERT INTO profiles (user_id) VALUES (?)", (user_id,))
        db.execute("INSERT INTO wallets (user_id) VALUES (?)", (user_id,))
        ref_code = 'LUXE' + secrets.token_hex(3).upper()
        db.execute("INSERT INTO referrals (referrer_id, referral_code) VALUES (?,?)", (user_id, ref_code))
        user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        is_new = True

    db.commit()
    token = create_token(user['id'], user['role'])
    return jsonify({
        'message': 'Logged in successfully',
        'token': token,
        'user': dict_row(user),
        'is_new': is_new
    })

@app.route('/api/auth/forgot-password', methods=['POST'])
@limiter.limit("5 per minute")
def forgot_password():
    d = request.json or {}
    mobile = sanitize(d.get('mobile_number',''))
    new_password = d.get('new_password','')
    
    if not mobile or not new_password:
        return jsonify({'error': 'Mobile number and new password required'}), 400
    if len(new_password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
        
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE mobile_number=? AND is_active=1", (mobile,)).fetchone()
    if not user:
        return jsonify({'error': 'User not found'}), 404
        
    verified_record = db.execute("SELECT id FROM otp_verifications WHERE mobile=? AND verified=1 ORDER BY id DESC LIMIT 1", (mobile,)).fetchone()
    if not verified_record:
        return jsonify({'error': 'Please verify your mobile number with OTP first'}), 400
        
    db.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(new_password), user['id']))
    db.execute("UPDATE otp_verifications SET verified=2 WHERE id=?", (verified_record['id'],))
    db.commit()
    
    return jsonify({'message': 'Password reset successfully'})

@app.route('/api/auth/register', methods=['POST'])
@limiter.limit("5 per minute")
def register():
    d = request.json or {}
    name = sanitize(d.get('name',''))
    mobile = sanitize(d.get('mobile_number',''))
    email = sanitize(d.get('email',''))
    password = d.get('password','')
    if not name or not mobile or not password:
        return jsonify({'error': 'Name, mobile & password required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    if not re.match(r'^\d{10}$', mobile):
        return jsonify({'error': 'Enter valid 10-digit mobile number'}), 400
    db = get_db()
    
    # OTP verification is optional — if verified, consume it; otherwise allow direct registration
    verified_record = db.execute("SELECT id FROM otp_verifications WHERE mobile=? AND verified=1 ORDER BY id DESC LIMIT 1", (mobile,)).fetchone()

    if db.execute('SELECT id FROM users WHERE mobile_number=?', (mobile,)).fetchone():
        return jsonify({'error': 'Mobile number already registered'}), 409
    if email and db.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone():
        return jsonify({'error': 'Email already registered'}), 409
        
    pw_hash = hash_password(password)
    cur = db.execute("INSERT INTO users (mobile_number,email,password_hash,name) VALUES (?,?,?,?)",
                     (mobile, email or None, pw_hash, name))
    uid = cur.lastrowid
    db.execute("INSERT INTO profiles (user_id) VALUES (?)", (uid,))
    db.execute("INSERT INTO wallets (user_id, balance) VALUES (?,?)", (uid, 0))
    ref_code = 'LUXE' + secrets.token_hex(3).upper()
    db.execute("INSERT INTO referrals (referrer_id, referral_code) VALUES (?,?)", (uid, ref_code))
    if verified_record:
        db.execute("UPDATE otp_verifications SET verified=2 WHERE id=?", (verified_record['id'],))
    
    # Handle referral bonus
    ref = d.get('referral_code','')
    if ref:
        referrer = db.execute("SELECT referrer_id FROM referrals WHERE referral_code=? AND referred_id IS NULL", (ref,)).fetchone()
        if referrer:
            db.execute("UPDATE referrals SET referred_id=?, reward_given=1 WHERE referral_code=?", (uid, ref))
            db.execute("UPDATE wallets SET balance=balance+100 WHERE user_id=?", (referrer['referrer_id'],))
            db.execute("INSERT INTO wallet_transactions (user_id,amount,type,description) VALUES (?,?,?,?)",
                       (referrer['referrer_id'], 100, 'credit', f'Referral bonus for {name}'))
            db.execute("INSERT INTO loyalty_points (user_id,points,type,description) VALUES (?,?,?,?)",
                       (referrer['referrer_id'], 50, 'earn', f'Referral: {name} joined'))
            notify(referrer['referrer_id'], 'Referral Reward!', f'{name} joined using your code. ₹100 added to wallet!', 'reward')
    db.commit()
    token = create_token(uid)
    return jsonify({'token': token, 'name': name, 'user_id': uid}), 201

@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    d = request.json or {}
    identifier = sanitize(d.get('mobile_number', d.get('email', '')))
    password = d.get('password','')
    otp = sanitize(d.get('otp',''))
    
    if not identifier:
        return jsonify({'error': 'Mobile number or email required'}), 400
        
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE (mobile_number=? OR email=?) AND is_active=1",
                      (identifier, identifier)).fetchone()
                      
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if otp:
        record = db.execute("SELECT * FROM otp_verifications WHERE mobile=? AND otp=? AND verified=0 ORDER BY id DESC LIMIT 1", (identifier, otp)).fetchone()
        if not record or record['expires_at'] < datetime.datetime.now().isoformat():
            return jsonify({'error': 'Invalid or expired OTP'}), 400
        db.execute("UPDATE otp_verifications SET verified=2 WHERE id=?", (record['id'],))
        db.commit()
    elif password:
        if not check_password(password, user['password_hash']):
            return jsonify({'error': 'Invalid credentials'}), 401
    else:
        return jsonify({'error': 'Password or OTP required'}), 400
        
    token = create_token(user['id'], user['role'])
    return jsonify({'token': token, 'name': user['name'], 'role': user['role'], 'user_id': user['id']})

@app.route('/api/auth/admin-login', methods=['POST'])
@limiter.limit("5 per minute")
def admin_login():
    d = request.json or {}
    username = d.get('username','')
    password = d.get('password','')
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE (name=? OR email=? OR mobile_number=?) AND role='admin' AND is_active=1", (username, username, username)).fetchone()
    if not user or not check_password(password, user['password_hash']):
        return jsonify({'error': 'Invalid admin credentials'}), 401
    token = create_token(user['id'], 'admin')
    log_audit(user['id'], 'admin_login', 'auth', 'Admin logged in')
    return jsonify({'token': token, 'name': user['name'], 'role': 'admin'})

@app.route('/api/auth/me', methods=['GET'])
@token_required
def get_me(user):
    db = get_db()
    profile = dict_row(db.execute("SELECT * FROM profiles WHERE user_id=?", (user['id'],)).fetchone()) or {}
    wallet = dict_row(db.execute("SELECT balance FROM wallets WHERE user_id=?", (user['id'],)).fetchone()) or {'balance':0}
    points = db.execute("SELECT COALESCE(SUM(CASE WHEN type='earn' THEN points ELSE -points END),0) as total FROM loyalty_points WHERE user_id=?", (user['id'],)).fetchone()
    ref = dict_row(db.execute("SELECT referral_code FROM referrals WHERE referrer_id=?", (user['id'],)).fetchone()) or {}
    unread = db.execute("SELECT COUNT(*) as c FROM notifications WHERE user_id=? AND is_read=0", (user['id'],)).fetchone()['c']
    return jsonify({
        'id': user['id'], 'name': user['name'], 'mobile_number': user['mobile_number'],
        'email': user['email'], 'role': user['role'],
        'profile': profile, 'wallet_balance': wallet['balance'],
        'loyalty_points': points['total'], 'referral_code': ref.get('referral_code',''),
        'unread_notifications': unread
    })

@app.route('/api/auth/update-profile', methods=['PUT'])
@token_required
def update_profile(user):
    d = request.json or {}
    db = get_db()
    if d.get('name'): db.execute("UPDATE users SET name=? WHERE id=?", (sanitize(d['name']), user['id']))
    if d.get('email'): db.execute("UPDATE users SET email=? WHERE id=?", (sanitize(d['email']), user['id']))
    profile_fields = {k: sanitize(d[k]) for k in ['dob','gender','photo_url'] if k in d}
    if profile_fields:
        sets = ', '.join(f"{k}=?" for k in profile_fields)
        vals = list(profile_fields.values()) + [user['id']]
        db.execute(f"UPDATE profiles SET {sets} WHERE user_id=?", vals)
    db.commit()
    return jsonify({'message': 'Profile updated'})

@app.route('/api/auth/change-password', methods=['PUT'])
@token_required
def change_password(user):
    d = request.json or {}
    if not check_password(d.get('current_password',''), user['password_hash']):
        return jsonify({'error': 'Current password incorrect'}), 400
    if len(d.get('new_password','')) < 6:
        return jsonify({'error': 'New password must be at least 6 characters'}), 400
    get_db().execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(d['new_password']), user['id']))
    get_db().commit()
    return jsonify({'message': 'Password changed'})

# ─── CATEGORIES ──────────────────────────────────────────────────────────────
@app.route('/api/categories', methods=['GET'])
def get_categories():
    cats = dict_rows(get_db().execute("SELECT * FROM categories ORDER BY sort_order").fetchall())
    return jsonify(cats)

# ─── PRODUCTS ────────────────────────────────────────────────────────────────
@app.route('/api/products', methods=['GET'])
def get_products():
    db = get_db()
    q = request.args
    query = "SELECT p.*, c.name as category_name FROM products p LEFT JOIN categories c ON p.category_id=c.id WHERE p.is_active=1"
    params = []
    if q.get('category'):
        query += " AND c.slug=?"; params.append(q['category'])
    search_term = q.get('search') or q.get('q')
    if search_term:
        query += " AND (p.name LIKE ? OR p.description LIKE ? OR p.brand LIKE ?)"
        s = f"%{search_term}%"; params += [s,s,s]
    if q.get('min_price'):
        query += " AND COALESCE(p.sale_price,p.base_price)>=?"; params.append(float(q['min_price']))
    if q.get('max_price'):
        query += " AND COALESCE(p.sale_price,p.base_price)<=?"; params.append(float(q['max_price']))
    if q.get('brand'):
        query += " AND p.brand=?"; params.append(q['brand'])
    if q.get('size'):
        query += " AND EXISTS (SELECT 1 FROM product_variants pv WHERE pv.product_id = p.id AND pv.size = ? AND pv.stock > 0)"; params.append(q['size'])
    if q.get('color'):
        query += " AND EXISTS (SELECT 1 FROM product_variants pv WHERE pv.product_id = p.id AND pv.color = ? AND pv.stock > 0)"; params.append(q['color'])
    if q.get('min_rating'):
        query += " AND (SELECT AVG(rating) FROM reviews r WHERE r.product_id = p.id AND r.is_approved=1) >= ?"; params.append(float(q['min_rating']))
    sort = q.get('sort','newest')
    order_clause = ""
    if sort == 'price_low': order_clause = " ORDER BY COALESCE(p.sale_price,p.base_price) ASC"
    elif sort == 'price_high': order_clause = " ORDER BY COALESCE(p.sale_price,p.base_price) DESC"
    elif sort == 'popular': order_clause = " ORDER BY p.is_featured DESC, p.id DESC"
    else: order_clause = " ORDER BY p.created_at DESC"
    page = int(q.get('page', 1)); per_page = int(q.get('per_page', 20))
    offset = (page - 1) * per_page
    count_q = query.replace("SELECT p.*, c.name as category_name", "SELECT COUNT(*) as total", 1)
    total = db.execute(count_q, params).fetchone()['total']
    query += order_clause + " LIMIT ? OFFSET ?"; params += [per_page, offset]
    products = dict_rows(db.execute(query, params).fetchall())
    for p in products:
        avg = db.execute("SELECT AVG(rating) as avg_rating, COUNT(*) as count FROM reviews WHERE product_id=? AND is_approved=1", (p['id'],)).fetchone()
        p['avg_rating'] = round(avg['avg_rating'],1) if avg['avg_rating'] else 0
        p['review_count'] = avg['count']
        p['price'] = p['sale_price'] or p['base_price']
        p['discount'] = round((1 - (p['sale_price'] or p['base_price'])/p['base_price'])*100) if p['sale_price'] and p['sale_price'] < p['base_price'] else 0
    return jsonify({'products': products, 'total': total, 'page': page, 'pages': math.ceil(total/per_page)})

@app.route('/api/products/<slug>', methods=['GET'])
def get_product_detail(slug):
    db = get_db()
    p = dict_row(db.execute("SELECT p.*, c.name as category_name FROM products p LEFT JOIN categories c ON p.category_id=c.id WHERE p.slug=? AND p.is_active=1", (slug,)).fetchone())
    if not p: return jsonify({'error': 'Product not found'}), 404
    p['variants'] = dict_rows(db.execute("SELECT * FROM product_variants WHERE product_id=?", (p['id'],)).fetchall())
    p['images'] = dict_rows(db.execute("SELECT image_url, is_primary FROM product_images WHERE product_id=? ORDER BY is_primary DESC", (p['id'],)).fetchall())
    p['reviews'] = dict_rows(db.execute("SELECT r.*, u.name as user_name FROM reviews r JOIN users u ON r.user_id=u.id WHERE r.product_id=? AND r.is_approved=1 ORDER BY r.created_at DESC LIMIT 10", (p['id'],)).fetchall())
    avg = db.execute("SELECT AVG(rating) as avg_rating, COUNT(*) as count FROM reviews WHERE product_id=? AND is_approved=1", (p['id'],)).fetchone()
    p['avg_rating'] = round(avg['avg_rating'],1) if avg['avg_rating'] else 0
    p['review_count'] = avg['count']
    p['price'] = p['sale_price'] or p['base_price']
    p['discount'] = round((1 - (p['sale_price'] or p['base_price'])/p['base_price'])*100) if p['sale_price'] and p['sale_price'] < p['base_price'] else 0
    related = dict_rows(db.execute("SELECT * FROM products WHERE category_id=? AND id!=? AND is_active=1 LIMIT 4", (p['category_id'], p['id'])).fetchall())
    p['related'] = related
    return jsonify(p)



# ─── WISHLIST ────────────────────────────────────────────────────────────────
@app.route('/api/wishlist', methods=['GET'])
@token_required
def get_wishlist(user):
    items = dict_rows(get_db().execute("""SELECT w.id, w.product_id, p.name, p.slug, p.image_url,
        COALESCE(p.sale_price,p.base_price) as price, p.base_price
        FROM wishlist w JOIN products p ON w.product_id=p.id WHERE w.user_id=? ORDER BY w.created_at DESC""", (user['id'],)).fetchall())
    return jsonify(items)

@app.route('/api/wishlist', methods=['POST'])
@token_required
def add_wishlist(user):
    pid = (request.json or {}).get('product_id')
    if not pid: return jsonify({'error': 'product_id required'}), 400
    db = get_db()
    try:
        db.execute("INSERT INTO wishlist (user_id, product_id) VALUES (?,?)", (user['id'], pid))
        db.commit()
    except Exception:
        pass
    return jsonify({'message': 'Added to wishlist'})

@app.route('/api/wishlist/<int:pid>', methods=['DELETE'])
@token_required
def remove_wishlist(user, pid):
    get_db().execute("DELETE FROM wishlist WHERE user_id=? AND product_id=?", (user['id'], pid))
    get_db().commit()
    return jsonify({'message': 'Removed from wishlist'})

# ─── CART ────────────────────────────────────────────────────────────────────
@app.route('/api/cart', methods=['GET'])
@token_required
def get_cart(user):
    items = dict_rows(get_db().execute("""SELECT c.id, c.product_id, c.variant_id, c.quantity, c.saved_for_later,
        p.name, p.slug, p.image_url, COALESCE(p.sale_price,p.base_price) as price, p.base_price,
        pv.size, pv.color
        FROM cart c JOIN products p ON c.product_id=p.id
        LEFT JOIN product_variants pv ON c.variant_id=pv.id
        WHERE c.user_id=? ORDER BY c.saved_for_later, c.id DESC""", (user['id'],)).fetchall())
    return jsonify(items)

@app.route('/api/cart', methods=['POST'])
@token_required
def add_to_cart(user):
    d = request.json or {}
    pid = d.get('product_id'); vid = d.get('variant_id'); qty = d.get('quantity', 1)
    if not pid: return jsonify({'error': 'product_id required'}), 400
    db = get_db()
    if vid:
        v = db.execute("SELECT stock FROM product_variants WHERE id=?", (vid,)).fetchone()
        if not v or v['stock'] < qty:
            return jsonify({'error': 'Out of stock for selected variant'}), 400
    existing = db.execute("SELECT * FROM cart WHERE user_id=? AND product_id=? AND (variant_id=? OR (variant_id IS NULL AND ? IS NULL)) AND saved_for_later=0",
                          (user['id'], pid, vid, vid)).fetchone()
    if existing:
        db.execute("UPDATE cart SET quantity=quantity+? WHERE id=?", (qty, existing['id']))
    else:
        db.execute("INSERT INTO cart (user_id,product_id,variant_id,quantity) VALUES (?,?,?,?)", (user['id'], pid, vid, qty))
    db.commit()
    return jsonify({'message': 'Added to cart'})

@app.route('/api/cart/<int:cart_id>', methods=['PUT'])
@token_required
def update_cart(user, cart_id):
    d = request.json or {}
    db = get_db()
    if 'quantity' in d:
        if d['quantity'] <= 0:
            db.execute("DELETE FROM cart WHERE id=? AND user_id=?", (cart_id, user['id']))
        else:
            db.execute("UPDATE cart SET quantity=? WHERE id=? AND user_id=?", (d['quantity'], cart_id, user['id']))
    if 'saved_for_later' in d:
        db.execute("UPDATE cart SET saved_for_later=? WHERE id=? AND user_id=?", (d['saved_for_later'], cart_id, user['id']))
    db.commit()
    return jsonify({'message': 'Cart updated'})

@app.route('/api/cart/<int:cart_id>', methods=['DELETE'])
@token_required
def remove_cart(user, cart_id):
    get_db().execute("DELETE FROM cart WHERE id=? AND user_id=?", (cart_id, user['id']))
    get_db().commit()
    return jsonify({'message': 'Removed from cart'})

# ─── ADDRESSES ───────────────────────────────────────────────────────────────
@app.route('/api/addresses', methods=['GET'])
@token_required
def get_addresses(user):
    return jsonify(dict_rows(get_db().execute("SELECT * FROM addresses WHERE user_id=?", (user['id'],)).fetchall()))

@app.route('/api/addresses', methods=['POST'])
@token_required
def add_address(user):
    d = request.json or {}
    required = ['full_name','phone','line1','city','state','pincode']
    for r in required:
        if not d.get(r): return jsonify({'error': f'{r} is required'}), 400
    db = get_db()
    if d.get('is_default'):
        db.execute("UPDATE addresses SET is_default=0 WHERE user_id=?", (user['id'],))
    db.execute("""INSERT INTO addresses (user_id,label,full_name,phone,line1,line2,city,state,pincode,is_default)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (user['id'], d.get('label','Home'), sanitize(d['full_name']), sanitize(d['phone']),
         sanitize(d['line1']), sanitize(d.get('line2','')), sanitize(d['city']),
         sanitize(d['state']), sanitize(d['pincode']), 1 if d.get('is_default') else 0))
    db.commit()
    return jsonify({'message': 'Address added'}), 201

@app.route('/api/addresses/<int:aid>', methods=['PUT'])
@token_required
def update_address(user, aid):
    d = request.json or {}
    db = get_db()
    if d.get('is_default'):
        db.execute("UPDATE addresses SET is_default=0 WHERE user_id=?", (user['id'],))
    fields = {k: sanitize(d[k]) for k in ['label','full_name','phone','line1','line2','city','state','pincode','is_default'] if k in d}
    if fields:
        sets = ', '.join(f"{k}=?" for k in fields)
        db.execute(f"UPDATE addresses SET {sets} WHERE id=? AND user_id=?", list(fields.values()) + [aid, user['id']])
    db.commit()
    return jsonify({'message': 'Address updated'})

@app.route('/api/addresses/<int:aid>', methods=['DELETE'])
@token_required
def delete_address(user, aid):
    get_db().execute("DELETE FROM addresses WHERE id=? AND user_id=?", (aid, user['id']))
    get_db().commit()
    return jsonify({'message': 'Address deleted'})

# ─── COUPONS ─────────────────────────────────────────────────────────────────
@app.route('/api/coupons/validate', methods=['POST'])
@token_required
def validate_coupon(user):
    code = (request.json or {}).get('code','').upper()
    db = get_db()
    c = dict_row(db.execute("SELECT * FROM coupons WHERE code=? AND is_active=1", (code,)).fetchone())
    if not c: return jsonify({'error': 'Invalid coupon code'}), 404
    if c['used_count'] >= c['usage_limit']:
        return jsonify({'error': 'Coupon usage limit reached'}), 400
    if c['expires_at'] and c['expires_at'] < datetime.datetime.now().isoformat():
        return jsonify({'error': 'Coupon expired'}), 400
    return jsonify({'coupon': c})

# ─── RAZORPAY ────────────────────────────────────────────────────────────────
@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify({'razorpay_key_id': RAZORPAY_KEY_ID, 'currency': 'INR', 'company_name': 'LUXE Fashion'})

@app.route('/api/razorpay/create-order', methods=['POST'])
@token_required
def razorpay_create_order(user):
    d = request.json or {}
    db = get_db()
    items = dict_rows(db.execute("""SELECT c.*, COALESCE(p.sale_price,p.base_price) as price, p.name as product_name
        FROM cart c JOIN products p ON c.product_id=p.id WHERE c.user_id=? AND c.saved_for_later=0""", (user['id'],)).fetchall())
    if not items: return jsonify({'error': 'Cart is empty'}), 400
    subtotal = sum(i['price'] * i['quantity'] for i in items)
    discount = 0
    coupon_code = d.get('coupon_code','').upper()
    if coupon_code:
        c = db.execute("SELECT * FROM coupons WHERE code=? AND is_active=1 AND used_count<usage_limit", (coupon_code,)).fetchone()
        if c and subtotal >= c['min_order']:
            if c['discount_type'] == 'percentage':
                discount = min(subtotal * c['discount_value'] / 100, c['max_discount'] or 99999)
            else:
                discount = c['discount_value']
    shipping = 0 if subtotal >= 999 else 99
    total = max(subtotal - discount + shipping, 1)
    amount_paise = int(total * 100)
    try:
        rz_order = razorpay_client.order.create({
            'amount': amount_paise, 'currency': 'INR',
            'receipt': 'LUXE' + secrets.token_hex(4).upper(),
            'notes': {'user_id': str(user['id']), 'coupon': coupon_code}
        })
        return jsonify({'order_id': rz_order['id'], 'amount': amount_paise, 'currency': 'INR',
                        'key_id': RAZORPAY_KEY_ID, 'subtotal': subtotal, 'discount': discount, 'shipping': shipping, 'total': total})
    except Exception as e:
        return jsonify({'error': f'Razorpay error: {str(e)}'}), 500

@app.route('/api/razorpay/verify-payment', methods=['POST'])
@token_required
def razorpay_verify_payment(user):
    d = request.json or {}
    rz_order_id = d.get('razorpay_order_id', '')
    rz_payment_id = d.get('razorpay_payment_id', '')
    rz_signature = d.get('razorpay_signature', '')
    if not rz_order_id or not rz_payment_id or not rz_signature:
        return jsonify({'error': 'Missing payment details'}), 400
    # Verify signature using HMAC SHA256
    msg = f"{rz_order_id}|{rz_payment_id}"
    generated_sig = hmac.HMAC(RAZORPAY_KEY_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    if generated_sig != rz_signature:
        try:
            razorpay_client.utility.verify_payment_signature({
                'razorpay_order_id': rz_order_id, 'razorpay_payment_id': rz_payment_id, 'razorpay_signature': rz_signature
            })
        except:
            return jsonify({'error': 'Payment verification failed'}), 400
    return jsonify({'verified': True, 'payment_id': rz_payment_id})

# ─── ORDERS & CHECKOUT ──────────────────────────────────────────────────────
@app.route('/api/checkout', methods=['POST'])
@token_required
def checkout(user):
    d = request.json or {}
    db = get_db()
    items = dict_rows(db.execute("""SELECT c.*, COALESCE(p.sale_price,p.base_price) as price, p.name as product_name, p.image_url as product_image,
        pv.size, pv.color, pv.stock
        FROM cart c JOIN products p ON c.product_id=p.id LEFT JOIN product_variants pv ON c.variant_id=pv.id
        WHERE c.user_id=? AND c.saved_for_later=0""", (user['id'],)).fetchall())
    if not items: return jsonify({'error': 'Cart is empty'}), 400
    for item in items:
        if item.get('variant_id') and item.get('stock') is not None and item['stock'] < item['quantity']:
            return jsonify({'error': f"{item['product_name']} ({item.get('size','')}) is out of stock"}), 400
    subtotal = sum(i['price'] * i['quantity'] for i in items)
    discount = 0
    coupon_code = d.get('coupon_code','').upper()
    if coupon_code:
        c = db.execute("SELECT * FROM coupons WHERE code=? AND is_active=1 AND used_count<usage_limit", (coupon_code,)).fetchone()
        if c:
            if subtotal >= c['min_order']:
                if c['discount_type'] == 'percentage':
                    discount = min(subtotal * c['discount_value'] / 100, c['max_discount'] or 99999)
                else:
                    discount = c['discount_value']
                db.execute("UPDATE coupons SET used_count=used_count+1 WHERE id=?", (c['id'],))
    shipping = 0 if subtotal >= 999 else 99
    total = subtotal - discount + shipping
    wallet_used = 0
    if d.get('use_wallet'):
        w = db.execute("SELECT balance FROM wallets WHERE user_id=?", (user['id'],)).fetchone()
        if w and w['balance'] > 0:
            wallet_used = min(w['balance'], total)
            total -= wallet_used
            db.execute("UPDATE wallets SET balance=balance-? WHERE user_id=?", (wallet_used, user['id']))
            db.execute("INSERT INTO wallet_transactions (user_id,amount,type,description) VALUES (?,?,?,?)",
                       (user['id'], wallet_used, 'debit', 'Used for order'))
    points_used = int(d.get('redeem_points', 0))
    if points_used > 0:
        available = db.execute("SELECT COALESCE(SUM(CASE WHEN type='earn' THEN points ELSE -points END),0) as t FROM loyalty_points WHERE user_id=?", (user['id'],)).fetchone()['t']
        points_used = min(points_used, available, int(total))
        if points_used > 0:
            total -= points_used
            db.execute("INSERT INTO loyalty_points (user_id,points,type,description) VALUES (?,?,?,?)",
                       (user['id'], points_used, 'redeem', 'Redeemed for order'))
    order_num = 'LUXE' + datetime.datetime.now().strftime('%y%m%d') + secrets.token_hex(3).upper()
    payment_method = d.get('payment_method', 'COD')
    address_id = d.get('address_id')
    if not address_id:
        return jsonify({'error': 'Please select a delivery address'}), 400
    razorpay_payment_id = d.get('razorpay_payment_id', '')
    razorpay_order_id = d.get('razorpay_order_id', '')
    razorpay_signature = d.get('razorpay_signature', '')
    
    if payment_method != 'COD':
        if not razorpay_payment_id or not razorpay_order_id or not razorpay_signature:
            return jsonify({'error': 'Incomplete payment details'}), 400
        msg = f"{razorpay_order_id}|{razorpay_payment_id}"
        generated_sig = hmac.HMAC(RAZORPAY_KEY_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
        if generated_sig != razorpay_signature:
            return jsonify({'error': 'Payment verification failed (tampered)'}), 400

    status = 'CONFIRMED'
    cur = db.execute("""INSERT INTO orders (order_number,user_id,address_id,subtotal,discount,shipping,total,status,payment_method,payment_id,razorpay_order_id,coupon_code)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (order_num, user['id'], address_id, subtotal, discount, shipping, max(total,0),
         status, payment_method, razorpay_payment_id, razorpay_order_id, coupon_code or None))
    oid = cur.lastrowid
    for item in items:
        db.execute("""INSERT INTO order_items (order_id,product_id,variant_id,product_name,product_image,size,color,price,quantity)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (oid, item['product_id'], item.get('variant_id'), item['product_name'], item['product_image'],
             item.get('size',''), item.get('color',''), item['price'], item['quantity']))
        if item.get('variant_id'):
            db.execute("UPDATE product_variants SET stock=stock-? WHERE id=?", (item['quantity'], item['variant_id']))
            db.execute("INSERT INTO inventory_logs (variant_id,change,reason) VALUES (?,?,?)",
                       (item['variant_id'], -item['quantity'], f'Order {order_num}'))
    db.execute("DELETE FROM cart WHERE user_id=? AND saved_for_later=0", (user['id'],))
    earned = int(subtotal / 10)
    if earned > 0:
        db.execute("INSERT INTO loyalty_points (user_id,points,type,description) VALUES (?,?,?,?)",
                   (user['id'], earned, 'earn', f'Order {order_num}'))
    notify(user['id'], 'Order Placed!', f'Your order {order_num} has been placed successfully. Total: Rs.{max(total,0):.0f}', 'order')
    db.commit()
    return jsonify({'message': 'Order placed!', 'order_number': order_num, 'total': max(total,0), 'order_id': oid})

@app.route('/api/orders', methods=['GET'])
@token_required
def get_orders(user):
    db = get_db()
    orders = dict_rows(db.execute("SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC", (user['id'],)).fetchall())
    for o in orders:
        o['items'] = dict_rows(db.execute("SELECT * FROM order_items WHERE order_id=?", (o['id'],)).fetchall())
    return jsonify(orders)

@app.route('/api/orders/<order_num>', methods=['GET'])
@token_required
def get_order_detail(user, order_num):
    db = get_db()
    o = dict_row(db.execute("SELECT * FROM orders WHERE order_number=? AND user_id=?", (order_num, user['id'])).fetchone())
    if not o: return jsonify({'error': 'Order not found'}), 404
    o['items'] = dict_rows(db.execute("SELECT * FROM order_items WHERE order_id=?", (o['id'],)).fetchall())
    addr = dict_row(db.execute("SELECT * FROM addresses WHERE id=?", (o['address_id'],)).fetchone()) if o['address_id'] else None
    o['address'] = addr
    return jsonify(o)

@app.route('/api/orders/<order_num>/invoice', methods=['GET'])
@token_required
def get_order_invoice(user, order_num):
    db = get_db()
    o = dict_row(db.execute("SELECT * FROM orders WHERE order_number=? AND user_id=?", (order_num, user['id'])).fetchone())
    if not o or o['status'] not in ('CONFIRMED', 'SHIPPED', 'DELIVERED'): 
        return jsonify({'error': 'Invoice not available for this order'}), 400
        
    items = dict_rows(db.execute("SELECT * FROM order_items WHERE order_id=?", (o['id'],)).fetchall())
    addr = dict_row(db.execute("SELECT * FROM addresses WHERE id=?", (o['address_id'],)).fetchone()) if o['address_id'] else {}
    
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 20)
    p.drawString(50, 750, "LUXE Fashion Invoice")
    
    p.setFont("Helvetica", 12)
    p.drawString(50, 720, f"Order Number: {o['order_number']}")
    p.drawString(50, 700, f"Date: {o['created_at']}")
    p.drawString(50, 680, f"Status: {o['status']}")
    
    if addr:
        p.drawString(350, 720, "Billing / Shipping Address:")
        p.drawString(350, 700, f"{addr.get('full_name', '')}")
        p.drawString(350, 680, f"{addr.get('line1', '')}, {addr.get('city', '')}")
        p.drawString(350, 660, f"{addr.get('state', '')} - {addr.get('pincode', '')}")
    
    p.line(50, 640, 550, 640)
    p.drawString(50, 620, "Item")
    p.drawString(300, 620, "Qty")
    p.drawString(400, 620, "Price")
    p.drawString(480, 620, "Total")
    p.line(50, 610, 550, 610)
    
    y = 590
    for item in items:
        p.drawString(50, y, f"{item['product_name'][:30]} ({item.get('size','')}, {item.get('color','')})")
        p.drawString(300, y, str(item['quantity']))
        p.drawString(400, y, f"INR {item['price']}")
        p.drawString(480, y, f"INR {item['price'] * item['quantity']}")
        y -= 20
        if y < 100:
            p.showPage()
            p.setFont("Helvetica", 12)
            y = 750
            
    p.line(50, y, 550, y)
    y -= 20
    p.drawString(350, y, f"Subtotal: INR {o['subtotal']}")
    y -= 20
    p.drawString(350, y, f"Discount: INR {o['discount']}")
    y -= 20
    p.drawString(350, y, f"Shipping: INR {o['shipping']}")
    y -= 20
    p.setFont("Helvetica-Bold", 14)
    p.drawString(350, y, f"Grand Total: INR {o['total']}")
    
    p.showPage()
    p.save()
    
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"Invoice_{o['order_number']}.pdf", mimetype='application/pdf')

@app.route('/api/orders/<order_num>/cancel', methods=['PUT'])
@token_required
def cancel_order(user, order_num):
    db = get_db()
    o = db.execute("SELECT * FROM orders WHERE order_number=? AND user_id=? AND status IN ('PENDING','CONFIRMED')", (order_num, user['id'])).fetchone()
    if not o: return jsonify({'error': 'Cannot cancel this order'}), 400
    db.execute("UPDATE orders SET status='CANCELLED', updated_at=CURRENT_TIMESTAMP WHERE id=?", (o['id'],))
    items = db.execute("SELECT * FROM order_items WHERE order_id=?", (o['id'],)).fetchall()
    for item in items:
        if item['variant_id']:
            db.execute("UPDATE product_variants SET stock=stock+? WHERE id=?", (item['quantity'], item['variant_id']))
            db.execute("INSERT INTO inventory_logs (variant_id,change,reason) VALUES (?,?,?)",
                       (item['variant_id'], item['quantity'], f'Cancelled order {order_num}'))
    if o['payment_method'] != 'COD':
        db.execute("UPDATE wallets SET balance=balance+? WHERE user_id=?", (o['total'], user['id']))
        db.execute("INSERT INTO wallet_transactions (user_id,amount,type,description) VALUES (?,?,?,?)",
                   (user['id'], o['total'], 'credit', f'Refund for order {order_num}'))
    notify(user['id'], 'Order Cancelled', f'Order {order_num} has been cancelled.', 'order')
    db.commit()
    return jsonify({'message': 'Order cancelled'})

# ─── REVIEWS ─────────────────────────────────────────────────────────────────
@app.route('/api/reviews', methods=['POST'])
@token_required
def add_review(user):
    d = request.json or {}
    pid = d.get('product_id'); rating = d.get('rating')
    if not pid or not rating: return jsonify({'error': 'product_id and rating required'}), 400
    db = get_db()
    bought = db.execute("SELECT 1 FROM order_items oi JOIN orders o ON oi.order_id=o.id WHERE o.user_id=? AND oi.product_id=? AND o.status='DELIVERED'",
                        (user['id'], pid)).fetchone()
    if not bought: return jsonify({'error': 'Only verified buyers can review'}), 403
    existing = db.execute("SELECT id FROM reviews WHERE user_id=? AND product_id=?", (user['id'], pid)).fetchone()
    if existing: return jsonify({'error': 'You already reviewed this product'}), 409
    photo_url = sanitize(d.get('photo_url', ''))
    images = json.dumps([photo_url]) if photo_url else '[]'
    db.execute("INSERT INTO reviews (user_id,product_id,rating,title,body,images) VALUES (?,?,?,?,?,?)",
               (user['id'], pid, rating, sanitize(d.get('title','')), sanitize(d.get('body','')), images))
    db.execute("INSERT INTO loyalty_points (user_id,points,type,description) VALUES (?,?,?,?)",
               (user['id'], 10, 'earn', 'Review submitted'))
    db.commit()
    return jsonify({'message': 'Review submitted for approval'}), 201

# ─── NOTIFICATIONS ───────────────────────────────────────────────────────────
@app.route('/api/notifications', methods=['GET'])
@token_required
def get_notifications(user):
    notes = dict_rows(get_db().execute("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 50", (user['id'],)).fetchall())
    return jsonify(notes)

@app.route('/api/notifications/read-all', methods=['PUT'])
@token_required
def mark_all_read(user):
    get_db().execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (user['id'],))
    get_db().commit()
    return jsonify({'message': 'All marked as read'})

# ─── WALLET & LOYALTY ────────────────────────────────────────────────────────
@app.route('/api/wallet', methods=['GET'])
@token_required
def get_wallet(user):
    db = get_db()
    w = dict_row(db.execute("SELECT balance FROM wallets WHERE user_id=?", (user['id'],)).fetchone()) or {'balance':0}
    txns = dict_rows(db.execute("SELECT * FROM wallet_transactions WHERE user_id=? ORDER BY created_at DESC LIMIT 20", (user['id'],)).fetchall())
    return jsonify({'balance': w['balance'], 'transactions': txns})

@app.route('/api/loyalty', methods=['GET'])
@token_required
def get_loyalty(user):
    db = get_db()
    points = db.execute("SELECT COALESCE(SUM(CASE WHEN type='earn' THEN points ELSE -points END),0) as total FROM loyalty_points WHERE user_id=?", (user['id'],)).fetchone()['total']
    history = dict_rows(db.execute("SELECT * FROM loyalty_points WHERE user_id=? ORDER BY created_at DESC LIMIT 20", (user['id'],)).fetchall())
    return jsonify({'total_points': points, 'history': history})

# ─── SUPPORT ─────────────────────────────────────────────────────────────────
@app.route('/api/support', methods=['GET'])
@token_required
def get_tickets(user):
    return jsonify(dict_rows(get_db().execute("SELECT * FROM support_tickets WHERE user_id=? ORDER BY created_at DESC", (user['id'],)).fetchall()))

@app.route('/api/support', methods=['POST'])
@token_required
def create_ticket(user):
    d = request.json or {}
    if not d.get('subject') or not d.get('message'): return jsonify({'error': 'Subject and message required'}), 400
    get_db().execute("INSERT INTO support_tickets (user_id,subject,message) VALUES (?,?,?)",
                     (user['id'], sanitize(d['subject']), sanitize(d['message'])))
    get_db().commit()
    return jsonify({'message': 'Ticket created'}), 201

# ─── BLOG ────────────────────────────────────────────────────────────────────
@app.route('/api/blog', methods=['GET'])
def get_blog_posts():
    posts = dict_rows(get_db().execute("SELECT bp.*, u.name as author FROM blog_posts bp LEFT JOIN users u ON bp.author_id=u.id WHERE bp.is_published=1 ORDER BY bp.created_at DESC").fetchall())
    return jsonify(posts)

@app.route('/api/blog/<slug>', methods=['GET'])
def get_blog_post(slug):
    p = dict_row(get_db().execute("SELECT bp.*, u.name as author FROM blog_posts bp LEFT JOIN users u ON bp.author_id=u.id WHERE bp.slug=? AND bp.is_published=1", (slug,)).fetchone())
    if not p: return jsonify({'error': 'Post not found'}), 404
    return jsonify(p)

# ─── BANNERS ─────────────────────────────────────────────────────────────────
@app.route('/api/banners', methods=['GET'])
def get_banners():
    return jsonify(dict_rows(get_db().execute("SELECT * FROM banners WHERE is_active=1 ORDER BY sort_order").fetchall()))

# ─── PUBLIC STATS ────────────────────────────────────────────────────────────
@app.route('/api/stats', methods=['GET'])
def get_public_stats():
    db = get_db()
    customers = db.execute("SELECT COUNT(*) as v FROM users WHERE role='customer'").fetchone()['v']
    products = db.execute("SELECT COUNT(*) as v FROM products WHERE is_active=1").fetchone()['v']
    brands = db.execute("SELECT COUNT(DISTINCT brand) as v FROM products WHERE is_active=1 AND brand IS NOT NULL AND brand != ''").fetchone()['v']
    avg_rating_row = db.execute("SELECT AVG(rating) as v FROM reviews WHERE is_approved=1").fetchone()
    avg_rating = round(avg_rating_row['v'], 1) if avg_rating_row['v'] else 4.8
    orders_delivered = db.execute("SELECT COUNT(*) as v FROM orders WHERE status='DELIVERED'").fetchone()['v']
    return jsonify({
        'happy_customers': max(customers, orders_delivered),
        'total_products': products,
        'total_brands': max(brands, 1),
        'avg_rating': avg_rating
    })

# ─── ORDER TRACKING ──────────────────────────────────────────────────────────
@app.route('/api/orders/<order_num>/tracking', methods=['GET'])
@token_required
def get_order_tracking(user, order_num):
    db = get_db()
    order = db.execute("SELECT id, user_id FROM orders WHERE order_number=?", (order_num,)).fetchone()
    if not order: return jsonify({'error': 'Order not found'}), 404
    if order['user_id'] != user['id'] and user['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    tracking = dict_rows(db.execute("SELECT * FROM order_tracking WHERE order_id=? ORDER BY created_at ASC", (order['id'],)).fetchall())
    return jsonify(tracking)

# ─── SUPPORT TICKET CHAT ────────────────────────────────────────────────────
@app.route('/api/support/<int:tid>/messages', methods=['GET'])
@token_required
def get_ticket_messages(user, tid):
    db = get_db()
    ticket = db.execute("SELECT * FROM support_tickets WHERE id=? AND user_id=?", (tid, user['id'])).fetchone()
    if not ticket: return jsonify({'error': 'Ticket not found'}), 404
    messages = dict_rows(db.execute("SELECT tm.*, CASE WHEN tm.sender_type='admin' THEN 'LUXE Support' ELSE u.name END as sender_name FROM ticket_messages tm LEFT JOIN users u ON tm.sender_id=u.id WHERE tm.ticket_id=? ORDER BY tm.created_at ASC", (tid,)).fetchall())
    return jsonify({'ticket': dict_row(ticket), 'messages': messages})

@app.route('/api/support/<int:tid>/messages', methods=['POST'])
@token_required
def send_ticket_message(user, tid):
    d = request.json or {}
    msg = sanitize(d.get('message', ''))
    if not msg: return jsonify({'error': 'Message required'}), 400
    db = get_db()
    ticket = db.execute("SELECT * FROM support_tickets WHERE id=? AND user_id=?", (tid, user['id'])).fetchone()
    if not ticket: return jsonify({'error': 'Ticket not found'}), 404
    db.execute("INSERT INTO ticket_messages (ticket_id, sender_type, sender_id, message) VALUES (?,?,?,?)",
               (tid, 'user', user['id'], msg))
    if ticket['status'] == 'resolved' or ticket['status'] == 'closed':
        db.execute("UPDATE support_tickets SET status='open' WHERE id=?", (tid,))
    db.commit()
    return jsonify({'message': 'Message sent'}), 201

@app.route('/api/admin/tickets/<int:tid>/messages', methods=['POST'])
@admin_required
def admin_send_ticket_message(admin, tid):
    d = request.json or {}
    msg = sanitize(d.get('message', ''))
    if not msg: return jsonify({'error': 'Message required'}), 400
    db = get_db()
    db.execute("INSERT INTO ticket_messages (ticket_id, sender_type, sender_id, message) VALUES (?,?,?,?)",
               (tid, 'admin', admin['id'], msg))
    ticket = db.execute("SELECT user_id, subject FROM support_tickets WHERE id=?", (tid,)).fetchone()
    if ticket:
        notify(ticket['user_id'], 'New Reply on Support Ticket', f'Your ticket "{ticket["subject"]}" has a new reply.', 'support')
    db.commit()
    return jsonify({'message': 'Reply sent'}), 201

@app.route('/api/admin/tickets/<int:tid>/messages', methods=['GET'])
@admin_required
def admin_get_ticket_messages(admin, tid):
    db = get_db()
    messages = dict_rows(db.execute("SELECT tm.*, CASE WHEN tm.sender_type='admin' THEN 'LUXE Support' ELSE u.name END as sender_name FROM ticket_messages tm LEFT JOIN users u ON tm.sender_id=u.id WHERE tm.ticket_id=? ORDER BY tm.created_at ASC", (tid,)).fetchall())
    ticket = dict_row(db.execute("SELECT st.*, u.name as customer_name FROM support_tickets st JOIN users u ON st.user_id=u.id WHERE st.id=?", (tid,)).fetchone())
    return jsonify({'ticket': ticket, 'messages': messages})

# ─── LUXE CLUB MEMBERSHIP ───────────────────────────────────────────────────
@app.route('/api/luxe-club/status', methods=['GET'])
@token_required
def luxe_club_status(user):
    db = get_db()
    member = dict_row(db.execute("SELECT * FROM luxe_club_members WHERE user_id=? AND is_active=1", (user['id'],)).fetchone())
    return jsonify({'is_member': bool(member), 'membership': member})

@app.route('/api/luxe-club/join', methods=['POST'])
@token_required
def luxe_club_join(user):
    db = get_db()
    existing = db.execute("SELECT id FROM luxe_club_members WHERE user_id=? AND is_active=1", (user['id'],)).fetchone()
    if existing: return jsonify({'error': 'Already a LUXE Club member'}), 400
    if not razorpay_client: return jsonify({'error': 'Payment not configured'}), 500
    try:
        rz_order = razorpay_client.order.create({
            'amount': 49900, 'currency': 'INR',
            'receipt': 'LUXECLUB' + secrets.token_hex(4).upper(),
            'notes': {'user_id': str(user['id']), 'type': 'luxe_club'}
        })
        return jsonify({'order_id': rz_order['id'], 'amount': 49900, 'currency': 'INR', 'key_id': RAZORPAY_KEY_ID})
    except Exception as e:
        return jsonify({'error': f'Payment error: {str(e)}'}), 500

@app.route('/api/luxe-club/verify', methods=['POST'])
@token_required
def luxe_club_verify(user):
    d = request.json or {}
    rz_payment_id = d.get('razorpay_payment_id', '')
    rz_order_id = d.get('razorpay_order_id', '')
    rz_signature = d.get('razorpay_signature', '')
    if not rz_payment_id or not rz_order_id:
        return jsonify({'error': 'Missing payment details'}), 400
    msg = f"{rz_order_id}|{rz_payment_id}"
    generated_sig = hmac.HMAC(RAZORPAY_KEY_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    if generated_sig != rz_signature:
        try:
            razorpay_client.utility.verify_payment_signature({
                'razorpay_order_id': rz_order_id, 'razorpay_payment_id': rz_payment_id, 'razorpay_signature': rz_signature
            })
        except:
            return jsonify({'error': 'Payment verification failed'}), 400
    db = get_db()
    expires = (datetime.datetime.now() + datetime.timedelta(days=365)).isoformat()
    try:
        db.execute("INSERT INTO luxe_club_members (user_id, payment_id, razorpay_order_id, amount, expires_at) VALUES (?,?,?,?,?)",
                   (user['id'], rz_payment_id, rz_order_id, 499, expires))
    except Exception:
        db.execute("UPDATE luxe_club_members SET is_active=1, payment_id=?, razorpay_order_id=?, expires_at=? WHERE user_id=?",
                   (rz_payment_id, rz_order_id, expires, user['id']))
    # Give a welcome coupon
    try:
        club_code = 'LUXECLUB' + secrets.token_hex(2).upper()
        db.execute("INSERT INTO coupons (code,discount_type,discount_value,min_order,max_discount,usage_limit,expires_at) VALUES (?,?,?,?,?,?,?)",
                   (club_code, 'percentage', 15, 999, 1000, 1, expires))
    except Exception: pass
    notify(user['id'], 'Welcome to LUXE Club! 🎉', 'You are now a LUXE Club member. Enjoy exclusive deals and 15% off!', 'reward')
    db.commit()
    return jsonify({'message': 'Welcome to LUXE Club!', 'is_member': True})

# ══════════════════════════════════════════════════════════════════════════════
# ─── ADMIN APIs ──────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/admin/dashboard', methods=['GET'])
@admin_required
def admin_dashboard(admin):
    db = get_db()
    today = datetime.date.today().isoformat()
    stats = {
        'total_revenue': db.execute("SELECT COALESCE(SUM(total),0) as v FROM orders WHERE status NOT IN ('CANCELLED')").fetchone()['v'],
        'total_orders': db.execute("SELECT COUNT(*) as v FROM orders").fetchone()['v'],
        'total_customers': db.execute("SELECT COUNT(*) as v FROM users WHERE role='customer'").fetchone()['v'],
        'total_products': db.execute("SELECT COUNT(*) as v FROM products").fetchone()['v'],
        'pending_orders': db.execute("SELECT COUNT(*) as v FROM orders WHERE status='PENDING'").fetchone()['v'],
        'today_revenue': db.execute("SELECT COALESCE(SUM(total),0) as v FROM orders WHERE DATE(created_at)=? AND status NOT IN ('CANCELLED')", (today,)).fetchone()['v'],
        'today_orders': db.execute("SELECT COUNT(*) as v FROM orders WHERE DATE(created_at)=?", (today,)).fetchone()['v'],
        'low_stock': db.execute("SELECT COUNT(*) as v FROM product_variants WHERE stock<5").fetchone()['v'],
        'pending_reviews': db.execute("SELECT COUNT(*) as v FROM reviews WHERE is_approved=0").fetchone()['v'],
        'open_tickets': db.execute("SELECT COUNT(*) as v FROM support_tickets WHERE status='open'").fetchone()['v'],
    }
    # Revenue last 7 days
    chart = []
    for i in range(6, -1, -1):
        d = (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
        rev = db.execute("SELECT COALESCE(SUM(total),0) as v FROM orders WHERE DATE(created_at)=? AND status NOT IN ('CANCELLED')", (d,)).fetchone()['v']
        cnt = db.execute("SELECT COUNT(*) as v FROM orders WHERE DATE(created_at)=?", (d,)).fetchone()['v']
        chart.append({'date': d, 'revenue': rev, 'orders': cnt})
    stats['chart'] = chart
    # Top products
    stats['top_products'] = dict_rows(db.execute("""SELECT p.name, SUM(oi.quantity) as sold, SUM(oi.price*oi.quantity) as revenue
        FROM order_items oi JOIN products p ON oi.product_id=p.id JOIN orders o ON oi.order_id=o.id WHERE o.status NOT IN ('CANCELLED')
        GROUP BY p.id ORDER BY sold DESC LIMIT 5""").fetchall())
    return jsonify(stats)

@app.route('/api/admin/products', methods=['GET'])
@admin_required
def admin_products(admin):
    db = get_db()
    products = dict_rows(db.execute("SELECT p.*, c.name as category_name FROM products p LEFT JOIN categories c ON p.category_id=c.id ORDER BY p.id DESC").fetchall())
    for p in products:
        p['variants'] = dict_rows(db.execute("SELECT * FROM product_variants WHERE product_id=?", (p['id'],)).fetchall())
        total_stock = sum(v['stock'] for v in p['variants'])
        p['total_stock'] = total_stock
    return jsonify(products)

@app.route('/api/admin/products', methods=['POST'])
@admin_required
def admin_add_product(admin):
    d = request.json or {}
    required = ['name','base_price','category_id']
    for r in required:
        if not d.get(r): return jsonify({'error': f'{r} is required'}), 400
    db = get_db()
    slug = slugify(d['name'])
    existing = db.execute("SELECT id FROM products WHERE slug=?", (slug,)).fetchone()
    if existing: slug += '-' + secrets.token_hex(2)
    cur = db.execute("""INSERT INTO products (name,slug,description,brand,sku,category_id,base_price,sale_price,
        fabric,material,weight,care_instructions,image_url,images,video_url,seo_title,seo_description,is_active,is_featured)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (sanitize(d['name']), slug, sanitize(d.get('description','')), sanitize(d.get('brand','')),
         d.get('sku', 'LX-'+secrets.token_hex(3).upper()), d['category_id'],
         float(d['base_price']), float(d['sale_price']) if d.get('sale_price') else None,
         sanitize(d.get('fabric','')), sanitize(d.get('material','')), d.get('weight',''),
         sanitize(d.get('care_instructions','')), d.get('image_url',''),
         json.dumps(d.get('images',[])), d.get('video_url',''),
         sanitize(d.get('seo_title','')), sanitize(d.get('seo_description','')),
         1 if d.get('is_active',True) else 0, 1 if d.get('is_featured') else 0))
    pid = cur.lastrowid
    for v in d.get('variants', []):
        db.execute("INSERT INTO product_variants (product_id,size,color,color_hex,stock,sku_variant) VALUES (?,?,?,?,?,?)",
                   (pid, v.get('size',''), v.get('color',''), v.get('color_hex',''), int(v.get('stock',0)),
                    v.get('sku_variant', f"LX-{secrets.token_hex(2).upper()}")))
    log_audit(admin['id'], 'product_created', str(pid), d['name'])
    db.commit()
    return jsonify({'message': 'Product created', 'id': pid}), 201

@app.route('/api/admin/products/<int:pid>', methods=['PUT'])
@admin_required
def admin_update_product(admin, pid):
    d = request.json or {}
    db = get_db()
    fields = {}
    for k in ['name','description','brand','sku','category_id','base_price','sale_price','fabric','material',
              'weight','care_instructions','image_url','video_url','seo_title','seo_description','is_active','is_featured']:
        if k in d: fields[k] = d[k]
    if fields:
        sets = ', '.join(f"{k}=?" for k in fields)
        db.execute(f"UPDATE products SET {sets} WHERE id=?", list(fields.values()) + [pid])
    log_audit(admin['id'], 'product_updated', str(pid), json.dumps(fields))
    db.commit()
    return jsonify({'message': 'Product updated'})

@app.route('/api/admin/products/<int:pid>', methods=['DELETE'])
@admin_required
def admin_delete_product(admin, pid):
    db = get_db()
    db.execute("UPDATE products SET is_active=0 WHERE id=?", (pid,))
    log_audit(admin['id'], 'product_deleted', str(pid), '')
    db.commit()
    return jsonify({'message': 'Product deactivated'})

@app.route('/api/admin/variants', methods=['POST'])
@admin_required
def admin_add_variant(admin):
    d = request.json or {}
    db = get_db()
    db.execute("INSERT INTO product_variants (product_id,size,color,color_hex,stock,sku_variant) VALUES (?,?,?,?,?,?)",
               (d['product_id'], d.get('size',''), d.get('color',''), d.get('color_hex',''),
                int(d.get('stock',0)), d.get('sku_variant','')))
    db.commit()
    return jsonify({'message': 'Variant added'}), 201

@app.route('/api/admin/variants/<int:vid>', methods=['PUT'])
@admin_required
def admin_update_variant(admin, vid):
    d = request.json or {}
    db = get_db()
    old = db.execute("SELECT stock FROM product_variants WHERE id=?", (vid,)).fetchone()
    fields = {k: d[k] for k in ['size','color','color_hex','stock','sku_variant','price_override'] if k in d}
    if fields:
        sets = ', '.join(f"{k}=?" for k in fields)
        db.execute(f"UPDATE product_variants SET {sets} WHERE id=?", list(fields.values()) + [vid])
    if 'stock' in d and old:
        change = int(d['stock']) - old['stock']
        if change != 0:
            db.execute("INSERT INTO inventory_logs (variant_id,change,reason,admin_id) VALUES (?,?,?,?)",
                       (vid, change, 'Manual stock update', admin['id']))
    db.commit()
    return jsonify({'message': 'Variant updated'})

@app.route('/api/admin/orders', methods=['GET'])
@admin_required
def admin_orders(admin):
    db = get_db()
    status = request.args.get('status')
    q = """SELECT o.*, u.name as customer_name, u.mobile_number, u.email,
           a.full_name as shipping_name, a.phone as shipping_phone, a.line1, a.line2, a.city, a.state, a.pincode 
           FROM orders o 
           JOIN users u ON o.user_id=u.id
           LEFT JOIN addresses a ON o.address_id=a.id"""
    params = []
    if status: q += " WHERE o.status=?"; params.append(status)
    q += " ORDER BY o.created_at DESC"
    orders = dict_rows(db.execute(q, params).fetchall())
    for o in orders:
        o['items'] = dict_rows(db.execute("SELECT * FROM order_items WHERE order_id=?", (o['id'],)).fetchall())
    return jsonify(orders)

@app.route('/api/admin/orders/<int:oid>/status', methods=['PUT'])
@admin_required
def admin_update_order_status(admin, oid):
    d = request.json or {}
    new_status = d.get('status')
    valid = ['PENDING','CONFIRMED','PACKED','SHIPPED','OUT_FOR_DELIVERY','DELIVERED','CANCELLED','RETURNED','REFUNDED']
    if new_status not in valid: return jsonify({'error': 'Invalid status'}), 400
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    if not order: return jsonify({'error': 'Order not found'}), 404
    db.execute("UPDATE orders SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (new_status, oid))
    # Auto-create tracking entry
    tracking_notes = d.get('notes', '')
    tracking_location = d.get('location', '')
    db.execute("INSERT INTO order_tracking (order_id, status, location, notes) VALUES (?,?,?,?)",
               (oid, new_status, tracking_location, tracking_notes or f'Order status updated to {new_status}'))
    notify(order['user_id'], f'Order {new_status.replace("_"," ").title()}',
           f'Your order {order["order_number"]} is now {new_status.replace("_"," ").lower()}.', 'order')
    if new_status in ('RETURNED','REFUNDED'):
        db.execute("UPDATE wallets SET balance=balance+? WHERE user_id=?", (order['total'], order['user_id']))
        db.execute("INSERT INTO wallet_transactions (user_id,amount,type,description) VALUES (?,?,?,?)",
                   (order['user_id'], order['total'], 'credit', f'Refund for {order["order_number"]}'))
    log_audit(admin['id'], 'order_status_changed', str(oid), f'{order["status"]} -> {new_status}')
    db.commit()
    return jsonify({'message': f'Order status updated to {new_status}'})

@app.route('/api/admin/customers', methods=['GET'])
@admin_required
def admin_customers(admin):
    db = get_db()
    customers = dict_rows(db.execute("""SELECT u.id, u.name, u.mobile_number, u.email, u.is_active, u.created_at,
        COUNT(DISTINCT o.id) as order_count, COALESCE(SUM(o.total),0) as total_spent
        FROM users u LEFT JOIN orders o ON u.id=o.user_id AND o.status NOT IN ('CANCELLED')
        WHERE u.role='customer' GROUP BY u.id ORDER BY u.created_at DESC""").fetchall())
    return jsonify(customers)

@app.route('/api/admin/customers/<int:uid>/toggle', methods=['PUT'])
@admin_required
def admin_toggle_customer(admin, uid):
    db = get_db()
    user = db.execute("SELECT is_active FROM users WHERE id=? AND role='customer'", (uid,)).fetchone()
    if not user: return jsonify({'error': 'User not found'}), 404
    new_status = 0 if user['is_active'] else 1
    db.execute("UPDATE users SET is_active=? WHERE id=?", (new_status, uid))
    log_audit(admin['id'], 'customer_toggled', str(uid), f'Active: {new_status}')
    db.commit()
    return jsonify({'message': f'Customer {"activated" if new_status else "blocked"}'})

@app.route('/api/admin/reviews', methods=['GET'])
@admin_required
def admin_reviews(admin):
    reviews = dict_rows(get_db().execute("""SELECT r.*, u.name as user_name, p.name as product_name
        FROM reviews r JOIN users u ON r.user_id=u.id JOIN products p ON r.product_id=p.id
        ORDER BY r.is_approved ASC, r.created_at DESC""").fetchall())
    return jsonify(reviews)

@app.route('/api/admin/reviews/<int:rid>/approve', methods=['PUT'])
@admin_required
def admin_approve_review(admin, rid):
    get_db().execute("UPDATE reviews SET is_approved=1 WHERE id=?", (rid,))
    get_db().commit()
    return jsonify({'message': 'Review approved'})

@app.route('/api/admin/reviews/<int:rid>', methods=['DELETE'])
@admin_required
def admin_delete_review(admin, rid):
    get_db().execute("DELETE FROM reviews WHERE id=?", (rid,))
    get_db().commit()
    return jsonify({'message': 'Review deleted'})

@app.route('/api/admin/coupons', methods=['GET'])
@admin_required
def admin_coupons(admin):
    return jsonify(dict_rows(get_db().execute("SELECT * FROM coupons ORDER BY created_at DESC").fetchall()))

@app.route('/api/admin/coupons', methods=['POST'])
@admin_required
def admin_add_coupon(admin):
    d = request.json or {}
    db = get_db()
    db.execute("""INSERT INTO coupons (code,discount_type,discount_value,min_order,max_discount,usage_limit,expires_at)
        VALUES (?,?,?,?,?,?,?)""",
        (d['code'].upper(), d.get('discount_type','percentage'), float(d['discount_value']),
         float(d.get('min_order',0)), float(d.get('max_discount',0)) or None,
         int(d.get('usage_limit',100)), d.get('expires_at')))
    log_audit(admin['id'], 'coupon_created', d['code'].upper(), json.dumps(d))
    db.commit()
    return jsonify({'message': 'Coupon created'}), 201

@app.route('/api/admin/coupons/<int:cid>', methods=['PUT'])
@admin_required
def admin_update_coupon(admin, cid):
    d = request.json or {}
    db = get_db()
    fields = {k: d[k] for k in ['code','discount_type','discount_value','min_order','max_discount','usage_limit','is_active','expires_at'] if k in d}
    if fields:
        sets = ', '.join(f"{k}=?" for k in fields)
        db.execute(f"UPDATE coupons SET {sets} WHERE id=?", list(fields.values()) + [cid])
    log_audit(admin['id'], 'coupon_updated', str(cid), json.dumps(d))
    db.commit()
    return jsonify({'message': 'Coupon updated'})

@app.route('/api/admin/coupons/<int:cid>', methods=['DELETE'])
@admin_required
def admin_delete_coupon(admin, cid):
    db = get_db()
    db.execute("DELETE FROM coupons WHERE id=?", (cid,))
    log_audit(admin['id'], 'coupon_deleted', str(cid), '')
    db.commit()
    return jsonify({'message': 'Coupon deleted'})

@app.route('/api/admin/banners', methods=['GET','POST'])
@admin_required
def admin_banners(admin):
    db = get_db()
    if request.method == 'GET':
        return jsonify(dict_rows(db.execute("SELECT * FROM banners ORDER BY sort_order").fetchall()))
    d = request.json or {}
    db.execute("INSERT INTO banners (title,subtitle,image_url,link,sort_order,is_active) VALUES (?,?,?,?,?,?)",
               (d.get('title',''), d.get('subtitle',''), d['image_url'], d.get('link',''), int(d.get('sort_order',0)), 1))
    db.commit()
    return jsonify({'message': 'Banner created'}), 201

@app.route('/api/admin/banners/<int:bid>', methods=['PUT','DELETE'])
@admin_required
def admin_manage_banner(admin, bid):
    db = get_db()
    if request.method == 'DELETE':
        db.execute("DELETE FROM banners WHERE id=?", (bid,))
        db.commit()
        return jsonify({'message': 'Banner deleted'})
    d = request.json or {}
    fields = {k: d[k] for k in ['title','subtitle','image_url','link','sort_order','is_active'] if k in d}
    if fields:
        sets = ', '.join(f"{k}=?" for k in fields)
        db.execute(f"UPDATE banners SET {sets} WHERE id=?", list(fields.values()) + [bid])
    db.commit()
    return jsonify({'message': 'Banner updated'})

@app.route('/api/admin/tickets', methods=['GET'])
@admin_required
def admin_tickets(admin):
    return jsonify(dict_rows(get_db().execute("""SELECT st.*, u.name as customer_name
        FROM support_tickets st JOIN users u ON st.user_id=u.id ORDER BY st.status='open' DESC, st.created_at DESC""").fetchall()))

@app.route('/api/admin/tickets/<int:tid>/reply', methods=['PUT'])
@admin_required
def admin_reply_ticket(admin, tid):
    d = request.json or {}
    db = get_db()
    db.execute("UPDATE support_tickets SET admin_reply=?, status=? WHERE id=?",
               (sanitize(d.get('reply','')), d.get('status','resolved'), tid))
    ticket = db.execute("SELECT user_id, subject FROM support_tickets WHERE id=?", (tid,)).fetchone()
    if ticket:
        notify(ticket['user_id'], 'Support Reply', f'Your ticket "{ticket["subject"]}" has been replied to.', 'support')
    db.commit()
    return jsonify({'message': 'Reply sent'})

@app.route('/api/admin/blog', methods=['GET','POST'])
@admin_required
def admin_blog(admin):
    db = get_db()
    if request.method == 'GET':
        return jsonify(dict_rows(db.execute("SELECT * FROM blog_posts ORDER BY created_at DESC").fetchall()))
    d = request.json or {}
    slug = slugify(d.get('title',''))
    db.execute("""INSERT INTO blog_posts (title,slug,content,excerpt,image_url,category,author_id,is_published)
        VALUES (?,?,?,?,?,?,?,?)""",
        (sanitize(d['title']), slug, d.get('content',''), sanitize(d.get('excerpt','')),
         d.get('image_url',''), d.get('category',''), admin['id'], 1 if d.get('is_published') else 0))
    db.commit()
    return jsonify({'message': 'Post created'}), 201

@app.route('/api/admin/categories', methods=['POST'])
@admin_required
def admin_add_category(admin):
    d = request.json or {}
    db = get_db()
    slug = slugify(d['name'])
    db.execute("INSERT INTO categories (name,slug,image_url,description,sort_order) VALUES (?,?,?,?,?)",
               (sanitize(d['name']), slug, d.get('image_url',''), sanitize(d.get('description','')), int(d.get('sort_order',0))))
    db.commit()
    return jsonify({'message': 'Category created'}), 201

@app.route('/api/admin/inventory', methods=['GET'])
@admin_required
def admin_inventory(admin):
    db = get_db()
    variants = dict_rows(db.execute("""SELECT pv.*, p.name as product_name, p.sku as product_sku
        FROM product_variants pv JOIN products p ON pv.product_id=p.id ORDER BY pv.stock ASC""").fetchall())
    low_stock = [v for v in variants if v['stock'] < 5]
    return jsonify({'variants': variants, 'low_stock': low_stock, 'total_variants': len(variants)})

@app.route('/api/admin/inventory_logs', methods=['GET'])
@admin_required
def admin_inventory_logs(admin):
    db = get_db()
    logs = dict_rows(db.execute("""SELECT il.*, pv.size, pv.color, p.name as product_name 
        FROM inventory_logs il 
        JOIN product_variants pv ON il.variant_id=pv.id 
        JOIN products p ON pv.product_id=p.id 
        ORDER BY il.created_at DESC""").fetchall())
    return jsonify(logs)

@app.route('/api/admin/abandoned_carts', methods=['GET'])
@admin_required
def admin_abandoned_carts(admin):
    db = get_db()
    # Since there's no timestamp on the cart table, we'll consider all active carts grouped by user.
    carts = dict_rows(db.execute("""SELECT c.user_id, u.name, u.email, COUNT(c.id) as items_count, SUM(p.sale_price * c.quantity) as estimated_value 
        FROM cart c 
        JOIN users u ON c.user_id=u.id 
        JOIN products p ON c.product_id=p.id 
        WHERE c.saved_for_later=0 
        GROUP BY c.user_id ORDER BY estimated_value DESC""").fetchall())
    return jsonify(carts)

@app.route('/api/admin/abandoned_carts/notify/<int:uid>', methods=['POST'])
@admin_required
def admin_notify_abandoned(admin, uid):
    notify(uid, 'Your Cart is Waiting! 🛒', 'Complete your purchase now before items run out of stock.', 'info')
    return jsonify({'message': 'Reminder sent successfully'})

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/admin/upload', methods=['POST'])
@admin_required
def admin_upload_file(admin):
    import werkzeug.utils
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file:
        filename = werkzeug.utils.secure_filename(file.filename)
        # Add random hex to prevent overwriting
        name, ext = os.path.splitext(filename)
        unique_filename = f"{name}_{secrets.token_hex(4)}{ext}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
        return jsonify({'message': 'File uploaded', 'url': f'/uploads/{unique_filename}'}), 201

@app.route('/api/admin/analytics', methods=['GET'])
@admin_required
def admin_analytics(admin):
    db = get_db()
    total_revenue = db.execute("SELECT COALESCE(SUM(total),0) as v FROM orders WHERE status NOT IN ('CANCELLED')").fetchone()['v']
    total_orders = db.execute("SELECT COUNT(*) as v FROM orders").fetchone()['v']
    total_customers = db.execute("SELECT COUNT(*) as v FROM users WHERE role='customer'").fetchone()['v']
    total_products = db.execute("SELECT COUNT(*) as v FROM products").fetchone()['v']
    low_stock = db.execute("SELECT COUNT(*) as v FROM product_variants WHERE stock < 5").fetchone()['v']
    pending_orders = db.execute("SELECT COUNT(*) as v FROM orders WHERE status='PENDING'").fetchone()['v']
    
    seven_days_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    chart = dict_rows(db.execute("""SELECT DATE(created_at) as date, SUM(total) as revenue 
        FROM orders WHERE status NOT IN ('CANCELLED') AND created_at >= ?
        GROUP BY DATE(created_at) ORDER BY date""", (seven_days_ago,)).fetchall())
        
    top_products = dict_rows(db.execute("""SELECT p.name, sum(oi.quantity) as sold, sum(oi.price*oi.quantity) as revenue
        FROM order_items oi JOIN products p ON oi.product_id=p.id
        JOIN orders o ON oi.order_id=o.id WHERE o.status NOT IN ('CANCELLED')
        GROUP BY p.id ORDER BY sold DESC LIMIT 5""").fetchall())

    return jsonify({
        'total_revenue': total_revenue, 'total_orders': total_orders,
        'total_customers': total_customers, 'total_products': total_products,
        'low_stock': low_stock, 'pending_orders': pending_orders,
        'chart': chart, 'top_products': top_products
    })

@app.route('/api/admin/returns', methods=['GET'])
@admin_required
def admin_returns(admin):
    db = get_db()
    returns = dict_rows(db.execute("""SELECT r.*, o.order_number, u.name as customer_name, u.email 
        FROM returns r JOIN orders o ON r.order_id=o.id JOIN users u ON r.user_id=u.id ORDER BY r.created_at DESC""").fetchall())
    return jsonify(returns)

@app.route('/api/admin/returns/<int:rid>', methods=['PUT'])
@admin_required
def admin_manage_return(admin, rid):
    d = request.json or {}
    db = get_db()
    status = d.get('status', 'approved')
    db.execute("UPDATE returns SET status=?, admin_notes=? WHERE id=?", (status, sanitize(d.get('notes','')), rid))
    
    # If approved, update order status to returned
    if status == 'approved':
        ret = db.execute("SELECT order_id FROM returns WHERE id=?", (rid,)).fetchone()
        if ret:
            db.execute("UPDATE orders SET status='RETURNED' WHERE id=?", (ret['order_id'],))
    
    db.commit()
    return jsonify({'message': f'Return marked as {status}'})

@app.route('/api/orders/<int:oid>/return', methods=['POST'])
@token_required
def request_return(user, oid):
    d = request.json or {}
    db = get_db()
    order = db.execute("SELECT id FROM orders WHERE id=? AND user_id=? AND status='DELIVERED'", (oid, user['id'])).fetchone()
    if not order:
        return jsonify({'error': 'Order not eligible for return'}), 400
    
    # Check if already requested
    if db.execute("SELECT id FROM returns WHERE order_id=?", (oid,)).fetchone():
        return jsonify({'error': 'Return already requested'}), 400
        
    db.execute("INSERT INTO returns (order_id, user_id, reason) VALUES (?,?,?)", (oid, user['id'], sanitize(d.get('reason',''))))
    db.commit()
    return jsonify({'message': 'Return request submitted successfully'}), 201

@app.route('/api/newsletter/subscribe', methods=['POST'])
def newsletter_subscribe():
    d = request.json or {}
    email = sanitize(d.get('email',''))
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({'error': 'Invalid email address'}), 400
    db = get_db()
    try:
        db.execute("INSERT INTO newsletter_subscribers (email) VALUES (?)", (email,))
        db.commit()
        return jsonify({'message': 'Successfully subscribed to the newsletter!'})
    except Exception:
        return jsonify({'error': 'Email is already subscribed'}), 400

@app.route('/api/razorpay/refund', methods=['POST'])
@admin_required
def create_refund(admin):
    d = request.json or {}
    payment_id = d.get('payment_id')
    amount = d.get('amount')
    if not razorpay_client or not payment_id:
        return jsonify({'error': 'Razorpay not configured or missing payment_id'}), 400
    try:
        # Amount in paise
        refund = razorpay_client.payment.refund(payment_id, {'amount': int(float(amount)*100)} if amount else {})
        return jsonify({'message': 'Refund initiated successfully', 'refund': refund})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── CMS & SETTINGS ──────────────────────────────────────────────────────────
@app.route('/api/site-config', methods=['GET'])
def get_site_config():
    db = get_db()
    settings = dict_rows(db.execute("SELECT key, value FROM settings").fetchall())
    config = {s['key']: s['value'] for s in settings}
    return jsonify(config)

@app.route('/api/admin/settings', methods=['GET', 'POST'])
@token_required
def admin_settings(user):
    if user['role'] != 'admin': return jsonify({'error': 'Unauthorized'}), 403
    db = get_db()
    if request.method == 'GET':
        settings = dict_rows(db.execute("SELECT key, value FROM settings").fetchall())
        return jsonify({s['key']: s['value'] for s in settings})
    
    d = request.json or {}
    for k, v in d.items():
        db.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=?", (k, str(v), str(v)))
    db.commit()
    return jsonify({'message': 'Settings updated successfully'})

@app.route('/sitemap.xml', methods=['GET'])
def sitemap():
    db = get_db()
    products = db.execute("SELECT slug, created_at FROM products WHERE is_active=1").fetchall()
    categories = db.execute("SELECT slug FROM categories").fetchall()
    
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    base_url = os.environ.get('BASE_URL', 'https://luxe-fashion.com')
    
    # Static routes
    for route in ['/', '/#shop', '/#categories']:
        xml += f'  <url>\n    <loc>{base_url}{route}</loc>\n    <changefreq>daily</changefreq>\n    <priority>1.0</priority>\n  </url>\n'
        
    for p in products:
        xml += f'  <url>\n    <loc>{base_url}/#product/{p["slug"]}</loc>\n    <lastmod>{p["created_at"][:10]}</lastmod>\n    <priority>0.8</priority>\n  </url>\n'
        
    for c in categories:
        xml += f'  <url>\n    <loc>{base_url}/#category/{c["slug"]}</loc>\n    <priority>0.7</priority>\n  </url>\n'
        
    xml += '</urlset>'
    return app.response_class(xml, mimetype='application/xml')

@app.route('/robots.txt', methods=['GET'])
def robots():
    content = "User-agent: *\nDisallow: /api/\nDisallow: /admin\nSitemap: https://luxe-fashion.com/sitemap.xml"
    return app.response_class(content, mimetype='text/plain')

# ─── Error Handlers ──────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(429)
def rate_limit(e):
    return jsonify({'error': 'Too many requests. Please try again later.'}), 429

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error'}), 500

# ─── Run ─────────────────────────────────────────────────────────────────────
with app.app_context():
    try:
        init_db()
    except Exception as e:
        app.logger.error(f"Error initializing DB: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=os.environ.get('FLASK_DEBUG','1')=='1', host='0.0.0.0', port=port)
