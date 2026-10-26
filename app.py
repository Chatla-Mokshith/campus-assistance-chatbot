"""
=============================================================================
HORIZON INSTITUTE - CAMPUS ASSISTANCE BACKEND (FLASK + MYSQL + AI/NLP)
=============================================================================
Phase 5 Backend (Admin Dashboard added):
1. Static web server to serve index.html, style.css, and script.js
2. GET  /api/status     - Health check verifying Flask, MySQL, and AI Engine status
3. POST /api/chat       - Grounded conversational assistant powered by MySQL + Gemini RAG
4. POST /api/feedback   - Logs student thumbs-up/down feedback
5. GET  /admin/login    - Admin login page
6. POST /admin/login    - Authenticate admin credentials
7. GET  /admin/logout   - Destroys admin session
8. GET  /admin/dashboard - Secured analytics overview page
9. GET  /admin/faqs     - FAQ management list (search, filter)
10. POST /admin/faqs/add - Add new FAQ
11. GET  /admin/faqs/<id>/edit - Edit FAQ form
12. POST /admin/faqs/<id>/edit - Save edited FAQ
13. POST /admin/faqs/<id>/delete - Delete FAQ
14. POST /admin/change-password  - Admin password update

Security:
- Database credentials and API keys stored exclusively in .env
- Session protection with SECRET_KEY
- CSRF protection via Flask-WTF on all state-changing admin forms
- Parameterized SQL queries in database.py throughout
- Werkzeug password hashing for admin credentials
- Admin routes guard-checked by login_required decorator
"""

from datetime import datetime
import os
import functools
from flask import (Flask, request, jsonify, send_from_directory,
                   session, redirect, url_for, render_template,
                   flash, abort)
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect, generate_csrf, CSRFError
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

from database import (
    init_database, get_db_connection,
    verify_admin_credentials,
    get_dashboard_metrics,
    get_all_faqs, get_faq_by_id, get_categories_list,
    add_faq, update_faq, delete_faq,
    log_chat_interaction, log_feedback
)
from ai_service import generate_campus_ai_response, get_ai_service_status

# ---------------------------------------------------------------------------
# Load .env and initialize Flask
# ---------------------------------------------------------------------------
load_dotenv()

app = Flask(__name__, static_folder='.', template_folder='admin')
app.secret_key = os.getenv("SECRET_KEY", "change-me-in-production!")
app.config["WTF_CSRF_TIME_LIMIT"] = 3600  # 1-hour CSRF token lifetime

CORS(app)
csrf = CSRFProtect(app)

# ---------------------------------------------------------------------------
# Auto-initialize database on application startup (essential for Gunicorn / Render)
# ---------------------------------------------------------------------------
try:
    init_success, init_msg = init_database()
    if init_success:
        print(f"[OK] Database initialized successfully (Total FAQs: {init_msg})")
    else:
        print(f"[WARN] Database initialization notice: {init_msg}")
except Exception as init_err:
    print(f"[WARN] Startup database initialization deferred: {init_err}")


@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    """Gracefully handles expired or invalid CSRF tokens without throwing a 400 crash page."""
    flash("⚠️ Security token expired. Please try submitting again.", "error")
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("admin_login_page"))


# =============================================================================
# HELPER: login_required decorator for all admin routes
# =============================================================================
def login_required(view_func):
    """Redirects to admin login page if the user is not authenticated."""
    @functools.wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        return view_func(*args, **kwargs)
    return wrapped


# =============================================================================
# 1. FRONTEND SERVING ROUTES
# =============================================================================
@app.route('/')
def serve_index():
    """Serves the main college homepage (index.html)."""
    return send_from_directory('.', 'index.html')


@app.route('/<path:filename>')
def serve_static(filename):
    """Serves static files (style.css, script.js, images, etc.)."""
    # Block direct browser access to sensitive files
    blocked = {'.env', '.env.example', '.gitignore', 'database.py',
               'ai_service.py', 'app.py'}
    if filename in blocked:
        abort(403)
    if os.path.exists(filename):
        return send_from_directory('.', filename)
    return jsonify({"error": "File not found"}), 404


# =============================================================================
# 2. PUBLIC CHATBOT API ENDPOINTS
# =============================================================================
@app.route('/api/status', methods=['GET'])
def get_status():
    """Health check endpoint — tests Flask, MySQL, and AI service."""
    db_status = "offline"
    try:
        conn = get_db_connection(use_database=True)
        if conn.is_connected():
            db_status = f"connected ({conn.database})"
            conn.close()
    except Exception as err:
        db_status = f"disconnected ({str(err)})"

    return jsonify({
        "status": "online",
        "service": "Horizon CampusBot API",
        "database": f"MySQL - {db_status}",
        "ai_engine": get_ai_service_status(),
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat()
    }), 200


@app.route('/api/chat', methods=['POST'])
@csrf.exempt
def chat_endpoint():
    """
    Chatbot endpoint.
    Receives JSON: { "message": "user question" }
    Returns JSON:  { "success": True, "reply": "...", "suggestions": [...], ... }
    """
    data = request.get_json(silent=True) or {}
    raw_message = data.get("message", "").strip()

    if not raw_message:
        return jsonify({
            "success": False,
            "reply": "Please enter a question so I can assist you.",
            "suggestions": [
                "How can I apply for admission?",
                "Where can I find placement information?"
            ]
        }), 400

    try:
        result = generate_campus_ai_response(raw_message)

        # Log the chat interaction for admin analytics
        log_chat_interaction(
            raw_message,
            result.get("matched_category", "Uncategorized"),
            result.get("source", "unknown")
        )

        return jsonify({
            "success": result.get("success", True),
            "reply": result.get("reply"),
            "suggestions": result.get("suggestions", []),
            "source": result.get("source", "grounded_ai"),
            "timestamp": datetime.now().strftime("%I:%M %p")
        }), 200

    except Exception as err:
        print(f"[ERROR] Exception in /api/chat: {err}")
        return jsonify({
            "success": False,
            "reply": "Sorry, an unexpected error occurred while processing your request.",
            "suggestions": ["How can I contact the campus helpdesk?"]
        }), 500


@app.route('/api/feedback', methods=['POST'])
@csrf.exempt
def feedback_endpoint():
    """Logs student thumbs-up/down ratings. No CSRF needed for this JSON API."""
    data = request.get_json(silent=True) or {}
    rating = data.get("rating", "").strip().lower()
    comment = data.get("comment", "").strip()

    if rating not in ("helpful", "unhelpful"):
        return jsonify({"success": False, "message": "Invalid rating value."}), 400

    logged = log_feedback(rating, comment)
    return jsonify({"success": logged}), 200


# =============================================================================
# 3. ADMIN AUTHENTICATION ROUTES
# =============================================================================
@app.route('/admin/login', methods=['GET'])
def admin_login_page():
    """Renders the admin login page."""
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))
    csrf_token = generate_csrf()
    return render_template('admin_login.html', csrf_token=csrf_token, error=None)


@app.route('/admin/login', methods=['POST'])
def admin_login_submit():
    """Verifies admin credentials and creates a session."""
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    if not username or not password:
        csrf_token = generate_csrf()
        return render_template('admin_login.html',
            csrf_token=csrf_token,
            error="Username and password are required."
        ), 400

    authenticated, user = verify_admin_credentials(username, password)
    if authenticated:
        session.clear()
        session["admin_logged_in"] = True
        session["admin_username"] = user["username"]
        session["admin_id"] = user["id"]
        session.permanent = False
        if user.get("db_offline"):
            flash("⚠️ Notice: MySQL database is currently unreachable on Render. You are logged in with emergency admin credentials. Configure your DB_HOST environment variables in Render to enable live persistence.", "error")
        return redirect(url_for("admin_dashboard"))

    csrf_token = generate_csrf()
    return render_template('admin_login.html',
        csrf_token=csrf_token,
        error="Invalid username or password. (Check your credentials or verify Cloud MySQL is connected)."
    ), 401


@app.route('/admin/logout')
@login_required
def admin_logout():
    """Destroys admin session and redirects to login."""
    session.clear()
    return redirect(url_for("admin_login_page"))


# =============================================================================
# 4. ADMIN DASHBOARD
# =============================================================================
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Renders the admin overview dashboard with live analytics."""
    metrics = get_dashboard_metrics()
    categories = get_categories_list()
    csrf_token = generate_csrf()
    return render_template('admin_dashboard.html',
        metrics=metrics,
        categories=categories,
        csrf_token=csrf_token,
        admin_username=session.get("admin_username", "Admin"),
        active_tab="dashboard"
    )


# =============================================================================
# 5. ADMIN FAQ MANAGEMENT
# =============================================================================
@app.route('/admin/faqs')
@login_required
def admin_faqs():
    """Renders the FAQ management page with optional search/filter."""
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    faqs = get_all_faqs(search_query=search, category_filter=category)
    categories = get_categories_list()
    csrf_token = generate_csrf()
    return render_template('admin_dashboard.html',
        faqs=faqs,
        categories=categories,
        csrf_token=csrf_token,
        admin_username=session.get("admin_username", "Admin"),
        active_tab="faqs",
        search=search,
        selected_category=category,
        metrics=None
    )


@app.route('/admin/faqs/add', methods=['POST'])
@login_required
def admin_add_faq():
    """Adds a new FAQ to MySQL."""
    category = request.form.get("category", "").strip()
    custom_cat = request.form.get("custom_category", "").strip()
    question = request.form.get("question", "").strip()
    answer = request.form.get("answer", "").strip()
    keywords = request.form.get("keywords", "").strip()

    # Allow admin to type a brand-new category name or select existing
    if category == "__new__":
        final_category = custom_cat
    else:
        final_category = custom_cat if custom_cat else category

    if not final_category:
        flash("❌ Category is required. Please select an existing category or enter a new one.", "error")
        return redirect(url_for("admin_faqs"))

    success, message = add_faq(final_category, question, answer, keywords)
    if success:
        flash(f"✅ {message}", "success")
    else:
        flash(f"❌ {message}", "error")
    return redirect(url_for("admin_faqs"))


@app.route('/admin/faqs/<int:faq_id>/edit', methods=['GET'])
@login_required
def admin_edit_faq_form(faq_id):
    """Renders the edit form for a specific FAQ."""
    faq = get_faq_by_id(faq_id)
    if not faq:
        flash("❌ FAQ not found.", "error")
        return redirect(url_for("admin_faqs"))
    categories = get_categories_list()
    csrf_token = generate_csrf()
    return render_template('admin_dashboard.html',
        faq=faq,
        categories=categories,
        csrf_token=csrf_token,
        admin_username=session.get("admin_username", "Admin"),
        active_tab="edit_faq",
        metrics=None
    )


@app.route('/admin/faqs/<int:faq_id>/edit', methods=['POST'])
@login_required
def admin_edit_faq_submit(faq_id):
    """Saves changes to an existing FAQ."""
    category = request.form.get("category", "").strip()
    custom_cat = request.form.get("custom_category", "").strip()
    question = request.form.get("question", "").strip()
    answer = request.form.get("answer", "").strip()
    keywords = request.form.get("keywords", "").strip()

    if category == "__new__":
        final_category = custom_cat
    else:
        final_category = custom_cat if custom_cat else category

    if not final_category:
        flash("❌ Category is required. Please select an existing category or enter a new one.", "error")
        return redirect(url_for("admin_edit_faq_form", faq_id=faq_id))

    success, message = update_faq(faq_id, final_category, question, answer, keywords)
    if success:
        flash(f"✅ {message}", "success")
    else:
        flash(f"❌ {message}", "error")
    return redirect(url_for("admin_faqs"))


@app.route('/admin/faqs/<int:faq_id>/delete', methods=['POST'])
@login_required
def admin_delete_faq(faq_id):
    """Deletes an FAQ from MySQL."""
    success, message = delete_faq(faq_id)
    if success:
        flash(f"✅ {message}", "success")
    else:
        flash(f"❌ {message}", "error")
    return redirect(url_for("admin_faqs"))


# =============================================================================
# 6. ADMIN CHANGE PASSWORD
# =============================================================================
@app.route('/admin/change-password', methods=['POST'])
@login_required
def admin_change_password():
    """Allows the current admin to update their own password."""
    import mysql.connector
    current = request.form.get("current_password", "").strip()
    new_pw = request.form.get("new_password", "").strip()
    confirm_pw = request.form.get("confirm_password", "").strip()

    username = session.get("admin_username")
    authenticated, _ = verify_admin_credentials(username, current)

    if not authenticated:
        flash("❌ Current password is incorrect.", "error")
        return redirect(url_for("admin_dashboard") + "#change-pw")

    if len(new_pw) < 8:
        flash("❌ New password must be at least 8 characters.", "error")
        return redirect(url_for("admin_dashboard") + "#change-pw")

    if new_pw != confirm_pw:
        flash("❌ New passwords do not match.", "error")
        return redirect(url_for("admin_dashboard") + "#change-pw")

    try:
        conn = get_db_connection(use_database=True)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE admin_users SET password_hash = %s WHERE username = %s;",
            (generate_password_hash(new_pw), username)
        )
        cursor.close()
        conn.close()
        flash("✅ Password updated successfully.", "success")
    except Exception as e:
        flash(f"❌ Database error: {e}", "error")
        return redirect(url_for("admin_dashboard") + "#change-pw")

    return redirect(url_for("admin_dashboard"))


# =============================================================================
# 7. APPLICATION ENTRY POINT
# =============================================================================
if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    host = os.getenv("HOST", "0.0.0.0")
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() in ("true", "1")

    print("---------------------------------------------------------------")
    print("HORIZON CAMPUS ASSISTANCE BACKEND v2.0 (Flask + MySQL + AI + Admin)")
    print("---------------------------------------------------------------")
    print(f"[OK] AI Engine: {get_ai_service_status()}")
    print(f"Student Portal : http://localhost:{port}")
    print(f"Admin Dashboard: http://localhost:{port}/admin/login")
    print("Press Ctrl+C to stop.")
    print("---------------------------------------------------------------")

    app.run(host=host, port=port, debug=debug_mode)

