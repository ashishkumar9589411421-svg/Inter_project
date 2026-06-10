/* ═══════════════════════════════════════════════════════════════════════════
   LUXE — Complete SPA Engine v2.0 (Razorpay + Dynamic UI)
   ═══════════════════════════════════════════════════════════════════════════ */

const API = '/api';
const state = {
    token: localStorage.getItem('luxe_token'),
    user: JSON.parse(localStorage.getItem('luxe_user') || 'null'),
    cart: [], wishlist: [], theme: localStorage.getItem('luxe_theme') || 'light',
    razorpayKeyId: ''
};

const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const app = $('#app');

// ─── Toast System ──────────────────────────────────────────────────────────
function toast(msg, type = 'info') {
    const icons = { success: 'fa-check-circle', error: 'fa-exclamation-circle', info: 'fa-info-circle', warning: 'fa-exclamation-triangle' };
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.innerHTML = `<i class="fas ${icons[type]}"></i><span>${msg}</span><span class="toast-close" onclick="this.parentElement.remove()"><i class="fas fa-times"></i></span>`;
    $('#toast-container').appendChild(t);
    setTimeout(() => { t.style.animation = 'slideOut 0.3s ease forwards'; setTimeout(() => t.remove(), 300); }, 3500);
}

// ─── API Helper ────────────────────────────────────────────────────────────
async function api(endpoint, method = 'GET', body = null) {
    const headers = { 'Content-Type': 'application/json' };
    if (state.token) headers['Authorization'] = `Bearer ${state.token}`;
    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(`${API}${endpoint}`, opts);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || data.message || 'Error');
    return data;
}

// ─── Razorpay Config ───────────────────────────────────────────────────────
async function loadConfig() {
    try { const c = await api('/config'); state.razorpayKeyId = c.razorpay_key_id; } catch(e) {}
}
loadConfig();

// ─── Site Config & Theme Builder ───────────────────────────────────────────
async function loadSiteConfig() {
    try {
        const c = await api('/site-config');
        if (c.brand_name) {
            document.title = `${c.brand_name} | Luxury Fashion`;
            const brandElements = $$('.brand-name-display');
            brandElements.forEach(el => el.textContent = c.brand_name);
        }
        if (c.primary_color) document.documentElement.style.setProperty('--primary', c.primary_color);
        if (c.accent_color) document.documentElement.style.setProperty('--accent', c.accent_color);
        
        if (c.show_developer_credit === '1' || c.show_developer_credit === 'true') {
            const devCredit = $('#developer-credit');
            if (devCredit) {
                devCredit.innerHTML = `Website made by <a href="${c.developer_portfolio}" target="_blank" style="color:var(--accent);">${c.developer_name}</a> | <a href="${c.developer_linkedin}" target="_blank" style="color:var(--accent);"><i class="fab fa-linkedin"></i> LinkedIn</a>`;
                devCredit.style.display = 'block';
            }
        }
    } catch(e) { console.warn("Failed to load site config:", e); }
}
loadSiteConfig();

// ─── Auth State ────────────────────────────────────────────────────────────
function setAuth(token, user) {
    state.token = token; state.user = user;
    localStorage.setItem('luxe_token', token);
    localStorage.setItem('luxe_user', JSON.stringify(user));
    updateNav();
}
function clearAuth() {
    state.token = null; state.user = null; state.cart = []; state.wishlist = [];
    localStorage.removeItem('luxe_token'); localStorage.removeItem('luxe_user');
    updateNav();
}
function isAdmin() { return state.user && state.user.role === 'admin'; }

// ─── Dark Mode ─────────────────────────────────────────────────────────────
function initTheme() {
    document.documentElement.setAttribute('data-theme', state.theme);
    const icon = $('#theme-toggle i');
    if (icon) icon.className = state.theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
}
$('#theme-toggle').addEventListener('click', () => {
    state.theme = state.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('luxe_theme', state.theme);
    initTheme();
});

// ─── Hamburger ─────────────────────────────────────────────────────────────
$('#hamburger').addEventListener('click', () => {
    $('#hamburger').classList.toggle('active');
    $('#nav-links').classList.toggle('show');
});

// ─── User Dropdown ─────────────────────────────────────────────────────────
$('#user-avatar-btn')?.addEventListener('click', (e) => {
    e.stopPropagation();
    $('#user-dropdown').classList.toggle('show');
});
document.addEventListener('click', () => $('#user-dropdown')?.classList.remove('show'));

// ─── Logout ────────────────────────────────────────────────────────────────
$('#logout-btn').addEventListener('click', (e) => {
    e.preventDefault();
    clearAuth();
    toast('Logged out successfully', 'info');
    navigate('home');
});

// ─── Back to Top ───────────────────────────────────────────────────────────
const backToTop = $('#back-to-top');
window.addEventListener('scroll', () => {
    $('#navbar').classList.toggle('scrolled', window.scrollY > 50);
    backToTop?.classList.toggle('show', window.scrollY > 400);
});
backToTop?.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));

// ─── Scroll Reveal ─────────────────────────────────────────────────────────
function initScrollReveal() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('visible'); observer.unobserve(e.target); } });
    }, { threshold: 0.1 });
    document.querySelectorAll('.reveal, .reveal-left, .reveal-right, .reveal-scale').forEach(el => observer.observe(el));
}

// ─── Counter Animation ────────────────────────────────────────────────────
function animateCounters() {
    document.querySelectorAll('.counter-num').forEach(el => {
        const target = parseInt(el.dataset.target);
        const suffix = el.dataset.suffix || '';
        let current = 0;
        const increment = target / 60;
        const timer = setInterval(() => {
            current += increment;
            if (current >= target) { current = target; clearInterval(timer); }
            el.textContent = Math.floor(current).toLocaleString() + suffix;
        }, 25);
    });
}

// ─── Floating Particles ───────────────────────────────────────────────────
function createParticles(container, count = 20) {
    for (let i = 0; i < count; i++) {
        const p = document.createElement('div');
        p.className = 'hero-particle';
        const size = Math.random() * 6 + 2;
        p.style.cssText = `width:${size}px;height:${size}px;left:${Math.random()*100}%;bottom:${-10}%;animation-duration:${Math.random()*8+6}s;animation-delay:${Math.random()*5}s;`;
        container.appendChild(p);
    }
}

// ─── Navigation ────────────────────────────────────────────────────────────
function navigate(hash) { window.location.hash = hash; }

function updateNav() {
    const logged = !!state.token;
    const admin = isAdmin();
    $$('.auth-only').forEach(el => el.style.display = logged ? '' : 'none');
    $$('.guest-only').forEach(el => el.style.display = logged ? 'none' : '');
    $$('.admin-only').forEach(el => el.style.display = admin ? '' : 'none');
    if (state.user) $('#dropdown-name').textContent = state.user.name || '';
    $('#nav-links').classList.remove('show');
    $('#hamburger').classList.remove('active');
    if (logged) { fetchCounts(); }
    else { $('#cart-count').textContent = '0'; $('#wishlist-count').textContent = '0'; $('#notif-count').textContent = '0'; }
}

async function fetchCounts() {
    try {
        const me = await api('/auth/me');
        state.user = { ...state.user, ...me };
        $('#cart-count').textContent = '0';
        try { state.cart = await api('/cart'); $('#cart-count').textContent = state.cart.filter(i => !i.saved_for_later).reduce((s, i) => s + i.quantity, 0); } catch(e){}
        try { state.wishlist = await api('/wishlist'); $('#wishlist-count').textContent = state.wishlist.length; } catch(e){}
        $('#notif-count').textContent = me.unread_notifications || '0';
    } catch(e) { if (e.message.includes('expired') || e.message.includes('Invalid')) clearAuth(); }
}

// ─── Router ────────────────────────────────────────────────────────────────
const routes = {
    home: renderHome, shop: renderShop, login: renderLogin, register: renderLogin,
    cart: renderCart, checkout: renderCheckout, dashboard: renderDashboard,
    orders: renderOrders, profile: renderProfile, wishlist: renderWishlist,
    notifications: renderNotifications, wallet: renderWallet, loyalty: renderLoyalty,
    addresses: renderAddresses, contact: renderContact, blog: renderBlog,
    about: renderAbout, privacy: renderPrivacy, refund: renderRefund, faq: renderFaq,
    'admin-login': renderAdminLogin, admin: renderAdmin, 'forgot-password': renderLogin
};

function router() {
    let hash = location.hash.replace('#', '').split('/')[0] || 'home';
    const param = location.hash.split('/')[1] || '';
    updateNav();
    if (hash === 'product') { renderProductDetail(param); return; }
    if (hash === 'order') { renderOrderDetail(param); return; }
    if (hash.startsWith('admin-') && hash !== 'admin-login') { renderAdmin(hash.replace('admin-','')); return; }
    if (routes[hash]) routes[hash]();
    else renderHome();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}
window.addEventListener('hashchange', router);

// ─── Helpers ───────────────────────────────────────────────────────────────
function skeletonGrid(n = 4) {
    return `<div class="product-grid">${Array(n).fill('<div class="skeleton skeleton-card"></div>').join('')}</div>`;
}
function esc(str) { if (!str) return ''; const d = document.createElement('div'); d.textContent = str; return d.innerHTML; }
function stars(rating) {
    let s = '';
    for (let i = 1; i <= 5; i++) s += `<i class="fas fa-star" style="color:${i <= rating ? 'var(--accent)' : 'var(--border)'}"></i>`;
    return s;
}

// ─── Product Card ──────────────────────────────────────────────────────────
function productCard(p) {
    const price = p.sale_price || p.price || p.base_price;
    const original = p.base_price;
    const discount = original && price < original ? Math.round((1 - price/original)*100) : 0;
    return `<div class="product-card reveal-scale" onclick="navigate('product/${esc(p.slug)}')">
        <div class="card-img">
            ${discount > 0 ? `<span class="product-badge badge-sale">${discount}% OFF</span>` : ''}
            ${p.is_featured ? `<span class="product-badge badge-new" style="left:auto;right:12px">Featured</span>` : ''}
            <img src="${esc(p.image_url)}" alt="${esc(p.name)}" loading="lazy">
            <div class="card-actions">
                <button class="action-btn" onclick="event.stopPropagation();addToWishlist(${p.id})" title="Wishlist"><i class="fas fa-heart"></i></button>
                <button class="action-btn" onclick="event.stopPropagation();quickAdd(${p.id})" title="Add to Cart"><i class="fas fa-shopping-bag"></i></button>
                <button class="action-btn" onclick="event.stopPropagation();navigate('product/${esc(p.slug)}')" title="Quick View"><i class="fas fa-eye"></i></button>
            </div>
        </div>
        <div class="card-body">
            <div class="card-category">${esc(p.category_name || '')}</div>
            <div class="card-title">${esc(p.name)}</div>
            <div class="card-price">
                <span class="price">₹${price.toLocaleString()}</span>
                ${discount > 0 ? `<span class="original">₹${original.toLocaleString()}</span><span class="discount">${discount}% off</span>` : ''}
            </div>
            ${p.avg_rating > 0 ? `<div class="card-rating">${stars(Math.round(p.avg_rating))} <span>(${p.review_count})</span></div>` : ''}
        </div>
    </div>`;
}

// ─── Quick Actions ─────────────────────────────────────────────────────────
async function quickAdd(pid) {
    if (!state.token) return navigate('login');
    try { await api('/cart', 'POST', { product_id: pid }); toast('Added to cart!', 'success'); fetchCounts(); } catch(e) { toast(e.message, 'error'); }
}
async function addToWishlist(pid) {
    if (!state.token) return navigate('login');
    try { await api('/wishlist', 'POST', { product_id: pid }); toast('Added to wishlist!', 'success'); fetchCounts(); } catch(e) { toast(e.message, 'error'); }
}

// ═══════════════════════════════════════════════════════════════════════════
// ─── HOME ──────────────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════
async function renderHome() {
    app.innerHTML = `
    <!-- Marquee Ticker -->
    <div class="marquee"><div class="marquee-inner">
        <span>⚡ SALE LIVE — Up to 50% Off</span><span>🚚 Free Shipping Over ₹999</span><span>🎁 Use Code WELCOME10</span><span>💎 Premium Quality Guaranteed</span><span>🔒 Secure Razorpay Payments</span><span>↩️ Easy 7-Day Returns</span>
        <span>⚡ SALE LIVE — Up to 50% Off</span><span>🚚 Free Shipping Over ₹999</span><span>🎁 Use Code WELCOME10</span><span>💎 Premium Quality Guaranteed</span><span>🔒 Secure Razorpay Payments</span><span>↩️ Easy 7-Day Returns</span>
    </div></div>

    <!-- Hero -->
    <div class="hero" id="hero-section">
        <div class="hero-bg"></div>
        <div class="hero-content">
            <h1 class="gsap-fade">ELEVATE YOUR <span class="accent">STYLE</span></h1>
            <p class="gsap-fade">Discover curated luxury fashion collections. Handpicked for the modern individual who demands excellence.</p>
            <div class="hero-actions gsap-fade">
                <a href="#shop" class="btn btn-primary btn-lg">Shop Now <i class="fas fa-arrow-right"></i></a>
                <a href="#shop" class="btn btn-outline btn-lg">New Arrivals</a>
            </div>
        </div>
        <div class="hero-scroll"><i class="fas fa-chevron-down"></i></div>
    </div>

    <!-- Features Strip -->
    <div class="features-strip">
        <div class="feature-badge"><i class="fas fa-shipping-fast"></i> Free Shipping Over ₹999</div>
        <div class="feature-badge"><i class="fas fa-shield-alt"></i> Secure Payments</div>
        <div class="feature-badge"><i class="fas fa-undo-alt"></i> 7-Day Returns</div>
        <div class="feature-badge"><i class="fas fa-gem"></i> Premium Quality</div>
        <div class="feature-badge"><i class="fas fa-headset"></i> 24/7 Support</div>
    </div>

    <div class="container">
        <!-- Categories -->
        <div class="section"><div class="section-title reveal"><h2>Shop by Category</h2><p>Find your perfect style</p><div class="line"></div></div>
            <div id="home-cats" class="categories-grid"></div>
        </div>

        <!-- Trending -->
        <div class="section"><div class="section-title reveal"><h2>Trending Now</h2><p>Most loved by our customers</p><div class="line"></div></div>
            <div id="home-featured">${skeletonGrid(4)}</div>
        </div>

        <!-- Counter Stats -->
        <div class="counter-section reveal">
            <div class="counter-grid">
                <div class="counter-item"><div class="counter-num" data-target="5000" data-suffix="+">0</div><div class="counter-label">Happy Customers</div></div>
                <div class="counter-item"><div class="counter-num" data-target="500" data-suffix="+">0</div><div class="counter-label">Products</div></div>
                <div class="counter-item"><div class="counter-num" data-target="50" data-suffix="+">0</div><div class="counter-label">Brands</div></div>
                <div class="counter-item"><div class="counter-num" data-target="4" data-suffix=".8★">0</div><div class="counter-label">Avg Rating</div></div>
            </div>
        </div>

        <!-- New Arrivals -->
        <div class="section"><div class="section-title reveal"><h2>New Arrivals</h2><p>Fresh drops this season</p><div class="line"></div></div>
            <div id="home-new">${skeletonGrid(4)}</div>
        </div>

        <!-- Flash Sale -->
        <div class="section" style="background:var(--accent-light); padding:3rem; border-radius:var(--radius-lg); margin-bottom:4rem;">
            <div class="section-title reveal"><h2>Flash Sale</h2><p>Limited time deals. Grab them before they're gone!</p><div class="line"></div></div>
            <div id="home-flash">${skeletonGrid(4)}</div>
        </div>
    </div>

    <!-- Newsletter -->
    <div class="newsletter-section">
        <h2>Join the LUXE Club</h2>
        <p>Subscribe for exclusive deals, early access & style tips</p>
        <form class="newsletter-form" onsubmit="event.preventDefault();toast('Subscribed! Welcome to LUXE Club 🎉','success');this.reset();">
            <input type="email" placeholder="Enter your email address" required>
            <button type="submit">Subscribe</button>
        </form>
    </div>

    <!-- Payment Trust -->
    <div class="container text-center" style="padding:2rem 0">
        <p class="text-muted" style="margin-bottom:0.5rem;font-size:0.85rem;text-transform:uppercase;letter-spacing:1px">Secure Payment Methods</p>
        <div class="payment-icons">
            <i class="fab fa-cc-visa"></i><i class="fab fa-cc-mastercard"></i><i class="fab fa-google-pay"></i><i class="fab fa-apple-pay"></i><i class="fas fa-university"></i><i class="fas fa-qrcode"></i>
        </div>
    </div>`;

    // Particles
    createParticles($('#hero-section'), 25);
    // GSAP hero animation
    if (typeof gsap !== 'undefined') {
        gsap.from('.gsap-fade', { y: 50, opacity: 0, duration: 1, stagger: 0.25, ease: 'power3.out' });
    }
    // Scroll reveal
    setTimeout(initScrollReveal, 100);
    // Counter animation with IntersectionObserver
    const counterObs = new IntersectionObserver((entries) => {
        entries.forEach(e => { if (e.isIntersecting) { animateCounters(); counterObs.disconnect(); } });
    }, { threshold: 0.3 });
    const counterEl = document.querySelector('.counter-section');
    if (counterEl) counterObs.observe(counterEl);

    // Load data
    try {
        const cats = await api('/categories');
        $('#home-cats').innerHTML = cats.map(c => `<div class="category-card reveal-scale" onclick="navigate('shop?category=${c.slug}')"><img src="${esc(c.image_url)}" alt="${esc(c.name)}" loading="lazy"><h3>${esc(c.name)}</h3></div>`).join('');
        const { products } = await api('/products?sort=popular&per_page=4');
        $('#home-featured').innerHTML = `<div class="product-grid">${products.map(productCard).join('')}</div>`;
        const { products: newP } = await api('/products?sort=newest&per_page=4');
        $('#home-new').innerHTML = `<div class="product-grid">${newP.map(productCard).join('')}</div>`;
        const { products: flashP } = await api('/products?sort=popular&per_page=4');
        $('#home-flash').innerHTML = `<div class="product-grid">${flashP.map(productCard).join('')}</div>`;
        initScrollReveal();
    } catch(e) { console.error(e); }
}

// ─── SHOP ──────────────────────────────────────────────────────────────────
async function renderShop() {
    const urlParams = new URLSearchParams(location.hash.split('?')[1] || '');
    app.innerHTML = `<div class="container">
        <div class="search-bar"><i class="fas fa-search"></i><input type="text" id="search-input" placeholder="Search products..." value="${esc(urlParams.get('search')||'')}"></div>
        <div class="sort-bar">
            <span id="product-count"></span>
            <div style="display:flex;gap:1rem;align-items:center;">
                <select id="sort-select"><option value="newest">Newest</option><option value="popular">Popular</option><option value="price_low">Price: Low to High</option><option value="price_high">Price: High to Low</option></select>
                <button class="btn btn-outline btn-sm" id="mobile-filter-btn" style="display:none;"><i class="fas fa-filter"></i> Filters</button>
            </div>
        </div>
        <div class="tabs" id="category-tabs"><button class="tab-btn active" data-cat="">All</button></div>
        
        <div class="shop-layout">
            <aside class="filter-sidebar" id="filter-sidebar">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;" class="mobile-only-header">
                    <h2 style="margin:0;">Filters</h2>
                    <button class="btn btn-ghost" onclick="document.getElementById('filter-sidebar').classList.remove('show')" style="display:none;" id="close-filter-btn"><i class="fas fa-times"></i></button>
                </div>
                <div class="filter-group">
                    <h3>Price Range</h3>
                    <div class="price-range">
                        <input type="number" id="min-price" placeholder="Min" value="${esc(urlParams.get('min_price')||'')}"> - 
                        <input type="number" id="max-price" placeholder="Max" value="${esc(urlParams.get('max_price')||'')}">
                    </div>
                </div>
                <div class="filter-group">
                    <h3>Brand</h3>
                    <select id="brand-select" style="width:100%; padding:0.5rem; border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--bg); color:var(--text)">
                        <option value="">All Brands</option>
                        <option value="LUXE Originals">LUXE Originals</option>
                        <option value="LUXE Ethnic">LUXE Ethnic</option>
                        <option value="K-Style">K-Style</option>
                        <option value="Denim Co">Denim Co</option>
                        <option value="Street LUXE">Street LUXE</option>
                        <option value="LUXE Studio">LUXE Studio</option>
                    </select>
                </div>
                <div class="filter-group">
                    <h3>Size</h3>
                    <select id="size-select" style="width:100%; padding:0.5rem; border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--bg); color:var(--text)">
                        <option value="">All Sizes</option>
                        <option value="XS">XS</option>
                        <option value="S">S</option>
                        <option value="M">M</option>
                        <option value="L">L</option>
                        <option value="XL">XL</option>
                        <option value="XXL">XXL</option>
                    </select>
                </div>
                <div class="filter-group">
                    <h3>Color</h3>
                    <select id="color-select" style="width:100%; padding:0.5rem; border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--bg); color:var(--text)">
                        <option value="">All Colors</option>
                        <option value="Black">Black</option>
                        <option value="White">White</option>
                        <option value="Navy">Navy</option>
                    </select>
                </div>
                <div class="filter-group">
                    <h3>Rating</h3>
                    <select id="rating-select" style="width:100%; padding:0.5rem; border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--bg); color:var(--text)">
                        <option value="">Any Rating</option>
                        <option value="4">4★ & Above</option>
                        <option value="3">3★ & Above</option>
                        <option value="2">2★ & Above</option>
                    </select>
                </div>
                <button class="btn btn-primary btn-full" id="apply-filters">Apply Filters</button>
            </aside>
            <div id="shop-grid">${skeletonGrid(8)}</div>
        </div>
    </div>
    <style>
        @media(max-width:1024px) {
            #mobile-filter-btn { display:inline-flex !important; }
            #close-filter-btn { display:block !important; }
            .filter-sidebar.show { display:block !important; position:fixed; top:0; left:0; right:0; bottom:0; background:var(--bg-card); z-index:2000; padding:2rem; overflow-y:auto; }
            .mobile-only-header { display:flex !important; }
        }
        .mobile-only-header { display:none; }
    </style>`;
    
    if (urlParams.get('brand')) $('#brand-select').value = urlParams.get('brand');
    if (urlParams.get('size')) $('#size-select').value = urlParams.get('size');
    if (urlParams.get('color')) $('#color-select').value = urlParams.get('color');
    if (urlParams.get('min_rating')) $('#rating-select').value = urlParams.get('min_rating');

    let currentCat = urlParams.get('category') || '';
    const cats = await api('/categories');
    const tabsEl = $('#category-tabs');
    cats.forEach(c => { const b = document.createElement('button'); b.className = 'tab-btn'; b.dataset.cat = c.slug; b.textContent = c.name; tabsEl.appendChild(b); });
    if (currentCat) { $$('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.cat === currentCat)); }

    async function loadProducts() {
        const search = $('#search-input').value;
        const sort = $('#sort-select').value;
        const minP = $('#min-price').value;
        const maxP = $('#max-price').value;
        const brand = $('#brand-select').value;
        const size = $('#size-select').value;
        const color = $('#color-select').value;
        const rating = $('#rating-select').value;

        let url = `/products?sort=${sort}&per_page=50`;
        if (currentCat) url += `&category=${currentCat}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (minP) url += `&min_price=${minP}`;
        if (maxP) url += `&max_price=${maxP}`;
        if (brand) url += `&brand=${encodeURIComponent(brand)}`;
        if (size) url += `&size=${encodeURIComponent(size)}`;
        if (color) url += `&color=${encodeURIComponent(color)}`;
        if (rating) url += `&min_rating=${rating}`;
        
        try {
            const { products, total } = await api(url);
            $('#product-count').textContent = `${total} products`;
            $('#shop-grid').innerHTML = products.length ? `<div class="product-grid">${products.map(productCard).join('')}</div>` :
                `<div class="empty-state"><i class="fas fa-search"></i><h3>No products found</h3><p>Try adjusting your search or filters</p></div>`;
            setTimeout(initScrollReveal, 50);
            $('#filter-sidebar').classList.remove('show'); // close sidebar on mobile after apply
        } catch(e) { toast(e.message, 'error'); }
    }

    let searchTimer;
    $('#search-input').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadProducts, 400); });
    $('#sort-select').addEventListener('change', loadProducts);
    $('#apply-filters').addEventListener('click', loadProducts);
    $('#mobile-filter-btn').addEventListener('click', () => $('#filter-sidebar').classList.add('show'));
    
    tabsEl.addEventListener('click', (e) => {
        if (e.target.classList.contains('tab-btn')) {
            $$('.tab-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentCat = e.target.dataset.cat;
            loadProducts();
        }
    });
    loadProducts();
}

// ─── Product Detail ────────────────────────────────────────────────────────
async function renderProductDetail(slug) {
    if (!slug) return navigate('shop');
    app.innerHTML = `<div class="container"><div class="product-detail"><div class="skeleton" style="height:500px"></div><div><div class="skeleton skeleton-text" style="width:80%;height:24px"></div></div></div></div>`;
    try {
        const p = await api(`/products/${slug}`);
        const price = p.sale_price || p.base_price;
        const sizes = [...new Set(p.variants.map(v => v.size).filter(Boolean))];
        const colors = [...new Set(p.variants.map(v => JSON.stringify({color:v.color,hex:v.color_hex})))].map(c=>JSON.parse(c));
        const allImages = [p.image_url, ...(p.images||[]).map(img => img.image_url)].filter((v,i,a)=>a.indexOf(v)===i);

        window.setMainImg = (el, src) => {
            $('#main-img').src = src;
            $$('.thumb').forEach(t=>t.classList.remove('active'));
            el.classList.add('active');
        };

        window.zoomImg = (e) => {
            const img = e.target;
            const x = e.offsetX / img.offsetWidth * 100;
            const y = e.offsetY / img.offsetHeight * 100;
            img.style.transformOrigin = `${x}% ${y}%`;
            img.style.transform = 'scale(2)';
        };

        app.innerHTML = `<div class="container">
            <div class="product-detail">
                <div class="detail-gallery">
                    <div class="main-img-container" style="overflow:hidden; position:relative; cursor:zoom-in; border-radius:var(--radius-lg)">
                        <img src="${esc(p.image_url)}" alt="${esc(p.name)}" id="main-img" style="transition: transform 0.2s ease; width:100%; height:100%; object-fit:cover;" onmousemove="zoomImg(event)" onmouseleave="this.style.transform='scale(1)'">
                    </div>
                    <div class="gallery-thumbnails" style="display:flex; gap:10px; margin-top:10px; overflow-x:auto; padding-bottom:5px;">
                        ${allImages.map((src, i) => `
                            <img src="${esc(src)}" class="thumb ${i===0?'active':''}" onclick="setMainImg(this, '${esc(src)}')" style="width:80px;height:80px;object-fit:cover;cursor:pointer;border:2px solid ${i===0?'var(--accent)':'transparent'};border-radius:var(--radius-sm); transition:border 0.2s">
                        `).join('')}
                    </div>
                </div>
                <div class="detail-info">
                    <div class="detail-brand">${esc(p.brand||'')}</div>
                    <h1>${esc(p.name)}</h1>
                    <div class="card-rating mb-2">${stars(Math.round(p.avg_rating))} <span>(${p.review_count} reviews)</span></div>
                    <div class="detail-price">₹${price.toLocaleString()}
                        ${p.discount>0?`<span class="original">₹${p.base_price.toLocaleString()}</span><span class="off">${p.discount}% off</span>`:''}
                    </div>
                    <p class="mb-3" style="color:var(--text-secondary)">${esc(p.description||'')}</p>
                    ${sizes.length?`<div class="variant-selector"><label>Size</label><div class="size-options">${sizes.map(s=>{
                        const v=p.variants.find(v=>v.size===s);
                        const oos=v&&v.stock<=0;
                        return `<button class="size-btn ${oos?'oos':''}" data-size="${s}" ${oos?'disabled':''}>${s}</button>`;
                    }).join('')}</div></div>`:''}
                    ${colors.length?`<div class="variant-selector"><label>Color</label><div class="color-options">${colors.map(c=>
                        `<button class="color-btn" data-color="${esc(c.color)}" style="background:${c.hex}" title="${esc(c.color)}"></button>`
                    ).join('')}</div></div>`:''}
                    <div class="qty-selector"><button onclick="changeQty(-1)">−</button><input type="number" id="detail-qty" value="1" min="1" max="10"><button onclick="changeQty(1)">+</button></div>
                    <div class="detail-actions">
                        <button class="btn btn-primary btn-lg pulse" id="add-to-cart-btn" onclick="addToCartDetail(${p.id})"><i class="fas fa-shopping-bag"></i> Add to Cart</button>
                        <button class="btn btn-outline" onclick="addToWishlist(${p.id})"><i class="fas fa-heart"></i></button>
                    </div>
                    <div class="razorpay-badge"><i class="fas fa-lock"></i> Secure Checkout with Razorpay</div>
                    <div class="detail-meta mt-3">
                        ${p.sku?`<p><strong>SKU:</strong> ${esc(p.sku)}</p>`:''}
                        ${p.fabric?`<p><strong>Fabric:</strong> ${esc(p.fabric)}</p>`:''}
                        ${p.material?`<p><strong>Material:</strong> ${esc(p.material)}</p>`:''}
                        ${p.care_instructions?`<p><strong>Care:</strong> ${esc(p.care_instructions)}</p>`:''}
                        <p><strong>Category:</strong> ${esc(p.category_name||'')}</p>
                    </div>
                </div>
            </div>
            
            <div class="section reveal">
                <div style="display:flex;justify-content:space-between;align-items:center;" class="mb-3">
                    <h2 style="margin:0;">Customer Reviews</h2>
                    ${state.token ? `<button class="btn btn-outline btn-sm" onclick="document.getElementById('review-form-container').style.display = document.getElementById('review-form-container').style.display === 'none' ? 'block' : 'none'">Write a Review</button>` : ''}
                </div>
                
                <div id="review-form-container" style="display:none; margin-bottom:2rem; padding:1.5rem; background:var(--bg-card); border-radius:var(--radius-lg); border:1px solid var(--border);">
                    <form id="submit-review-form">
                        <div class="form-group">
                            <label>Rating</label>
                            <select id="review-rating" required style="width:100px; padding:0.5rem; border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--bg); color:var(--text);">
                                <option value="5">5 ★</option>
                                <option value="4">4 ★</option>
                                <option value="3">3 ★</option>
                                <option value="2">2 ★</option>
                                <option value="1">1 ★</option>
                            </select>
                        </div>
                        <div class="form-group"><label>Title</label><input type="text" id="review-title" placeholder="Summarize your experience"></div>
                        <div class="form-group"><label>Review</label><textarea id="review-body" rows="3" placeholder="What did you like or dislike?"></textarea></div>
                        <div class="form-group"><label>Photo URL (Optional)</label><input type="text" id="review-photo" placeholder="https://example.com/photo.jpg"></div>
                        <button type="submit" class="btn btn-primary">Submit Review</button>
                    </form>
                </div>

                ${p.reviews.length ? p.reviews.map(r=>{
                    let imgs = [];
                    try { imgs = JSON.parse(r.images||'[]'); } catch(e){}
                    return `<div class="review-card">
                        <div class="review-header">
                            <div><span class="review-author">${esc(r.user_name)}</span> <span class="review-date">${new Date(r.created_at).toLocaleDateString()}</span></div>
                            <div class="review-stars">${stars(r.rating)}</div>
                        </div>
                        ${r.title?`<strong>${esc(r.title)}</strong>`:''}
                        <p>${esc(r.body||'')}</p>
                        ${imgs.length && imgs[0] ? `<div class="review-photos" style="display:flex;gap:10px;margin-top:10px;">
                            ${imgs.map(img => `<img src="${esc(img)}" style="width:80px;height:80px;object-fit:cover;border-radius:var(--radius-sm);cursor:pointer;" onclick="openMediaModal('${esc(img)}')">`).join('')}
                        </div>` : ''}
                    </div>`;
                }).join('') : '<p class="text-muted">No reviews yet.</p>'}
            </div>

            ${p.related&&p.related.length?`<div class="section reveal"><div class="section-title"><h2>You May Also Like</h2><div class="line"></div></div><div class="product-grid">${p.related.map(productCard).join('')}</div></div>`:''}
        </div>
        <style>
            .thumb.active { border-color: var(--accent) !important; }
        </style>`;
        
        setTimeout(initScrollReveal, 100);
        let selectedSize = '', selectedColor = '';
        $$('.size-btn:not(.oos)').forEach(btn => btn.addEventListener('click', () => {
            $$('.size-btn').forEach(b=>b.classList.remove('selected')); btn.classList.add('selected'); selectedSize = btn.dataset.size;
        }));
        $$('.color-btn').forEach(btn => btn.addEventListener('click', () => {
            $$('.color-btn').forEach(b=>b.classList.remove('selected')); btn.classList.add('selected'); selectedColor = btn.dataset.color;
        }));
        window.addToCartDetail = async (pid) => {
            if (!state.token) return navigate('login');
            const variant = p.variants.find(v => (!selectedSize || v.size===selectedSize) && (!selectedColor || v.color===selectedColor));
            const qty = parseInt($('#detail-qty').value) || 1;
            try { await api('/cart', 'POST', { product_id: pid, variant_id: variant?.id, quantity: qty }); toast('Added to cart!', 'success'); fetchCounts(); } catch(e) { toast(e.message, 'error'); }
        };
        window.changeQty = (d) => { const el=$('#detail-qty'); el.value = Math.max(1, Math.min(10, parseInt(el.value)+d)); };
        
        if ($('#submit-review-form')) {
            $('#submit-review-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                try {
                    await api('/reviews', 'POST', {
                        product_id: p.id,
                        rating: parseInt($('#review-rating').value),
                        title: $('#review-title').value,
                        body: $('#review-body').value,
                        photo_url: $('#review-photo').value
                    });
                    toast('Review submitted successfully!', 'success');
                    $('#review-form-container').style.display = 'none';
                    setTimeout(() => renderProductDetail(slug), 500); // Reload to show review
                } catch(err) {
                    toast(err.message, 'error');
                }
            });
        }
    } catch(e) { app.innerHTML = `<div class="container empty-state"><i class="fas fa-exclamation-circle"></i><h3>Product not found</h3><a href="#shop" class="btn btn-primary">Back to Shop</a></div>`; }
}

// ─── Auth Views ────────────────────────────────────────────────────────────
function renderLogin() {
    app.innerHTML = `<div class="form-container" style="max-width: 420px; margin: 2rem auto; text-align: center;">
        <h2 style="margin-bottom: 0.5rem;">Welcome to LUXE</h2>
        <p class="text-muted" style="margin-bottom: 2rem;">Log in or sign up seamlessly</p>
        
        <div id="login-main" class="reveal">
            <div id="otp-step-1">
                <form id="send-otp-form">
                    <div class="form-group" style="text-align: left;">
                        <label>Mobile Number</label>
                        <div style="display:flex;align-items:center;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-sm);padding-left:1rem;">
                            <span style="color:var(--text-secondary);">+91</span>
                            <input type="tel" id="otp-mobile" required pattern="[0-9]{10}" placeholder="10-digit mobile" style="border:none;outline:none;box-shadow:none;width:100%;background:transparent;">
                        </div>
                    </div>
                    <button type="submit" class="btn btn-primary btn-full btn-lg" id="send-otp-btn" style="margin-bottom: 1rem;"><i class="fas fa-mobile-alt"></i> Send OTP</button>
                </form>
            </div>

            <div id="otp-step-2" style="display:none;">
                <form id="verify-otp-form">
                    <p style="font-size:0.9rem; margin-bottom:1rem; color:var(--text-secondary);">OTP sent to <strong id="display-mobile"></strong></p>
                    <div class="form-group" style="text-align: left;">
                        <label>Enter OTP</label>
                        <input type="text" id="otp-code" required placeholder="4-digit code" pattern="[0-9]{4}">
                    </div>
                    <button type="submit" class="btn btn-primary btn-full btn-lg" id="verify-otp-btn" style="margin-bottom: 1rem;"><i class="fas fa-check-circle"></i> Verify & Login</button>
                    <a href="#" id="change-mobile-btn" style="font-size:0.85rem; color:var(--accent);">Change Mobile Number</a>
                </form>
            </div>

            <div style="margin: 1rem 0; text-align: center; position: relative;">
                <hr style="border:0; border-top:1px solid var(--border); margin:0;">
                <span style="position: absolute; top:-10px; left:50%; transform:translateX(-50%); background:var(--bg-card); padding:0 10px; font-size:0.85rem; color:var(--text-secondary);">OR LOGIN WITH PASSWORD</span>
            </div>

            <form id="password-login-form">
                <div class="form-group" style="text-align: left;">
                    <label>Mobile Number or Email</label>
                    <input type="text" id="login-id" required placeholder="Enter mobile or email">
                </div>
                <div class="form-group" style="text-align: left;">
                    <label>Password</label>
                    <input type="password" id="login-pw" required placeholder="Enter password" minlength="6">
                </div>
                <button type="submit" class="btn btn-accent btn-full btn-lg" id="pw-login-btn">Login</button>
            </form>

            <div style="margin-top: 1rem; font-size: 0.9rem;">
                <a href="#" id="show-register-btn" style="color:var(--accent);">New user? Create Account</a>
            </div>
        </div>

        <div id="register-section" style="display:none;" class="reveal">
            <h3 style="margin-bottom:1rem;">Create Account</h3>
            <form id="register-form">
                <div class="form-group" style="text-align: left;"><label>Full Name</label><input type="text" id="reg-name" required></div>
                <div class="form-group" style="text-align: left;"><label>Mobile Number</label>
                    <div style="display:flex;align-items:center;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-sm);padding-left:1rem;">
                        <span style="color:var(--text-secondary);">+91</span>
                        <input type="tel" id="reg-mobile" required pattern="[0-9]{10}" placeholder="10-digit mobile" style="border:none;outline:none;box-shadow:none;width:100%;background:transparent;">
                    </div>
                </div>
                <div class="form-group" style="text-align: left;"><label>Email (Optional)</label><input type="email" id="reg-email" placeholder="your@email.com"></div>
                <div class="form-group" style="text-align: left;"><label>Password</label><input type="password" id="reg-pw" required minlength="6" placeholder="Min 6 characters"></div>
                <button type="submit" class="btn btn-primary btn-full btn-lg" id="reg-btn">Create Account</button>
            </form>
            <div style="margin-top:1rem;font-size:0.9rem;"><a href="#" id="show-login-btn" style="color:var(--accent);">Already have an account? Login</a></div>
        </div>
        
        <div class="form-footer mt-2"><a href="#admin-login">Admin Login \u2192</a></div>
    </div>`;
    
    setTimeout(initScrollReveal, 100);

    // Toggle between login and register
    $('#show-register-btn').addEventListener('click', (e) => {
        e.preventDefault();
        $('#login-main').style.display = 'none';
        $('#register-section').style.display = 'block';
    });
    $('#show-login-btn').addEventListener('click', (e) => {
        e.preventDefault();
        $('#register-section').style.display = 'none';
        $('#login-main').style.display = 'block';
    });

    // Custom Mock OTP Flow
    let currentMobile = '';

    $('#send-otp-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        currentMobile = $('#otp-mobile').value;
        const btn = $('#send-otp-btn');
        btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Sending...';
        
        try {
            const d = await api('/auth/send-otp', 'POST', { mobile_number: currentMobile });
            toast(d.message, 'info');
            $('#otp-step-1').style.display = 'none';
            $('#otp-step-2').style.display = 'block';
            $('#display-mobile').textContent = '+91 ' + currentMobile;
        } catch (e) {
            toast(e.message || 'Failed to send OTP', 'error');
        } finally {
            btn.disabled = false; btn.innerHTML = '<i class="fas fa-mobile-alt"></i> Send OTP';
        }
    });

    $('#change-mobile-btn').addEventListener('click', (e) => {
        e.preventDefault();
        $('#otp-step-2').style.display = 'none';
        $('#otp-step-1').style.display = 'block';
    });

    $('#verify-otp-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const code = $('#otp-code').value;
        const btn = $('#verify-otp-btn');
        btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Verifying...';

        try {
            const d = await api('/auth/verify-otp', 'POST', { mobile_number: currentMobile, otp: code });
            setAuth(d.token, { name: d.user.name, role: d.user.role, id: d.user.id }); 
            toast(d.is_new ? 'Account created! Welcome.' : 'Welcome back!', 'success');
            navigate(d.user.role === 'admin' ? 'admin' : 'dashboard');
        } catch (e) {
            toast(e.message || 'Invalid OTP', 'error');
        } finally {
            btn.disabled = false; btn.innerHTML = '<i class="fas fa-check-circle"></i> Verify & Login';
        }
    });

    // Password Login
    $('#password-login-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = $('#pw-login-btn');
        btn.disabled = true; btn.textContent = 'Logging in...';
        try {
            const d = await api('/auth/login', 'POST', {
                mobile_number: $('#login-id').value,
                password: $('#login-pw').value
            });
            setAuth(d.token, { name: d.name, role: d.role, id: d.user_id });
            toast('Welcome back!', 'success');
            navigate(d.role === 'admin' ? 'admin' : 'dashboard');
        } catch (e) {
            toast(e.message || 'Login failed', 'error');
        } finally {
            btn.disabled = false; btn.textContent = 'Login';
        }
    });

    // Register
    $('#register-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = $('#reg-btn');
        btn.disabled = true; btn.textContent = 'Creating...';
        try {
            const d = await api('/auth/register', 'POST', {
                name: $('#reg-name').value,
                mobile_number: $('#reg-mobile').value,
                email: $('#reg-email').value || undefined,
                password: $('#reg-pw').value
            });
            setAuth(d.token, { name: d.name, role: 'customer', id: d.user_id });
            toast('Account created! Welcome to LUXE!', 'success');
            navigate('dashboard');
        } catch (e) {
            toast(e.message || 'Registration failed', 'error');
        } finally {
            btn.disabled = false; btn.textContent = 'Create Account';
        }
    });
}

function renderAdminLogin() {
    app.innerHTML = `<div class="form-container"><h2>Admin Access</h2><form id="admin-form">
        <div class="form-group"><label>Username</label><input type="text" id="adm-user" required></div>
        <div class="form-group"><label>Password</label><input type="password" id="adm-pw" required></div>
        <button type="submit" class="btn btn-accent btn-full btn-lg">Admin Login</button></form></div>`;
    $('#admin-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        try { const d = await api('/auth/admin-login', 'POST', { username: $('#adm-user').value, password: $('#adm-pw').value });
            setAuth(d.token, { name: d.name, role: 'admin' }); toast('Admin access granted', 'success'); navigate('admin');
        } catch(e) { toast(e.message, 'error'); }
    });
}

// ─── Cart ──────────────────────────────────────────────────────────────────
async function renderCart() {
    if (!state.token) return navigate('login');
    app.innerHTML = `<div class="container"><h1 class="mb-3">Shopping Bag</h1><div id="cart-content">Loading...</div></div>`;
    try {
        const items = await api('/cart');
        state.cart = items;
        const active = items.filter(i => !i.saved_for_later);
        const saved = items.filter(i => i.saved_for_later);
        if (active.length === 0 && saved.length === 0) {
            $('#cart-content').innerHTML = `<div class="empty-state"><i class="fas fa-shopping-bag"></i><h3>Your bag is empty</h3><p>Looks like you haven't added anything yet.</p><a href="#shop" class="btn btn-primary">Start Shopping</a></div>`;
            return;
        }
        const subtotal = active.reduce((s, i) => s + i.price * i.quantity, 0);
        const shipping = subtotal >= 999 ? 0 : 99;
        $('#cart-content').innerHTML = `<div class="cart-layout"><div>
            ${active.map(i => `<div class="cart-item"><img src="${esc(i.image_url)}" alt="${esc(i.name)}">
                <div class="cart-item-info"><h3>${esc(i.name)}</h3><div class="variant">${i.size||''} ${i.color||''}</div>
                    <div class="cart-item-price">₹${(i.price*i.quantity).toLocaleString()}</div>
                    <div class="cart-item-actions">
                        <div class="qty-selector"><button onclick="updateCartQty(${i.id},${i.quantity-1})">−</button><input value="${i.quantity}" readonly><button onclick="updateCartQty(${i.id},${i.quantity+1})">+</button></div>
                        <button class="btn btn-ghost btn-sm" onclick="saveForLater(${i.id})"><i class="fas fa-bookmark"></i> Save</button>
                        <button class="btn btn-ghost btn-sm" onclick="removeCartItem(${i.id})" style="color:var(--danger)"><i class="fas fa-trash"></i></button>
                    </div></div></div>`).join('')}
            ${saved.length ? `<h3 class="mt-4 mb-2">Saved for Later (${saved.length})</h3>${saved.map(i => `<div class="cart-item"><img src="${esc(i.image_url)}"><div class="cart-item-info"><h3>${esc(i.name)}</h3><div class="cart-item-price">₹${i.price.toLocaleString()}</div><div class="cart-item-actions"><button class="btn btn-sm btn-outline" onclick="moveToCart(${i.id})">Move to Cart</button><button class="btn btn-ghost btn-sm" onclick="removeCartItem(${i.id})" style="color:var(--danger)"><i class="fas fa-trash"></i></button></div></div></div>`).join('')}` : ''}
        </div>
        </div>
        <div class="cart-summary"><h3>Order Summary</h3>
            <div class="summary-row"><span>Subtotal</span><span>₹${subtotal.toLocaleString()}</span></div>
            <div class="summary-row"><span>Shipping</span><span>${shipping===0?'<span style="color:var(--success)">FREE</span>':'₹'+shipping}</span></div>
            ${subtotal<999?`<div style="color:var(--accent);font-size:0.85rem;margin-bottom:0.5rem">Add ₹${(999-subtotal).toLocaleString()} more for free shipping!</div>`:''}
            <div class="summary-row total"><span>Total</span><span>₹${(subtotal+shipping).toLocaleString()}</span></div>
            
            <div class="shipping-estimator mt-3" style="padding:1rem; border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--bg-card)">
                <h4 style="margin:0 0 0.5rem 0; font-size:0.9rem">Estimate Shipping Delivery</h4>
                <div style="display:flex; gap:5px">
                    <input type="text" id="est-pin" placeholder="Enter Pincode" style="padding:0.4rem; font-size:0.85rem">
                    <button class="btn btn-outline btn-sm" onclick="estimateShipping()">Check</button>
                </div>
                <div id="est-result" style="font-size:0.85rem; margin-top:0.5rem; color:var(--text-secondary);"></div>
            </div>
            
            <a href="#checkout" class="btn btn-primary btn-full mt-3">Proceed to Checkout</a>
            <div class="razorpay-badge mt-2"><i class="fas fa-shield-alt"></i> Protected by Razorpay</div>
            <a href="#shop" class="btn btn-ghost btn-full mt-1">Continue Shopping</a>
        </div></div>`;
        
        window.estimateShipping = () => {
            const pin = $('#est-pin').value;
            if (!/^\d{6}$/.test(pin)) return toast('Enter a valid 6-digit Pincode', 'error');
            const days = Math.floor(Math.random() * 3) + 2;
            const date = new Date(); date.setDate(date.getDate() + days);
            $('#est-result').innerHTML = `<i class="fas fa-truck" style="color:var(--success)"></i> Estimated Delivery by <strong>${date.toLocaleDateString()}</strong>`;
        };
    } catch(e) { toast(e.message, 'error'); }
}
window.updateCartQty = async (id, qty) => { try { await api(`/cart/${id}`, 'PUT', { quantity: qty }); renderCart(); fetchCounts(); } catch(e) { toast(e.message,'error'); }};
window.removeCartItem = async (id) => { try { await api(`/cart/${id}`, 'DELETE'); toast('Removed', 'info'); renderCart(); fetchCounts(); } catch(e) { toast(e.message,'error'); }};
window.saveForLater = async (id) => { try { await api(`/cart/${id}`, 'PUT', { saved_for_later: 1 }); toast('Saved for later', 'info'); renderCart(); fetchCounts(); } catch(e) { toast(e.message,'error'); }};
window.moveToCart = async (id) => { try { await api(`/cart/${id}`, 'PUT', { saved_for_later: 0 }); toast('Moved to cart', 'success'); renderCart(); fetchCounts(); } catch(e) { toast(e.message,'error'); }};

// ═══════════════════════════════════════════════════════════════════════════
// ─── CHECKOUT with RAZORPAY ────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════
async function renderCheckout() {
    if (!state.token) return navigate('login');
    const cartItems = state.cart.filter(i => !i.saved_for_later);
    if (!cartItems.length) { try { state.cart = await api('/cart'); } catch(e) {} const ci = state.cart.filter(i=>!i.saved_for_later); if(!ci.length) return navigate('cart'); }
    const items = state.cart.filter(i => !i.saved_for_later);
    const subtotal = items.reduce((s, i) => s + i.price * i.quantity, 0);
    let addresses = [];
    try { addresses = await api('/addresses'); } catch(e) {}
    app.innerHTML = `<div class="container"><h1 class="mb-3">Checkout</h1>
        <div class="checkout-steps">
            <div class="checkout-step active"><div class="step-circle">1</div><div class="step-label">Address</div></div>
            <div class="checkout-step"><div class="step-circle">2</div><div class="step-label">Payment</div></div>
            <div class="checkout-step"><div class="step-circle">3</div><div class="step-label">Confirm</div></div>
        </div>
        <div class="cart-layout">
            <div>
                <h3 class="mb-2">Shipping Address</h3>
                <div class="address-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
                ${addresses.length ? addresses.map(a => `<div class="order-card address-card" style="cursor:pointer;border:${a.is_default?'2px solid var(--accent)':'1px solid var(--border)'};position:relative" onclick="selectAddr(this)">
                    <input type="radio" name="addr" value="${a.id}" ${a.is_default?'checked':''} style="position:absolute;top:1rem;right:1rem;accent-color:var(--accent)">
                    <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.5rem;color:var(--text-secondary);font-size:0.85rem;text-transform:uppercase;letter-spacing:1px"><i class="fas fa-${a.label.toLowerCase() === 'home' ? 'home' : (a.label.toLowerCase() === 'work' || a.label.toLowerCase() === 'office' ? 'briefcase' : 'map-marker-alt')}"></i> <strong>${esc(a.label)}</strong></div>
                    <strong style="font-size:1.1rem;display:block;margin-bottom:0.25rem">${esc(a.full_name)}</strong>
                    <p style="color:var(--text-secondary);font-size:0.9rem;line-height:1.4;margin-bottom:0.5rem">${esc(a.line1)}${a.line2?', '+esc(a.line2):''}, ${esc(a.city)}, ${esc(a.state)} - ${esc(a.pincode)}</p>
                    <div style="font-size:0.9rem"><strong>Mobile:</strong> ${esc(a.phone)}</div>
                </div>`).join('') : '<div class="empty-state" style="padding:1rem;grid-column:1/-1"><p>No addresses. Add one below.</p></div>'}
                </div>
                <button class="btn btn-outline btn-full mt-2" onclick="$('#inline-addr-form').style.display='block'; this.style.display='none'"><i class="fas fa-plus"></i> Add New Address</button>
                <div id="inline-addr-form" style="display:none; margin-top: 1rem; border: 1px solid var(--border); border-radius: var(--radius-md); padding: 1.5rem; background: var(--bg-card);">
                    <h3 class="mb-2">Add Delivery Address</h3>
                    <form id="checkout-addr-form">
                        <div class="form-row"><div class="form-group"><label>Full Name</label><input id="c-name" required></div><div class="form-group"><label>Phone</label><input id="c-phone" required pattern="\\d{10}" placeholder="10-digit mobile"></div></div>
                        <div class="form-group"><label>Address Line 1</label><input id="c-line1" required></div>
                        <div class="form-group"><label>Address Line 2 (Optional)</label><input id="c-line2"></div>
                        <div class="form-row"><div class="form-group"><label>City</label><input id="c-city" required></div><div class="form-group"><label>State</label><input id="c-state" required></div></div>
                        <div class="form-row"><div class="form-group"><label>Pincode</label><input id="c-pin" required pattern="\\d{6}" placeholder="6-digit PIN"></div><div class="form-group"><label>Label</label><select id="c-label"><option>Home</option><option>Work</option><option>Other</option></select></div></div>
                        <div style="display:flex;gap:10px;margin-top:1rem;">
                            <button type="submit" class="btn btn-primary" style="flex:1">Save Address</button>
                            <button type="button" class="btn btn-outline" style="flex:1" onclick="$('#inline-addr-form').style.display='none'; this.parentElement.parentElement.parentElement.previousElementSibling.style.display='block'">Cancel</button>
                        </div>
                    </form>
                </div>

                <h3 class="mt-4 mb-2">Payment Method</h3>
                <div class="payment-option selected" onclick="selectPayment('ONLINE',this)">
                    <input type="radio" name="payment" value="ONLINE" checked>
                    <i class="fas fa-credit-card"></i>
                    <div><div class="payment-label">Pay Online (Razorpay)</div><div class="payment-desc">UPI, Credit/Debit Cards, Wallets, Net Banking</div></div>
                </div>
                <div class="payment-option mt-1" onclick="selectPayment('COD',this)">
                    <input type="radio" name="payment" value="COD">
                    <i class="fas fa-money-bill-wave"></i>
                    <div><div class="payment-label">Cash on Delivery</div><div class="payment-desc">Pay when you receive your order</div></div>
                </div>

                <h3 class="mt-4 mb-2">Coupon Code</h3>
                <div class="coupon-input"><input type="text" id="coupon-code" placeholder="Enter code"><button class="btn btn-sm btn-accent" onclick="applyCoupon()">Apply</button></div>
                <div id="coupon-msg"></div>
            </div>
            <div class="cart-summary">
                <h3>Order Summary</h3>
                ${items.map(i => `<div class="summary-row"><span>${esc(i.name)} x${i.quantity}</span><span>₹${(i.price*i.quantity).toLocaleString()}</span></div>`).join('')}
                <div class="summary-row"><span>Subtotal</span><span>₹${subtotal.toLocaleString()}</span></div>
                <div class="summary-row"><span>Shipping</span><span>${subtotal>=999?'FREE':'₹99'}</span></div>
                <div id="discount-row"></div>
                <div class="summary-row total"><span>Total</span><span id="checkout-total">₹${(subtotal + (subtotal>=999?0:99)).toLocaleString()}</span></div>
                <button class="btn btn-accent btn-full btn-lg mt-2 pulse" id="place-order-btn" onclick="placeOrder()"><i class="fas fa-lock"></i> Place Order</button>
                <div class="razorpay-badge mt-2" style="justify-content:center"><i class="fas fa-shield-alt"></i> 100% Secure Payment</div>
                <div class="payment-icons mt-2" style="opacity:0.5;font-size:1.2rem"><i class="fab fa-cc-visa"></i><i class="fab fa-cc-mastercard"></i><i class="fab fa-google-pay"></i><i class="fas fa-qrcode"></i></div>
            </div>
        </div></div>`;

    window.selectAddr = (el) => { 
        $$('[name=addr]').forEach(r => r.checked = false); 
        $$('.address-card').forEach(c => c.style.border = '1px solid var(--border)');
        el.querySelector('input').checked = true; 
        el.style.border = '2px solid var(--accent)';
    };
    window.selectPayment = (val, el) => {
        $$('.payment-option').forEach(p => { p.classList.remove('selected'); p.querySelector('input').checked = false; });
        el.classList.add('selected'); el.querySelector('input').checked = true;
    };
    let appliedCoupon = '';
    window.applyCoupon = async () => {
        const code = $('#coupon-code').value;
        try { const d = await api('/coupons/validate', 'POST', { code }); appliedCoupon = code;
            $('#coupon-msg').innerHTML = `<span style="color:var(--success)"><i class="fas fa-check-circle"></i> Coupon applied! ${d.coupon.discount_type==='percentage'?d.coupon.discount_value+'% off':'₹'+d.coupon.discount_value+' off'}</span>`;
            toast('Coupon applied!', 'success');
        } catch(e) { appliedCoupon = ''; $('#coupon-msg').innerHTML = `<span style="color:var(--danger)">${e.message}</span>`; }
    };

    if ($('#checkout-addr-form')) {
        $('#checkout-addr-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            try {
                await api('/addresses', 'POST', {
                    full_name: $('#c-name').value, phone: $('#c-phone').value,
                    line1: $('#c-line1').value, line2: $('#c-line2').value,
                    city: $('#c-city').value, state: $('#c-state').value,
                    pincode: $('#c-pin').value, label: $('#c-label').value, is_default: true
                });
                toast('Address added successfully', 'success');
                renderCheckout();
            } catch(e) { toast(e.message, 'error'); }
        });
    }

    // ─── PLACE ORDER with RAZORPAY ─────────────────────────────────────────
    window.placeOrder = async () => {
        const addrEl = document.querySelector('[name=addr]:checked');
        const payment = document.querySelector('[name=payment]:checked')?.value || 'ONLINE';
        if (!addrEl) { toast('Please add or select a delivery address first', 'warning'); return; }

        const btn = $('#place-order-btn');
        btn.disabled = true;
        btn.innerHTML = '<div class="spinner" style="width:18px;height:18px;border:2px solid #fff;border-top-color:transparent;border-radius:50%;animation:spin 0.8s linear infinite;display:inline-block"></div> Processing...';

        if (payment === 'ONLINE') {
            // Create Razorpay Order
            try {
                const rzOrder = await api('/razorpay/create-order', 'POST', { coupon_code: appliedCoupon });
                const options = {
                    key: state.razorpayKeyId || rzOrder.key_id,
                    amount: rzOrder.amount,
                    currency: 'INR',
                    name: 'LUXE Fashion',
                    description: `Payment for ${items.length} item(s)`,
                    order_id: rzOrder.order_id,
                    handler: async function(response) {
                        // Verify payment
                        try {
                            await api('/razorpay/verify-payment', 'POST', {
                                razorpay_order_id: response.razorpay_order_id,
                                razorpay_payment_id: response.razorpay_payment_id,
                                razorpay_signature: response.razorpay_signature
                            });
                            // Place the order with payment details
                            const d = await api('/checkout', 'POST', {
                                address_id: addrEl?.value, payment_method: 'ONLINE',
                                coupon_code: appliedCoupon,
                                razorpay_payment_id: response.razorpay_payment_id,
                                razorpay_order_id: response.razorpay_order_id
                            });
                            toast('🎉 Payment successful! Order placed!', 'success');
                            state.cart = []; fetchCounts();
                            navigate('order/' + d.order_number);
                        } catch(e) { toast('Payment verified but order failed: ' + e.message, 'error'); btn.disabled = false; btn.innerHTML = '<i class="fas fa-lock"></i> Place Order'; }
                    },
                    prefill: {
                        name: state.user?.name || '',
                        email: state.user?.email || '',
                        contact: state.user?.mobile_number || ''
                    },
                    theme: { color: '#c9a84c' },
                    modal: {
                        ondismiss: function() {
                            toast('Payment cancelled', 'warning');
                            btn.disabled = false;
                            btn.innerHTML = '<i class="fas fa-lock"></i> Place Order';
                        }
                    }
                };
                const rzp = new Razorpay(options);
                rzp.on('payment.failed', function(resp) {
                    toast('Payment failed: ' + resp.error.description, 'error');
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fas fa-lock"></i> Place Order';
                });
                rzp.open();
            } catch(e) {
                toast('Failed to create payment: ' + e.message, 'error');
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-lock"></i> Place Order';
            }
        } else {
            // COD
            try {
                const d = await api('/checkout', 'POST', { address_id: addrEl?.value, payment_method: 'COD', coupon_code: appliedCoupon });
                toast('🎉 Order placed! ' + d.message, 'success'); state.cart = []; fetchCounts(); navigate('order/' + d.order_number);
            } catch(e) { toast(e.message, 'error'); btn.disabled = false; btn.innerHTML = '<i class="fas fa-lock"></i> Place Order'; }
        }
    };
}

// ─── Dashboard ─────────────────────────────────────────────────────────────
async function renderDashboard() {
    if (!state.token) return navigate('login');
    try { const me = await api('/auth/me'); const orders = await api('/orders');
    app.innerHTML = `<div class="container"><div class="dashboard-layout">
        <div class="dash-sidebar">
            <a href="#dashboard" class="active"><i class="fas fa-tachometer-alt"></i> Dashboard</a>
            <a href="#orders"><i class="fas fa-box"></i> Orders</a>
            <a href="#wishlist"><i class="fas fa-heart"></i> Wishlist</a>
            <a href="#addresses"><i class="fas fa-map-marker-alt"></i> Addresses</a>
            <a href="#wallet"><i class="fas fa-wallet"></i> Wallet</a>
            <a href="#loyalty"><i class="fas fa-gem"></i> Loyalty</a>
            <a href="#profile"><i class="fas fa-user-edit"></i> Profile</a>
            <a href="#notifications"><i class="fas fa-bell"></i> Notifications</a>
            <a href="#contact"><i class="fas fa-headset"></i> Support</a>
        </div>
        <div>
            <h1 class="mb-3">Welcome, ${esc(me.name)}</h1>
            <div class="stat-cards">
                <div class="stat-card"><div class="stat-icon" style="background:var(--accent-light);color:var(--accent)"><i class="fas fa-box"></i></div><div class="stat-value">${orders.length}</div><div class="stat-label">Total Orders</div></div>
                <div class="stat-card"><div class="stat-icon" style="background:rgba(46,204,113,0.1);color:var(--success)"><i class="fas fa-wallet"></i></div><div class="stat-value">₹${(me.wallet_balance||0).toLocaleString()}</div><div class="stat-label">Wallet</div></div>
                <div class="stat-card"><div class="stat-icon" style="background:rgba(52,152,219,0.1);color:var(--info)"><i class="fas fa-gem"></i></div><div class="stat-value">${me.loyalty_points||0}</div><div class="stat-label">Loyalty Points</div></div>
                <div class="stat-card"><div class="stat-icon" style="background:rgba(155,89,182,0.1);color:#9b59b6"><i class="fas fa-gift"></i></div><div class="stat-value">${esc(me.referral_code)}</div><div class="stat-label">Referral Code</div></div>
            </div>
            <h2 class="mb-2">Recent Orders</h2>
            ${orders.length ? orders.slice(0,5).map(o => orderCardHTML(o)).join('') : '<div class="empty-state"><i class="fas fa-box-open"></i><h3>No orders yet</h3><a href="#shop" class="btn btn-primary">Start Shopping</a></div>'}
        </div></div></div>`;
    } catch(e) { toast(e.message, 'error'); }
}

function orderCardHTML(o) {
    return `<div class="order-card" onclick="navigate('order/${o.order_number}')" style="cursor:pointer">
        <div class="order-header"><div><strong>${esc(o.order_number)}</strong><br><small class="text-muted">${new Date(o.created_at).toLocaleDateString()}</small></div>
        <span class="order-status status-${o.status}">${o.status.replace(/_/g,' ')}</span></div>
        <div class="flex items-center justify-between"><span>${o.items?o.items.length:0} item(s)</span><strong>₹${o.total.toLocaleString()}</strong></div>
        ${o.payment_method==='ONLINE'?'<div class="razorpay-badge" style="margin-top:0.5rem"><i class="fas fa-check-circle"></i> Paid Online</div>':''}</div>`;
}

async function renderOrders() { if(!state.token) return navigate('login'); try { const orders = await api('/orders');
    app.innerHTML = `<div class="container"><h1 class="mb-3">My Orders</h1>${orders.length ? orders.map(orderCardHTML).join('') : '<div class="empty-state"><i class="fas fa-box-open"></i><h3>No orders yet</h3><a href="#shop" class="btn btn-primary">Start Shopping</a></div>'}</div>`;
} catch(e){toast(e.message,'error');}}

async function renderOrderDetail(num) { if(!state.token) return navigate('login'); try { const o = await api(`/orders/${num}`);
    const statuses = ['PENDING','CONFIRMED','PACKED','SHIPPED','OUT_FOR_DELIVERY','DELIVERED'];
    const idx = statuses.indexOf(o.status);
    app.innerHTML = `<div class="container"><h1 class="mb-2">Order ${esc(o.order_number)}</h1><span class="order-status status-${o.status}">${o.status.replace(/_/g,' ')}</span>
        ${o.payment_method==='ONLINE'?'<div class="razorpay-badge ml-2"><i class="fas fa-check-circle"></i> Paid via Razorpay</div>':''}
        <div class="timeline mt-3">${statuses.map((s,i)=>`<div class="timeline-item ${i<=idx?'done':''} ${i===idx?'active':''}"><strong>${s.replace(/_/g,' ')}</strong></div>`).join('')}</div>
        <h3 class="mt-4 mb-2">Items</h3>${o.items.map(i=>`<div class="cart-item"><img src="${esc(i.product_image||'')}" style="width:60px;height:80px"><div class="cart-item-info"><h3>${esc(i.product_name)}</h3><div class="variant">${i.size||''} ${i.color||''}</div><div>₹${i.price.toLocaleString()} x ${i.quantity}</div></div></div>`).join('')}
        <div class="mt-3"><div class="summary-row"><span>Subtotal</span><span>₹${o.subtotal.toLocaleString()}</span></div>
        ${o.discount>0?`<div class="summary-row"><span>Discount</span><span style="color:var(--success)">-₹${o.discount.toLocaleString()}</span></div>`:''}
        <div class="summary-row"><span>Shipping</span><span>${o.shipping===0?'FREE':'₹'+o.shipping}</span></div>
        <div class="summary-row total"><span>Total</span><span>₹${o.total.toLocaleString()}</span></div></div>
        <div class="mt-3">
            ${o.status==='PENDING'||o.status==='CONFIRMED'?`<button class="btn btn-danger" onclick="cancelOrder('${o.order_number}')">Cancel Order</button>`:''}
            ${['CONFIRMED','SHIPPED','DELIVERED'].includes(o.status)?`<button class="btn btn-outline ml-2" onclick="downloadInvoice('${o.order_number}')"><i class="fas fa-file-pdf"></i> Download Invoice</button>`:''}
        </div>
        </div>`;
} catch(e){toast(e.message,'error');}}
window.cancelOrder = async (num) => { if(!confirm('Cancel this order?')) return; try { await api(`/orders/${num}/cancel`, 'PUT'); toast('Order cancelled','info'); renderOrderDetail(num); } catch(e){toast(e.message,'error');}};
window.downloadInvoice = async (num) => {
    try {
        toast('Generating invoice...', 'info');
        const res = await fetch(`${API}/orders/${num}/invoice`, { headers: { Authorization: `Bearer ${state.token}` } });
        if (!res.ok) throw new Error('Invoice not available');
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a'); a.href = url; a.download = `Invoice_${num}.pdf`;
        document.body.appendChild(a); a.click(); a.remove();
        window.URL.revokeObjectURL(url);
    } catch(e) { toast(e.message, 'error'); }
};

// ─── Wishlist, Profile, Addresses, Wallet, Loyalty, Notifications ─────────
async function renderWishlist() { if(!state.token) return navigate('login'); try { const items = await api('/wishlist');
    app.innerHTML = `<div class="container"><h1 class="mb-3">My Wishlist</h1>${items.length ? `<div class="product-grid">${items.map(i=>`<div class="product-card"><div class="card-img" onclick="navigate('product/${i.slug}')"><img src="${esc(i.image_url)}" loading="lazy"></div><div class="card-body"><div class="card-title">${esc(i.name)}</div><div class="card-price"><span class="price">₹${i.price.toLocaleString()}</span></div><div class="flex gap-1 mt-2"><button class="btn btn-primary btn-sm" onclick="quickAdd(${i.product_id})"><i class="fas fa-shopping-bag"></i> Add to Cart</button><button class="btn btn-ghost btn-sm" onclick="removeWishlist(${i.product_id})" style="color:var(--danger)"><i class="fas fa-trash"></i></button></div></div></div>`).join('')}</div>` : '<div class="empty-state"><i class="fas fa-heart"></i><h3>Your wishlist is empty</h3><a href="#shop" class="btn btn-primary">Explore Products</a></div>'}</div>`;
} catch(e){toast(e.message,'error');}}
window.removeWishlist = async (pid) => { try{await api(`/wishlist/${pid}`,'DELETE'); toast('Removed','info'); renderWishlist(); fetchCounts();}catch(e){toast(e.message,'error');}};

async function renderProfile() { if(!state.token) return navigate('login'); try { const me = await api('/auth/me');
    app.innerHTML = `<div class="container"><div class="form-container"><h2>Edit Profile</h2><form id="profile-form">
        <div class="form-group"><label>Full Name</label><input type="text" id="pf-name" value="${esc(me.name)}"></div>
        <div class="form-group"><label>Email</label><input type="email" id="pf-email" value="${esc(me.email||'')}"></div>
        <div class="form-group"><label>Mobile</label><input type="text" value="${esc(me.mobile_number)}" disabled></div>
        <div class="form-row"><div class="form-group"><label>Date of Birth</label><input type="date" id="pf-dob" value="${me.profile?.dob||''}"></div>
        <div class="form-group"><label>Gender</label><select id="pf-gender"><option value="">Select</option><option ${me.profile?.gender==='Male'?'selected':''}>Male</option><option ${me.profile?.gender==='Female'?'selected':''}>Female</option><option ${me.profile?.gender==='Other'?'selected':''}>Other</option></select></div></div>
        <button type="submit" class="btn btn-primary btn-full">Save Changes</button></form>
        <h3 class="mt-4 mb-2">Change Password</h3><form id="pw-form">
        <div class="form-group"><label>Current Password</label><input type="password" id="pw-cur" required></div>
        <div class="form-group"><label>New Password</label><input type="password" id="pw-new" required minlength="6"></div>
        <button type="submit" class="btn btn-outline btn-full">Change Password</button></form></div></div>`;
    $('#profile-form').addEventListener('submit', async(e)=>{e.preventDefault(); try{await api('/auth/update-profile','PUT',{name:$('#pf-name').value,email:$('#pf-email').value,dob:$('#pf-dob').value,gender:$('#pf-gender').value}); toast('Profile updated','success');}catch(e){toast(e.message,'error');}});
    $('#pw-form').addEventListener('submit', async(e)=>{e.preventDefault(); try{await api('/auth/change-password','PUT',{current_password:$('#pw-cur').value,new_password:$('#pw-new').value}); toast('Password changed','success'); $('#pw-form').reset();}catch(e){toast(e.message,'error');}});
} catch(e){toast(e.message,'error');}}

async function renderAddresses() { if(!state.token) return navigate('login'); try { const addrs = await api('/addresses');
    app.innerHTML = `<div class="container"><h1 class="mb-3">My Addresses</h1>
        ${addrs.map(a=>`<div class="order-card"><div class="flex justify-between items-center"><div><strong>${esc(a.label)}</strong> ${a.is_default?'<span class="order-status status-CONFIRMED">Default</span>':''}<br>${esc(a.full_name)}, ${esc(a.phone)}<br>${esc(a.line1)}${a.line2?', '+esc(a.line2):''}<br>${esc(a.city)}, ${esc(a.state)} - ${esc(a.pincode)}</div>
        <div>
            ${!a.is_default ? `<button class="btn btn-ghost btn-sm" onclick="makeDefaultAddr(${a.id})" style="color:var(--accent);margin-right:8px;"><i class="fas fa-star"></i> Default</button>` : ''}
            <button class="btn btn-ghost btn-sm" onclick="deleteAddr(${a.id})" style="color:var(--danger)"><i class="fas fa-trash"></i></button>
        </div></div></div>`).join('')}
        <div class="form-container mt-3"><h2>Add New Address</h2><form id="addr-form">
        <div class="form-row"><div class="form-group"><label>Full Name</label><input id="a-name" required></div><div class="form-group"><label>Phone</label><input id="a-phone" required></div></div>
        <div class="form-group"><label>Address Line 1</label><input id="a-line1" required></div>
        <div class="form-group"><label>Address Line 2</label><input id="a-line2"></div>
        <div class="form-row"><div class="form-group"><label>City</label><input id="a-city" required></div><div class="form-group"><label>State</label><input id="a-state" required></div></div>
        <div class="form-row"><div class="form-group"><label>Pincode</label><input id="a-pin" required></div><div class="form-group"><label>Label</label><select id="a-label"><option>Home</option><option>Work</option><option>Other</option></select></div></div>
        <button type="submit" class="btn btn-primary btn-full">Save Address</button></form></div></div>`;
    $('#addr-form').addEventListener('submit',async(e)=>{e.preventDefault();try{await api('/addresses','POST',{full_name:$('#a-name').value,phone:$('#a-phone').value,line1:$('#a-line1').value,line2:$('#a-line2').value,city:$('#a-city').value,state:$('#a-state').value,pincode:$('#a-pin').value,label:$('#a-label').value,is_default:true}); toast('Address added','success'); renderAddresses();}catch(e){toast(e.message,'error');}});
} catch(e){toast(e.message,'error');}}
window.deleteAddr = async(id)=>{try{await api(`/addresses/${id}`,'DELETE'); toast('Deleted','info'); renderAddresses();}catch(e){toast(e.message,'error');}};
window.makeDefaultAddr = async(id)=>{try{await api(`/addresses/${id}`,'PUT',{is_default:true}); toast('Set as default','success'); renderAddresses();}catch(e){toast(e.message,'error');}};

async function renderWallet() { if(!state.token) return navigate('login'); try { const w = await api('/wallet');
    app.innerHTML = `<div class="container"><h1 class="mb-3">My Wallet</h1><div class="wallet-card"><div class="wallet-label">Available Balance</div><div class="wallet-balance">₹${w.balance.toLocaleString()}</div></div>
        <h3 class="mt-4 mb-2">Transaction History</h3>${w.transactions.length?w.transactions.map(t=>`<div class="order-card"><div class="flex justify-between"><div><strong>${t.type==='credit'?'+':'−'}₹${Math.abs(t.amount).toLocaleString()}</strong><br><small class="text-muted">${esc(t.description)}</small></div><div><small>${new Date(t.created_at).toLocaleDateString()}</small><br><span class="order-status ${t.type==='credit'?'status-DELIVERED':'status-CANCELLED'}">${t.type}</span></div></div></div>`).join(''):'<p class="text-muted">No transactions yet</p>'}</div>`;
} catch(e){toast(e.message,'error');}}

async function renderLoyalty() { if(!state.token) return navigate('login'); try { const l = await api('/loyalty');
    app.innerHTML = `<div class="container"><h1 class="mb-3">Loyalty Points</h1><div class="wallet-card" style="background:linear-gradient(135deg,#4a0e4e,#1a0533)"><div class="wallet-label">Available Points</div><div class="wallet-balance">${l.total_points} pts</div><div style="opacity:0.7;margin-top:0.5rem">= ₹${l.total_points} discount on checkout</div></div>
        <h3 class="mt-4 mb-2">Points History</h3>${l.history.map(h=>`<div class="order-card"><div class="flex justify-between"><div><strong>${h.type==='earn'?'+':'-'}${h.points} pts</strong><br><small class="text-muted">${esc(h.description)}</small></div><small>${new Date(h.created_at).toLocaleDateString()}</small></div></div>`).join('')}</div>`;
} catch(e){toast(e.message,'error');}}

async function renderNotifications() { if(!state.token) return navigate('login'); try { const notes = await api('/notifications');
    await api('/notifications/read-all','PUT'); fetchCounts();
    app.innerHTML = `<div class="container"><h1 class="mb-3">Notifications</h1>${notes.length?notes.map(n=>`<div class="notif-item ${n.is_read?'':'unread'}"><div class="notif-icon"><i class="fas fa-${n.type==='order'?'box':n.type==='reward'?'gift':'bell'}"></i></div><div class="notif-text"><h4>${esc(n.title)}</h4><p>${esc(n.message)}</p></div><div class="notif-time">${new Date(n.created_at).toLocaleDateString()}</div></div>`).join(''):'<div class="empty-state"><i class="fas fa-bell"></i><h3>No notifications</h3></div>'}</div>`;
} catch(e){toast(e.message,'error');}}

// ─── Contact / Blog ────────────────────────────────────────────────────────
async function renderContact() {
    app.innerHTML = `<div class="container"><h1 class="mb-3">Get in Touch</h1>
        <div class="grid-2 mb-4"><div class="contact-info-card reveal"><i class="fas fa-envelope"></i><h3>Email</h3><p>support@luxe.com</p></div><div class="contact-info-card reveal"><i class="fab fa-whatsapp"></i><h3>WhatsApp</h3><p>+91 99999 99999</p></div></div>
        <div class="form-container"><h2>Submit a Ticket</h2><form id="ticket-form">
        <div class="form-group"><label>Subject</label><input id="t-sub" required></div>
        <div class="form-group"><label>Message</label><textarea id="t-msg" rows="5" required></textarea></div>
        <button type="submit" class="btn btn-primary btn-full">${state.token?'Submit Ticket':'Login to Submit'}</button></form></div></div>`;
    setTimeout(initScrollReveal, 100);
    if(state.token) $('#ticket-form').addEventListener('submit',async(e)=>{e.preventDefault();try{await api('/support','POST',{subject:$('#t-sub').value,message:$('#t-msg').value});toast('Ticket submitted!','success');$('#ticket-form').reset();}catch(e){toast(e.message,'error');}});
}

async function renderBlog() { try { const posts = await api('/blog');
    app.innerHTML = `<div class="container"><div class="section-title"><h2>The LUXE Journal</h2><p>Fashion insights and style guides</p><div class="line"></div></div>
        ${posts.length?`<div class="blog-grid">${posts.map(p=>`<div class="blog-card reveal-scale"><img src="${esc(p.image_url||'https://images.unsplash.com/photo-1445205170230-053b83016050?w=600')}" loading="lazy"><div class="blog-body"><div class="blog-category">${esc(p.category||'Fashion')}</div><h3>${esc(p.title)}</h3><p>${esc(p.excerpt||'')}</p></div></div>`).join('')}</div>`:'<div class="empty-state"><i class="fas fa-newspaper"></i><h3>Coming soon</h3><p>Our blog is being curated.</p></div>'}</div>`;
    setTimeout(initScrollReveal, 100);
} catch(e){toast(e.message,'error');}}

// ═══════════════════════════════════════════════════════════════════════════
// ─── ADMIN PANEL ───────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════
async function renderAdmin(tab = 'dashboard') {
    if (!state.token || !isAdmin()) return navigate('admin-login');
    const tabs = [
        {id:'dashboard',icon:'fa-tachometer-alt',label:'Dashboard'},
        {id:'admin-products',icon:'fa-box',label:'Products'},
        {id:'admin-orders',icon:'fa-shopping-cart',label:'Orders'},
        {id:'admin-customers',icon:'fa-users',label:'Customers'},
        {id:'admin-reviews',icon:'fa-star',label:'Reviews'},
        {id:'admin-coupons',icon:'fa-ticket-alt',label:'Coupons'},
        {id:'admin-inventory',icon:'fa-warehouse',label:'Inventory'},
        {id:'admin-returns',icon:'fa-undo',label:'Returns'},
        {id:'admin-tickets',icon:'fa-headset',label:'Support'},
        {id:'admin-inventory-logs',icon:'fa-clipboard-list',label:'Inv. Logs'},
        {id:'admin-abandoned',icon:'fa-shopping-basket',label:'Abandoned'},
        {id:'admin-settings',icon:'fa-cog',label:'Settings'}
    ];
    app.innerHTML = `<div class="container"><div class="admin-layout">
        <div class="admin-sidebar"><h3>Admin</h3>${tabs.map(t=>`<a href="#${t.id}" class="${tab===t.id||tab===t.id.replace('admin-','')?'active':''}" onclick="event.preventDefault();renderAdmin('${t.id.replace('admin-','')}')"><i class="fas ${t.icon}"></i> ${t.label}</a>`).join('')}</div>
        <div id="admin-content">Loading...</div></div></div>`;
    const content = $('#admin-content');
    try {
        if (tab === 'dashboard') {
            const d = await api('/admin/analytics');
            content.innerHTML = `<h1 class="mb-3">Admin Dashboard</h1>
                <div class="stat-cards">
                    <div class="stat-card"><div class="stat-icon" style="background:var(--accent-light);color:var(--accent)"><i class="fas fa-rupee-sign"></i></div><div class="stat-value">₹${d.total_revenue.toLocaleString()}</div><div class="stat-label">Total Revenue</div></div>
                    <div class="stat-card"><div class="stat-icon" style="background:rgba(46,204,113,0.1);color:var(--success)"><i class="fas fa-shopping-cart"></i></div><div class="stat-value">${d.total_orders}</div><div class="stat-label">Total Orders</div></div>
                    <div class="stat-card"><div class="stat-icon" style="background:rgba(52,152,219,0.1);color:var(--info)"><i class="fas fa-users"></i></div><div class="stat-value">${d.total_customers}</div><div class="stat-label">Customers</div></div>
                    <div class="stat-card"><div class="stat-icon" style="background:rgba(155,89,182,0.1);color:#9b59b6"><i class="fas fa-box"></i></div><div class="stat-value">${d.total_products}</div><div class="stat-label">Products</div></div>
                    <div class="stat-card"><div class="stat-icon" style="background:rgba(231,76,60,0.1);color:var(--danger)"><i class="fas fa-exclamation-triangle"></i></div><div class="stat-value">${d.low_stock}</div><div class="stat-label">Low Stock</div></div>
                    <div class="stat-card"><div class="stat-icon" style="background:rgba(241,196,15,0.1);color:var(--warning)"><i class="fas fa-clock"></i></div><div class="stat-value">${d.pending_orders}</div><div class="stat-label">Pending Orders</div></div>
                </div>
                <div class="chart-container"><h3>Revenue (Last 7 Days)</h3><canvas id="revenue-chart" height="100"></canvas></div>
                <h3 class="mb-2">Top Products</h3>
                <table class="data-table"><thead><tr><th>Product</th><th>Sold</th><th>Revenue</th></tr></thead><tbody>${d.top_products.map(p=>`<tr><td>${esc(p.name)}</td><td>${p.sold}</td><td>₹${p.revenue.toLocaleString()}</td></tr>`).join('')}</tbody></table>`;
            if (d.chart.length && typeof Chart !== 'undefined') {
                new Chart($('#revenue-chart'), { type:'line', data:{labels:d.chart.map(c=>c.date.slice(5)),datasets:[{label:'Revenue',data:d.chart.map(c=>c.revenue),borderColor:'#c9a84c',backgroundColor:'rgba(201,168,76,0.1)',fill:true,tension:0.4,pointBackgroundColor:'#c9a84c',pointRadius:4}]}, options:{responsive:true,plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,grid:{color:'rgba(0,0,0,0.05)'}},x:{grid:{display:false}}}}});
            }
        } else if (tab === 'orders') {
            const orders = await api('/admin/orders');
            content.innerHTML = `<h1 class="mb-3">Orders (${orders.length})</h1>
                <table class="data-table"><thead><tr><th>Order</th><th>Shipping Details</th><th>Total</th><th>Payment</th><th>Status</th><th>Date</th><th>Action</th></tr></thead><tbody>${orders.map(o=>`<tr>
                    <td><strong>${esc(o.order_number)}</strong><br><small>${o.items?o.items.length:0} items</small></td>
                    <td><strong>${esc(o.shipping_name || o.customer_name)}</strong> <small>(${esc(o.shipping_phone || o.mobile_number)})</small><br><small style="color:var(--text-secondary)">${esc(o.line1||'')} ${esc(o.line2||'')}, ${esc(o.city||'')}, ${esc(o.state||'')} - ${esc(o.pincode||'')}</small></td>
                    <td>₹${o.total.toLocaleString()}</td>
                    <td>${o.payment_method==='ONLINE'?'<span style="color:var(--success)"><i class="fas fa-check-circle"></i> Online</span>':'COD'}</td>
                    <td><span class="order-status status-${o.status}">${o.status.replace(/_/g,' ')}</span></td><td>${new Date(o.created_at).toLocaleDateString()}</td>
                    <td><select onchange="updateOrderStatus(${o.id},this.value)" style="padding:4px;border-radius:4px;border:1px solid var(--border)"><option value="">Update</option>${['CONFIRMED','PACKED','SHIPPED','OUT_FOR_DELIVERY','DELIVERED','CANCELLED'].map(s=>`<option value="${s}">${s.replace(/_/g,' ')}</option>`).join('')}</select></td></tr>`).join('')}</tbody></table>`;
        } else if (tab === 'products') {
            const products = await api('/admin/products');
            content.innerHTML = `<div class="flex justify-between items-center mb-3"><h1>Products (${products.length})</h1><button class="btn btn-accent" onclick="showAddProduct()"><i class="fas fa-plus"></i> Add Product</button></div>
                <div id="admin-product-form"></div>
                <table class="data-table"><thead><tr><th>Image</th><th>Name</th><th>Price</th><th>Stock</th><th>Active</th><th>Action</th></tr></thead><tbody>${products.map(p=>`<tr>
                    <td><img src="${esc(p.image_url)}"></td><td><strong>${esc(p.name)}</strong><br><small class="text-muted">${esc(p.sku||'')}</small></td>
                    <td>₹${(p.sale_price||p.base_price).toLocaleString()}</td><td>${p.total_stock}</td><td>${p.is_active?'✅':'❌'}</td>
                    <td><div class="flex gap-1"><button class="btn btn-sm btn-outline" onclick="editProduct(${p.id})"><i class="fas fa-edit"></i></button> <button class="btn btn-sm btn-danger" onclick="deleteProduct(${p.id})"><i class="fas fa-trash"></i></button></div></td></tr>`).join('')}</tbody></table>`;
        } else if (tab === 'customers') {
            const customers = await api('/admin/customers');
            content.innerHTML = `<h1 class="mb-3">Customers (${customers.length})</h1>
                <table class="data-table"><thead><tr><th>Name</th><th>Mobile</th><th>Orders</th><th>Spent</th><th>Status</th><th>Action</th></tr></thead><tbody>${customers.map(c=>`<tr>
                    <td>${esc(c.name)}</td><td>${esc(c.mobile_number)}</td><td>${c.order_count}</td><td>₹${c.total_spent.toLocaleString()}</td>
                    <td>${c.is_active?'<span style="color:var(--success)">Active</span>':'<span style="color:var(--danger)">Blocked</span>'}</td>
                    <td><button class="btn btn-sm ${c.is_active?'btn-danger':'btn-accent'}" onclick="toggleCustomer(${c.id})">${c.is_active?'Block':'Activate'}</button></td></tr>`).join('')}</tbody></table>`;
        } else if (tab === 'reviews') {
            const reviews = await api('/admin/reviews');
            content.innerHTML = `<h1 class="mb-3">Reviews (${reviews.length})</h1>
                ${reviews.map(r=>`<div class="order-card"><div class="flex justify-between"><div><strong>${esc(r.user_name)}</strong> on <em>${esc(r.product_name)}</em><br>${stars(r.rating)}<br><p class="mt-1">${esc(r.body||'')}</p></div>
                <div class="flex gap-1">${!r.is_approved?`<button class="btn btn-sm btn-accent" onclick="approveReview(${r.id})">Approve</button>`:''}<button class="btn btn-sm btn-danger" onclick="deleteReview(${r.id})">Delete</button></div></div></div>`).join('')}`;
        } else if (tab === 'coupons') {
            const coupons = await api('/admin/coupons');
            content.innerHTML = `<h1 class="mb-3">Coupons</h1>
                <table class="data-table"><thead><tr><th>Code</th><th>Type</th><th>Value</th><th>Min Order</th><th>Used</th><th>Limit</th></tr></thead><tbody>${coupons.map(c=>`<tr><td><strong>${esc(c.code)}</strong></td><td>${c.discount_type}</td><td>${c.discount_type==='percentage'?c.discount_value+'%':'₹'+c.discount_value}</td><td>₹${c.min_order}</td><td>${c.used_count}</td><td>${c.usage_limit}</td></tr>`).join('')}</tbody></table>`;
        } else if (tab === 'inventory') {
            const inv = await api('/admin/inventory');
            content.innerHTML = `<h1 class="mb-3">Inventory</h1>
                ${inv.low_stock.length?`<div class="order-card" style="border-color:var(--danger)"><strong style="color:var(--danger)"><i class="fas fa-exclamation-triangle"></i> ${inv.low_stock.length} variants with low stock!</strong></div>`:''}
                <table class="data-table"><thead><tr><th>Product</th><th>Size</th><th>Color</th><th>Stock</th><th>Update</th></tr></thead><tbody>${inv.variants.map(v=>`<tr style="${v.stock<5?'background:rgba(231,76,60,0.05)':''}">
                    <td>${esc(v.product_name)}</td><td>${v.size}</td><td>${v.color}</td><td><strong>${v.stock}</strong></td>
                    <td><input type="number" value="${v.stock}" style="width:60px;padding:4px;border:1px solid var(--border);border-radius:4px" onchange="updateStock(${v.id},this.value)"></td></tr>`).join('')}</tbody></table>`;
        } else if (tab === 'settings') {
            const s = await api('/admin/settings');
            content.innerHTML = `<h1 class="mb-3">Site Customization</h1>
                <form id="site-settings-form" class="auth-form" style="max-width:600px; margin:0;" onsubmit="saveSiteSettings(event)">
                    <div class="form-group"><label>Brand Name</label><input type="text" id="set_brand" value="${esc(s.brand_name||'')}"></div>
                    <div class="flex gap-1">
                        <div class="form-group" style="flex:1"><label>Primary Color</label><input type="color" id="set_primary" value="${esc(s.primary_color||'#121212')}" style="height:40px;width:100%"></div>
                        <div class="form-group" style="flex:1"><label>Accent Color</label><input type="color" id="set_accent" value="${esc(s.accent_color||'#C5A880')}" style="height:40px;width:100%"></div>
                    </div>
                    <div class="form-group"><label>Developer Name</label><input type="text" id="set_dev" value="${esc(s.developer_name||'')}"></div>
                    <div class="form-group"><label>Developer LinkedIn</label><input type="url" id="set_linkedin" value="${esc(s.developer_linkedin||'')}"></div>
                    <div class="form-group"><label>Developer Portfolio</label><input type="url" id="set_portfolio" value="${esc(s.developer_portfolio||'')}"></div>
                    <div class="form-group" style="flex-direction:row; align-items:center; gap:0.5rem">
                        <input type="checkbox" id="set_showdev" ${s.show_developer_credit==='1'?'checked':''} style="width:auto;margin:0;">
                        <label for="set_showdev" style="margin:0;cursor:pointer">Show Developer Credit in Footer</label>
                    </div>
                    <button type="submit" class="btn btn-primary w-100 mt-2">Save Changes</button>
                </form>`;
        } else if (tab === 'returns') {
            const returns = await api('/admin/returns');
            content.innerHTML = `<h1 class="mb-3">Returns (${returns.length})</h1>
                <table class="data-table"><thead><tr><th>Order #</th><th>Customer</th><th>Reason</th><th>Status</th><th>Date</th><th>Action</th></tr></thead><tbody>${returns.map(r=>`<tr>
                    <td><strong>${esc(r.order_number)}</strong></td><td>${esc(r.customer_name)}<br><small>${esc(r.email)}</small></td>
                    <td>${esc(r.reason)}</td><td><span class="order-status status-${r.status==='approved'?'DELIVERED':'PENDING'}">${r.status.toUpperCase()}</span></td><td>${new Date(r.created_at).toLocaleDateString()}</td>
                    <td>${r.status==='pending'?`<button class="btn btn-sm btn-accent" onclick="approveReturn(${r.id})">Approve</button> <button class="btn btn-sm btn-danger" onclick="rejectReturn(${r.id})">Reject</button>`:'-'}</td></tr>`).join('')}</tbody></table>`;
        } else if (tab === 'tickets') {
            const tickets = await api('/admin/tickets');
            content.innerHTML = `<h1 class="mb-3">Support Tickets</h1>
                ${tickets.map(t=>`<div class="order-card"><div class="flex justify-between items-center"><div><strong>${esc(t.subject)}</strong><br><small>${esc(t.customer_name)} — ${new Date(t.created_at).toLocaleDateString()}</small><p class="mt-1">${esc(t.message)}</p>${t.admin_reply?`<div class="mt-1" style="padding:0.5rem;background:var(--bg-alt);border-radius:var(--radius-sm)"><strong>Reply:</strong> ${esc(t.admin_reply)}</div>`:''}</div>
                <span class="order-status status-${t.status==='open'?'PENDING':'DELIVERED'}">${t.status}</span></div>
                ${t.status==='open'?`<div class="mt-2"><input id="reply-${t.id}" placeholder="Type reply..." style="width:70%;padding:0.4rem;border:1px solid var(--border);border-radius:4px"><button class="btn btn-sm btn-accent" onclick="replyTicket(${t.id})">Reply</button></div>`:''}</div>`).join('')}`;
        } else if (tab === 'inventory-logs') {
            const logs = await api('/admin/inventory_logs');
            content.innerHTML = `<h1 class="mb-3">Inventory Logs</h1>
                <table class="data-table"><thead><tr><th>Date</th><th>Product</th><th>Variant</th><th>Change</th><th>Reason</th></tr></thead><tbody>${logs.map(l=>`<tr>
                    <td>${new Date(l.created_at).toLocaleString()}</td>
                    <td>${esc(l.product_name)}</td>
                    <td>${l.size||''} ${l.color||''}</td>
                    <td style="color:${l.change<0?'var(--danger)':'var(--success)'}"><strong>${l.change>0?'+':''}${l.change}</strong></td>
                    <td>${esc(l.reason||'')}</td></tr>`).join('')}</tbody></table>`;
        } else if (tab === 'abandoned') {
            const carts = await api('/admin/abandoned_carts');
            content.innerHTML = `<h1 class="mb-3">Abandoned Carts</h1>
                <table class="data-table"><thead><tr><th>Customer</th><th>Items</th><th>Cart Value</th><th>Action</th></tr></thead><tbody>${carts.map(c=>`<tr>
                    <td><strong>${esc(c.name)}</strong><br><small>${esc(c.email||'No Email')}</small></td>
                    <td>${c.items_count} items</td>
                    <td>₹${c.estimated_value.toLocaleString()}</td>
                    <td><button class="btn btn-sm btn-outline" onclick="notifyAbandoned(${c.user_id})">Send Reminder</button></td></tr>`).join('')}</tbody></table>`;
        }
    } catch(e) { content.innerHTML = `<div class="error"><i class="fas fa-exclamation-triangle"></i> ${e.message}</div>`; }
}

window.saveSiteSettings = async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector('button');
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
    const payload = {
        brand_name: $('#set_brand').value,
        primary_color: $('#set_primary').value,
        accent_color: $('#set_accent').value,
        developer_name: $('#set_dev').value,
        developer_linkedin: $('#set_linkedin').value,
        developer_portfolio: $('#set_portfolio').value,
        show_developer_credit: $('#set_showdev').checked ? '1' : '0'
    };
    try {
        await api('/admin/settings', 'POST', payload);
        toast('Settings saved successfully!', 'success');
        btn.innerHTML = 'Save Changes';
        await loadSiteConfig(); // Instantly apply changes
    } catch(err) { toast(err.message, 'error'); btn.innerHTML = 'Save Changes'; }
};

window.deleteProduct = async (id) => {
    if(!confirm('Are you sure you want to delete this product?')) return;
    try { await api(`/admin/products/${id}`, 'DELETE'); toast('Product deleted', 'success'); renderAdmin('products'); } catch(e) { toast(e.message, 'error'); }
};

window.editProduct = async (id) => {
    toast('Editing products will be supported in the next update!', 'info');
};

window.updateOrderStatus = async(oid,status)=>{if(!status)return;try{await api(`/admin/orders/${oid}/status`,'PUT',{status});toast('Status updated','success');renderAdmin('orders');}catch(e){toast(e.message,'error');}};
window.toggleCustomer = async(uid)=>{try{await api(`/admin/customers/${uid}/toggle`,'PUT');toast('Updated','success');renderAdmin('customers');}catch(e){toast(e.message,'error');}};
window.approveReview = async(rid)=>{try{await api(`/admin/reviews/${rid}/approve`,'PUT');toast('Approved','success');renderAdmin('reviews');}catch(e){toast(e.message,'error');}};
window.deleteReview = async(rid)=>{try{await api(`/admin/reviews/${rid}`,'DELETE');toast('Deleted','info');renderAdmin('reviews');}catch(e){toast(e.message,'error');}};
window.updateStock = async(vid,stock)=>{try{await api(`/admin/variants/${vid}`,'PUT',{stock:parseInt(stock)});toast('Stock updated','success');}catch(e){toast(e.message,'error');}};
window.replyTicket = async(tid)=>{const reply=$(`#reply-${tid}`).value;if(!reply)return;try{await api(`/admin/tickets/${tid}/reply`,'PUT',{reply,status:'resolved'});toast('Reply sent','success');renderAdmin('tickets');}catch(e){toast(e.message,'error');}};
window.showAddProduct = ()=>{
    api('/categories').then(cats=>{
    $('#admin-product-form').innerHTML = `<div class="order-card mb-3"><h3 class="mb-2">Add New Product</h3><form id="add-prod-form">
        <div class="form-row"><div class="form-group"><label>Name</label><input id="np-name" required></div><div class="form-group"><label>Brand</label><input id="np-brand"></div></div>
        <div class="form-row"><div class="form-group"><label>Category</label><select id="np-cat" required>${cats.map(c=>`<option value="${c.id}">${c.name}</option>`).join('')}</select></div><div class="form-group"><label>SKU</label><input id="np-sku"></div></div>
        <div class="form-row"><div class="form-group"><label>Base Price</label><input type="number" id="np-price" required></div><div class="form-group"><label>Sale Price</label><input type="number" id="np-sale"></div></div>
        <div class="form-group"><label>Description</label><textarea id="np-desc" rows="3"></textarea></div>
        <div class="form-group"><label>Image URL</label><input id="np-img" placeholder="https://..."></div>
        <div class="form-row"><div class="form-group"><label>Fabric</label><input id="np-fabric"></div><div class="form-group"><label>Material</label><input id="np-material"></div></div>
        <button type="submit" class="btn btn-accent">Create Product</button></form></div>`;
    $('#add-prod-form').addEventListener('submit',async(e)=>{e.preventDefault();try{await api('/admin/products','POST',{name:$('#np-name').value,brand:$('#np-brand').value,category_id:parseInt($('#np-cat').value),sku:$('#np-sku').value,base_price:parseFloat($('#np-price').value),sale_price:parseFloat($('#np-sale').value)||null,description:$('#np-desc').value,image_url:$('#np-img').value,fabric:$('#np-fabric').value,material:$('#np-material').value});toast('Product created!','success');renderAdmin('products');}catch(e){toast(e.message,'error');}});
    });
};

window.approveReturn = async(rid)=>{try{await api(`/admin/returns/${rid}`,'PUT',{status:'approved'});toast('Return approved','success');renderAdmin('returns');}catch(e){toast(e.message,'error');}};
window.rejectReturn = async(rid)=>{try{await api(`/admin/returns/${rid}`,'PUT',{status:'rejected'});toast('Return rejected','success');renderAdmin('returns');}catch(e){toast(e.message,'error');}};
window.notifyAbandoned = async(uid)=>{try{await api(`/admin/abandoned_carts/notify/${uid}`,'POST');toast('Reminder sent','success');}catch(e){toast(e.message,'error');}};

// ─── Smart Search ───
const searchInput = $('#smart-search');
const searchSug = $('#search-suggestions');
let searchTimeout;
if (searchInput) {
    searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        const q = e.target.value.trim();
        if(q.length < 2) { searchSug.style.display = 'none'; return; }
        searchTimeout = setTimeout(async () => {
            try {
                const res = await api(`/products?q=${encodeURIComponent(q)}&per_page=5`);
                if(res.products.length) {
                    searchSug.innerHTML = res.products.map(p=>`<div class="search-item" onclick="navigate('product/${p.slug}');$('#search-suggestions').style.display='none';$('#smart-search').value=''">
                        <img src="${esc(p.image_url)}"><div class="search-item-info"><h4>${esc(p.name)}</h4><p>₹${(p.sale_price||p.base_price).toLocaleString()}</p></div></div>`).join('');
                    searchSug.style.display = 'block';
                } else { searchSug.style.display = 'none'; }
            } catch(e){}
        }, 300);
    });
    document.addEventListener('click', (e) => { if(!e.target.closest('.smart-search-wrapper')) searchSug.style.display = 'none'; });
}

// ─── Modals ───
window.openMediaModal = (url, isVideo) => {
    $('#media-container').innerHTML = isVideo ? `<video controls autoplay src="${url}" style="width:100%"></video>` : `<img src="${url}">`;
    $('#media-modal').style.display = 'flex';
};
window.closeMediaModal = () => { $('#media-modal').style.display = 'none'; $('#media-container').innerHTML = ''; };
window.openReturnModal = (oid) => { $('#return-order-id').value = oid; $('#return-modal').style.display = 'flex'; };
window.closeReturnModal = () => { $('#return-modal').style.display = 'none'; $('#return-form').reset(); };

if($('#return-form')) {
    $('#return-form').addEventListener('submit', async(e) => {
        e.preventDefault();
        try {
            await api(`/orders/${$('#return-order-id').value}/return`, 'POST', { reason: $('#return-reason').value });
            toast('Return requested successfully', 'success');
            closeReturnModal();
            renderDashboard();
        } catch(e) { toast(e.message, 'error'); }
    });
}

// ─── Init ──────────────────────────────────────────────────────────────────
initTheme();
// ─── Static Pages ──────────────────────────────────────────────────────────
function renderAbout() {
    app.innerHTML = `<div class="container section">
        <div class="section-title reveal"><h2>About Us</h2><div class="line"></div></div>
        <div style="max-width:800px; margin:0 auto; text-align:center;">
            <p>Welcome to LUXE, the epitome of modern luxury fashion. We are dedicated to providing curated collections for the discerning individual.</p>
            <p class="mt-2">Our mission is to bring high-quality, exclusive designs right to your doorstep with an emphasis on craftsmanship and timeless elegance.</p>
        </div>
    </div>`;
}

function renderPrivacy() {
    app.innerHTML = `<div class="container section">
        <div class="section-title reveal"><h2>Privacy Policy</h2><div class="line"></div></div>
        <div style="max-width:800px; margin:0 auto;">
            <p>At LUXE, we respect your privacy. This policy outlines how we collect, use, and protect your personal information.</p>
            <h3 class="mt-2">Information Collection</h3>
            <p>We collect information you provide when creating an account, making a purchase, or contacting support.</p>
            <h3 class="mt-2">Data Protection</h3>
            <p>We implement industry-standard security measures to ensure your data is safe and secure.</p>
        </div>
    </div>`;
}

function renderRefund() {
    app.innerHTML = `<div class="container section">
        <div class="section-title reveal"><h2>Refund & Return Policy</h2><div class="line"></div></div>
        <div style="max-width:800px; margin:0 auto;">
            <p>We offer a hassle-free 7-day return policy for all unworn and unwashed items with tags attached.</p>
            <h3 class="mt-2">How to Return</h3>
            <p>Navigate to your orders page and click the "Return" button on eligible items. A pickup will be scheduled within 24-48 hours.</p>
            <h3 class="mt-2">Refunds</h3>
            <p>Refunds are processed to your original payment method or LUXE Wallet within 5-7 business days after the item is received and inspected.</p>
        </div>
    </div>`;
}

function renderFaq() {
    app.innerHTML = `<div class="container section">
        <div class="section-title reveal"><h2>Frequently Asked Questions</h2><div class="line"></div></div>
        <div style="max-width:800px; margin:0 auto;">
            <div class="faq-item mb-2">
                <h3>What are your shipping charges?</h3>
                <p class="text-muted">We offer free shipping on all orders over ₹999. For orders below this amount, a standard fee of ₹99 applies.</p>
            </div>
            <div class="faq-item mb-2">
                <h3>Do you ship internationally?</h3>
                <p class="text-muted">Currently, we only ship within India. We plan to expand globally soon!</p>
            </div>
            <div class="faq-item mb-2">
                <h3>How can I track my order?</h3>
                <p class="text-muted">You can track your order in real-time from the 'My Orders' section in your account dashboard.</p>
            </div>
        </div>
    </div>`;
}

router();
