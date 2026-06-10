# LUXE E-Commerce Platform

A premium, monolithic Flask/SQLite single-page application built for luxury fashion retail.

## Features
- **Dynamic CMS:** Theme builder, configurable footer branding, categories, and banners.
- **Smart Search & Filters:** Product discovery with intelligent query mapping.
- **Secure Payments:** Razorpay integration with backend HMAC signature validation.
- **Unified UI:** No page reloads. Hash-based routing built with Vanilla JavaScript and CSS variables.
- **Authentication:** JWT-based stateless auth with Password login and Mock OTP fallback.

## Setup Instructions

### 1. Prerequisites
- Python 3.10+
- SQLite3

### 2. Installation
```bash
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configuration
Create a `.env` file in the root directory:
```env
SECRET_KEY=your_secure_random_key
ADMIN_PASSWORD=your_secure_admin_password
MSG91_AUTH_KEY=your_msg91_auth_key
RAZORPAY_KEY_ID=your_razorpay_key_id
RAZORPAY_KEY_SECRET=your_razorpay_secret
```

### 4. Run the Application
```bash
python app.py
```
The database will automatically initialize and seed the admin user on the first run.

## Admin Access
- **Email:** ashishadmin
- **Password:** (Check your `ADMIN_PASSWORD` in `.env`, defaults to `admin123`)
- **Dashboard URL:** `http://localhost:5000/#admin`
