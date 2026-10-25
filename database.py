"""
=============================================================================
HORIZON INSTITUTE - MYSQL DATABASE LAYER (Phase 5: Admin Dashboard)
=============================================================================
Handles MySQL connection, database initialization, table creation,
parameterized query matching for the chatbot, and full administrative
CRUD & analytics operations.
"""

import os
import json
import math
import re
from difflib import SequenceMatcher
from urllib.parse import urlparse, unquote
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# Load environment variables from .env
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "campus_assistance")

ADMIN_DEFAULT_USERNAME = os.getenv("ADMIN_DEFAULT_USERNAME", "admin")
ADMIN_DEFAULT_PASSWORD = os.getenv("ADMIN_DEFAULT_PASSWORD", "Admin@Horizon2026!")

# In-memory cache for fast vector similarity searches across active FAQs
# Structure: {faq_id: {"embedding": [float], "category": str, "question": str, "answer": str, "keywords": str}}
_FAQ_EMBEDDINGS_CACHE = {}


def get_gemini_api_key():
    """Dynamically reads the latest GEMINI_API_KEY from .env."""
    load_dotenv(override=True)
    return os.getenv("GEMINI_API_KEY", "").strip()


def compute_text_embedding(text):
    """
    Computes a 3072-dimensional vector embedding for text using Google Gemini models/gemini-embedding-001.
    Returns: list of floats, or None if unavailable/error.
    """
    if not text or not GENAI_AVAILABLE:
        return None
    api_key = get_gemini_api_key()
    if not api_key or api_key.startswith("your_") or len(api_key) < 10:
        return None
    try:
        client = genai.Client(api_key=api_key, http_options={"timeout": 15000})
        res = client.models.embed_content(
            model="models/gemini-embedding-001",
            contents=text[:1500]
        )
        if res and res.embeddings and len(res.embeddings) > 0:
            return res.embeddings[0].values
    except Exception as e:
        print(f"[WARN] Embedding generation failed for '{text[:40]}...': {e}")
    return None


def cosine_similarity(vec_a, vec_b):
    """
    Computes standard cosine similarity between two numeric vectors.
    Returns float in range [-1.0, 1.0].
    """
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)



def get_db_config(use_database=True):
    """
    Resolves MySQL connection parameters from environment variables.
    Supports individual DB_* variables as well as full DATABASE_URL / MYSQL_URL strings.
    Supports TLS / SSL for cloud MySQL providers (TiDB Serverless, Aiven, Railway, etc.).
    """
    database_url = os.getenv("DATABASE_URL") or os.getenv("MYSQL_URL")
    if database_url:
        parsed = urlparse(database_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 3306
        user = unquote(parsed.username) if parsed.username else "root"
        password = unquote(parsed.password) if parsed.password else ""
        db_name = parsed.path.lstrip('/') or DB_NAME
    else:
        host = os.getenv("DB_HOST", "localhost")
        port = int(os.getenv("DB_PORT", "3306"))
        user = os.getenv("DB_USER", "root")
        password = os.getenv("DB_PASSWORD", "")
        db_name = os.getenv("DB_NAME", "campus_assistance")

    config = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "autocommit": True,
        "charset": "utf8mb4"
    }
    if use_database:
        config["database"] = db_name

    # SSL / TLS configuration for cloud-hosted databases
    ssl_env = os.getenv("DB_SSL", "").strip().lower()
    auto_ssl = any(d in host.lower() for d in ["tidbcloud.com", "aivencloud.com", "clever-cloud.com"])
    if ssl_env in ("true", "1", "yes") or auto_ssl:
        config["ssl_disabled"] = False
        ssl_ca = os.getenv("DB_SSL_CA", "").strip()
        if ssl_ca and os.path.exists(ssl_ca):
            config["ssl_ca"] = ssl_ca
            config["ssl_verify_cert"] = True
        else:
            config["ssl_verify_cert"] = False

    return config, db_name


def get_db_connection(use_database=True):
    """
    Creates and returns a connection to MySQL Server.
    If use_database is False, connects without selecting a specific database.
    """
    config, _ = get_db_config(use_database=use_database)
    return mysql.connector.connect(**config)


# Sample FAQs data covering all required campus domains
SAMPLE_FAQS = [
    # 1. Admissions
    (
        "Admissions",
        "How can I apply for admission?",
        "🎓 **Admissions Overview:**\nAdmissions for Academic Year 2026-27 are currently open for B.Tech, M.Tech, MBA, and MCA programs.\n\n**Application Steps:**\n1. Register online at admissions.horizon.edu\n2. Fill academic details and upload grade transcripts\n3. Submit national entrance scores (or appear for Horizon Entrance Test)\n4. Attend online counseling and confirm seat reservation.",
        "admission, apply, application, enroll, entrance, register, process"
    ),
    (
        "Admissions",
        "What are the admission deadlines?",
        "📅 **Admission Deadlines (2026-27):**\n• Early Round Deadline: June 15, 2026\n• Regular Applications Close: July 30, 2026\n• Orientation & Document Verification: Late August 2026",
        "deadline, last date, cut off, admission dates, schedule, college start, reopening date, reopening, classes begin, semester start"
    ),
    (
        "Admissions",
        "What are the eligibility criteria for undergraduate programs?",
        "📋 **Eligibility Criteria:**\nApplicants for B.Tech programs must possess a minimum of 60% aggregate in Physics, Chemistry, and Mathematics (10+2). International applicants require an equivalent secondary diploma verified by the Academic Board.",
        "eligibility, criteria, qualification, percentage, marks, requirements"
    ),

    # 2. Academic Programs
    (
        "Academics",
        "What academic programs are offered?",
        "📚 **Featured Academic Programs:**\n• B.Tech in Computer Science & Artificial Intelligence\n• B.Tech in Electronics & IoT Systems\n• B.Tech in Data Science & Big Data Analytics\n• B.Tech in Mechanical & Mechatronics Engineering\n• M.Tech in Autonomous Systems & Robotics\n• Master of Business Administration (MBA - Tech Management)",
        "programs, courses, branch, degrees, academics, b.tech, m.tech, mba, curriculum"
    ),
    (
        "Academics",
        "What is the curriculum and credit structure?",
        "📖 **Curriculum Structure:**\nOur 8-semester curriculum emphasizes experiential learning with hands-on lab modules, industrial internships in the 6th semester, and an industry-sponsored capstone project in the final year.",
        "curriculum, credits, syllabus, semester, subjects, study"
    ),

    # 3. Examinations
    (
        "Examinations",
        "When are the semester examinations conducted?",
        "📝 **Examination Schedule:**\n• Odd Semester Mid-Terms: October | End-Sem Finals: December\n• Even Semester Mid-Terms: March | End-Sem Finals: May\n• Detailed timetable is published on the Student Exam Portal 3 weeks prior.",
        "exam, exams, examination, examinations, midterm, midterms, mid term, end term, final, finals, timetable, results, test"
    ),
    (
        "Examinations",
        "What is the grading system and CGPA evaluation?",
        "📊 **Grading System:**\nHorizon Institute follows a 10-point CGPA grading scale (O: 10, A+: 9, A: 8, B+: 7, B: 6, C: 5). A minimum CGPA of 5.0 is required for graduation.",
        "grading, cgpa, gpa, marks, evaluation, pass, grade"
    ),

    # 4. Placements & Careers
    (
        "Placements",
        "Where can I find placement information?",
        "💼 **Placements & Career Center:**\n• **Placement Rate:** 92% overall placement record for 2025-26\n• **Salary Packages:** Highest: $38,000 / year (Demo) | Average: $14,500 / year (Demo)\n• **Recruiters:** Over 180+ partner organizations including TechNova Labs, Apex Cloud Systems, and DataPulse Analytics.\n• **Contact:** careers@horizon.edu | Room 302, Student Activity Building",
        "placement, career, jobs, package, recruiter, salary, internship, companies"
    ),

    # 5. Scholarships & Financial Aid
    (
        "Scholarships",
        "What scholarships and financial aid are available?",
        "💰 **Scholarships & Financial Aid:**\n• **Merit Scholarships:** Up to 50% tuition waiver for top 5% entrance rank holders\n• **Sports Excellence:** 30% waiver for state/national medalists\n• **STEM Diversity:** Need-based grants for underrepresented candidates\nContact finaid@horizon.edu for scholarship forms.",
        "scholarship, fee, tuition, financial aid, concession, waiver, cost"
    ),

    # 6. Hostels & Accommodation
    (
        "Hostels",
        "What are the hostel and accommodation facilities?",
        "🏠 **Residential Hostels:**\nSeparate air-conditioned and non-AC residential towers for men and women. Includes high-speed Wi-Fi, 24/7 security, gym, indoor sports, and hygienic multi-cuisine dining halls. Hostel allotment begins alongside admission confirmation.",
        "hostel, accommodation, room, dorm, residence, stay, food, mess"
    ),

    # 7. Library Facilities
    (
        "Library",
        "What are the library timings and facilities?",
        "📖 **Central Digital Library:**\nHouses over 80,000 physical volumes, 250,000 e-journals, IEEE/ACM digital access, and 24 quiet research pods.\n• **Hours:** Mon - Sat: 8:00 AM - 10:00 PM | Sun: 10:00 AM - 6:00 PM\n• Remote e-library access available via student credentials.",
        "library, books, journals, timings, reading room, study, digital library"
    ),

    # 8. Campus Events & Hackathons
    (
        "Events",
        "What are the upcoming campus events and hackathons?",
        "📅 **Upcoming Campus Events:**\n• **Nov 18, 2026:** Annual 36-Hour Hackathon on Community AI Solutions\n• **Dec 05, 2026:** International Tech Symposium & Future of AI Forum\n• **Jan 14, 2027:** Annual Spring Campus Placement Fair\nRSVP online through the student portal.",
        "events, hackathon, fest, symposium, activities, conference, workshop"
    ),

    # 9. Campus Contacts & Helpdesk
    (
        "Contact",
        "How can I contact the campus helpdesk?",
        "📞 **Campus Contact & Helpdesk:**\n• **Address:** 100 Knowledge Boulevard, Innovation District, Tech City 560001\n• **General Inquiries:** admissions@horizon.edu / helpdesk@horizon.edu\n• **Helpline:** +1 (800) 555-0199 (Mon-Fri, 9:00 AM - 5:00 PM)",
        "contact, phone, email, address, helpdesk, office, location, helpline"
    )
]


def init_database():
    """
    Initializes MySQL database and all required tables:
    1. campus_faqs (Knowledge base)
    2. admin_users (Administrative credentials with password hashing)
    3. chat_logs (Real-time student interaction logs)
    4. feedback_logs (Student satisfaction ratings)
    """
    try:
        _, db_name = get_db_config(use_database=True)

        # Step 1: Connect to MySQL server and ensure database exists (if permitted)
        try:
            server_conn = get_db_connection(use_database=False)
            server_cursor = server_conn.cursor()
            server_cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
            server_cursor.close()
            server_conn.close()
        except Exception as create_db_err:
            # Managed cloud MySQL (TiDB, Aiven, etc.) pre-provisions the database
            # and may restrict server-level CREATE DATABASE permissions.
            pass

        # Step 2: Connect to campus_assistance database and create tables
        db_conn = get_db_connection(use_database=True)
        cursor = db_conn.cursor()

        # 1. campus_faqs Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS `campus_faqs` (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            `category` VARCHAR(100) NOT NULL,
            `question` VARCHAR(255) NOT NULL,
            `answer` TEXT NOT NULL,
            `keywords` VARCHAR(255) NOT NULL,
            UNIQUE KEY `uq_question` (`question`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # 2. admin_users Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS `admin_users` (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            `username` VARCHAR(50) NOT NULL UNIQUE,
            `password_hash` VARCHAR(255) NOT NULL,
            `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # 3. chat_logs Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS `chat_logs` (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            `user_query` VARCHAR(500) NOT NULL,
            `matched_category` VARCHAR(100),
            `response_source` VARCHAR(50),
            `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # 4. feedback_logs Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS `feedback_logs` (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            `rating` VARCHAR(20) NOT NULL,
            `comment` VARCHAR(500),
            `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # 5. faq_embeddings Table (Semantic Vector Storage with CASCADE delete)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS `faq_embeddings` (
            `faq_id` INT PRIMARY KEY,
            `embedding_json` MEDIUMTEXT NOT NULL,
            `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            CONSTRAINT `fk_faq_embeddings` FOREIGN KEY (`faq_id`) REFERENCES `campus_faqs`(`id`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Step 3: Insert sample FAQs with ON DUPLICATE KEY UPDATE (idempotent / no duplicates)
        insert_faq_sql = """
        INSERT INTO `campus_faqs` (`category`, `question`, `answer`, `keywords`)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            `category` = VALUES(`category`),
            `answer` = VALUES(`answer`),
            `keywords` = VALUES(`keywords`);
        """
        cursor.executemany(insert_faq_sql, SAMPLE_FAQS)

        # Step 4: Seed Default Admin User if not already present
        cursor.execute("SELECT id FROM `admin_users` WHERE `username` = %s;", (ADMIN_DEFAULT_USERNAME,))
        existing_admin = cursor.fetchone()
        if not existing_admin:
            hashed_pw = generate_password_hash(ADMIN_DEFAULT_PASSWORD)
            cursor.execute(
                "INSERT INTO `admin_users` (`username`, `password_hash`) VALUES (%s, %s);",
                (ADMIN_DEFAULT_USERNAME, hashed_pw)
            )
            print(f"[OK] Seeded default admin user: '{ADMIN_DEFAULT_USERNAME}'")

        # Verify row count
        cursor.execute("SELECT COUNT(*) FROM `campus_faqs`;")
        row_count = cursor.fetchone()[0]

        cursor.close()
        db_conn.close()

        print(f"[OK] MySQL database '{DB_NAME}' initialized successfully.")
        print(f"[OK] Total FAQs in 'campus_faqs': {row_count}")

        # Synchronize semantic embeddings into MySQL & memory
        sync_all_faq_embeddings()

        return True, row_count

    except Error as e:
        print(f"[ERROR] MySQL Initialization Error: {e}")
        return False, str(e)


# =============================================================================
# SEMANTIC VECTOR EMBEDDING SYNCHRONIZATION
# =============================================================================
def sync_all_faq_embeddings():
    """
    Synchronizes the MySQL faq_embeddings table with campus_faqs and populates _FAQ_EMBEDDINGS_CACHE.
    Automatically generates embeddings for any newly found FAQs missing a vector.
    """
    global _FAQ_EMBEDDINGS_CACHE
    try:
        conn = get_db_connection(use_database=True)
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT f.id, f.category, f.question, f.answer, f.keywords, e.embedding_json
            FROM campus_faqs f
            LEFT JOIN faq_embeddings e ON f.id = e.faq_id;
        """)
        rows = cursor.fetchall()

        loaded = 0
        generated = 0
        new_cache = {}

        for r in rows:
            faq_id = r["id"]
            cat = r["category"]
            q = r["question"]
            ans = r["answer"]
            kw = r["keywords"]

            emb = None
            if r["embedding_json"]:
                try:
                    emb = json.loads(r["embedding_json"])
                    loaded += 1
                except Exception:
                    emb = None

            if not emb:
                text_to_embed = f"Category: {cat}\nQuestion: {q}\nAnswer: {ans}\nKeywords: {kw}"
                emb = compute_text_embedding(text_to_embed)
                if emb:
                    cursor.execute(
                        "REPLACE INTO faq_embeddings (faq_id, embedding_json) VALUES (%s, %s);",
                        (faq_id, json.dumps(emb))
                    )
                    generated += 1

            new_cache[faq_id] = {
                "id": faq_id,
                "category": cat,
                "question": q,
                "answer": ans,
                "keywords": kw,
                "embedding": emb
            }

        cursor.close()
        conn.close()
        _FAQ_EMBEDDINGS_CACHE.clear()
        _FAQ_EMBEDDINGS_CACHE.update(new_cache)
        print(f"[OK] Semantic Search Engine ready: {len(_FAQ_EMBEDDINGS_CACHE)} FAQs cached (Loaded: {loaded}, Generated: {generated})")
        return True
    except Exception as e:
        print(f"[WARN] sync_all_faq_embeddings error: {e}")
        return False


def sync_single_faq_embedding(faq_id, category, question, answer, keywords):
    """
    Dynamically generates and saves the embedding for a single FAQ (add or edit),
    updating MySQL and immediately refreshing the in-memory cache without restart.
    """
    global _FAQ_EMBEDDINGS_CACHE
    text_to_embed = f"Category: {category}\nQuestion: {question}\nAnswer: {answer}\nKeywords: {keywords}"
    emb = compute_text_embedding(text_to_embed)
    if emb:
        try:
            conn = get_db_connection(use_database=True)
            cursor = conn.cursor()
            cursor.execute(
                "REPLACE INTO faq_embeddings (faq_id, embedding_json) VALUES (%s, %s);",
                (faq_id, json.dumps(emb))
            )
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"[WARN] Failed to save embedding to MySQL for FAQ #{faq_id}: {e}")

    _FAQ_EMBEDDINGS_CACHE[faq_id] = {
        "id": faq_id,
        "category": category,
        "question": question,
        "answer": answer,
        "keywords": keywords,
        "embedding": emb
    }
    print(f"[OK] Dynamically updated embedding cache for FAQ #{faq_id} ('{question[:30]}...')")


# =============================================================================
# ADMIN AUTHENTICATION HELPERS
# =============================================================================
def verify_admin_credentials(username, password):
    """
    Verifies admin credentials using parameterized SQL and password hashing.
    Returns: (is_authenticated, user_dict_or_none)
    """
    if not username or not password:
        return False, None

    try:
        conn = get_db_connection(use_database=True)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, username, password_hash, created_at FROM admin_users WHERE username = %s LIMIT 1;",
            (username.strip(),)
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            # Do not return the password hash in the user dict
            user.pop("password_hash", None)
            return True, user
        return False, None
    except Error as e:
        print(f"[ERROR] verify_admin_credentials error: {e}")
        return False, None


# =============================================================================
# ADMIN DASHBOARD ANALYTICS & LOGGING
# =============================================================================
def log_chat_interaction(user_query, matched_category, response_source):
    """Logs student chat questions to chat_logs for live analytics."""
    try:
        conn = get_db_connection(use_database=True)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_logs (user_query, matched_category, response_source) VALUES (%s, %s, %s);",
            (user_query[:500], matched_category[:100] if matched_category else "Uncategorized", response_source[:50])
        )
        cursor.close()
        conn.close()
    except Error as e:
        print(f"[WARN] Failed to log chat interaction: {e}")


def log_feedback(rating, comment=""):
    """Logs student satisfaction rating ('helpful' or 'unhelpful')."""
    try:
        conn = get_db_connection(use_database=True)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO feedback_logs (rating, comment) VALUES (%s, %s);",
            (rating[:20], comment[:500] if comment else "")
        )
        cursor.close()
        conn.close()
        return True
    except Error as e:
        print(f"[WARN] Failed to log feedback: {e}")
        return False


def get_dashboard_metrics():
    """
    Computes live analytics for the admin dashboard based strictly on actual data:
    - Total FAQs count
    - Category distribution breakdown
    - Total student chat inquiries
    - Answered vs Fallback rate
    - Feedback summary count
    """
    metrics = {
        "total_faqs": 0,
        "categories_breakdown": [],
        "total_chats": 0,
        "answered_chats": 0,
        "fallback_chats": 0,
        "helpful_feedback": 0,
        "unhelpful_feedback": 0,
        "recent_queries": []
    }
    try:
        conn = get_db_connection(use_database=True)
        cursor = conn.cursor(dictionary=True)

        # 1. Total FAQs
        cursor.execute("SELECT COUNT(*) AS count FROM campus_faqs;")
        metrics["total_faqs"] = cursor.fetchone()["count"]

        # 2. Categories breakdown
        cursor.execute("SELECT category, COUNT(*) AS count FROM campus_faqs GROUP BY category ORDER BY count DESC;")
        metrics["categories_breakdown"] = cursor.fetchall()

        # 3. Total Chat Inquiries
        cursor.execute("SELECT COUNT(*) AS count FROM chat_logs;")
        metrics["total_chats"] = cursor.fetchone()["count"]

        # 4. Fallback vs Answered Count
        cursor.execute("SELECT COUNT(*) AS count FROM chat_logs WHERE response_source = 'mysql_fallback';")
        metrics["fallback_chats"] = cursor.fetchone()["count"]
        metrics["answered_chats"] = max(0, metrics["total_chats"] - metrics["fallback_chats"])

        # 5. Feedback counts
        cursor.execute("SELECT rating, COUNT(*) AS count FROM feedback_logs GROUP BY rating;")
        for row in cursor.fetchall():
            if row["rating"].lower() == "helpful":
                metrics["helpful_feedback"] = row["count"]
            elif row["rating"].lower() == "unhelpful":
                metrics["unhelpful_feedback"] = row["count"]

        # 6. Recent Queries
        cursor.execute("SELECT id, user_query, matched_category, response_source, created_at FROM chat_logs ORDER BY created_at DESC LIMIT 10;")
        metrics["recent_queries"] = cursor.fetchall()

        cursor.close()
        conn.close()
    except Error as e:
        print(f"[ERROR] get_dashboard_metrics error: {e}")

    return metrics


# =============================================================================
# ADMIN FAQ CRUD (CREATE, READ, UPDATE, DELETE)
# =============================================================================
def get_all_faqs(search_query=None, category_filter=None):
    """
    Retrieves all campus FAQs with optional search and category filters.
    Uses parameterized SQL queries.
    """
    faqs = []
    try:
        conn = get_db_connection(use_database=True)
        cursor = conn.cursor(dictionary=True)

        sql = "SELECT id, category, question, answer, keywords FROM campus_faqs WHERE 1=1"
        params = []

        if category_filter and category_filter.strip():
            sql += " AND category = %s"
            params.append(category_filter.strip())

        if search_query and search_query.strip():
            search_param = f"%{search_query.strip()}%"
            sql += " AND (question LIKE %s OR answer LIKE %s OR keywords LIKE %s OR category LIKE %s)"
            params.extend([search_param, search_param, search_param, search_param])

        sql += " ORDER BY id DESC;"
        cursor.execute(sql, tuple(params))
        faqs = cursor.fetchall()
        cursor.close()
        conn.close()
    except Error as e:
        print(f"[ERROR] get_all_faqs error: {e}")

    return faqs


def get_faq_by_id(faq_id):
    """Retrieves a single FAQ record by its ID using parameterized SQL."""
    try:
        conn = get_db_connection(use_database=True)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, category, question, answer, keywords FROM campus_faqs WHERE id = %s LIMIT 1;", (faq_id,))
        faq = cursor.fetchone()
        cursor.close()
        conn.close()
        return faq
    except Error as e:
        print(f"[ERROR] get_faq_by_id error: {e}")
        return None


def get_categories_list():
    """Returns a list of distinct FAQ categories currently in MySQL."""
    try:
        conn = get_db_connection(use_database=True)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM campus_faqs ORDER BY category ASC;")
        categories = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return categories
    except Error as e:
        print(f"[ERROR] get_categories_list error: {e}")
        return []


def add_faq(category, question, answer, keywords):
    """
    Inserts a new campus FAQ into MySQL using parameterized SQL.
    Validates input fields and immediately updates semantic embeddings.
    """
    category = category.strip() if category else ""
    question = question.strip() if question else ""
    answer = answer.strip() if answer else ""
    keywords = keywords.strip() if keywords else ""

    if not category or not question or not answer:
        return False, "Category, Question, and Answer fields are required."

    try:
        conn = get_db_connection(use_database=True)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO campus_faqs (category, question, answer, keywords) VALUES (%s, %s, %s, %s);",
            (category, question, answer, keywords)
        )
        new_id = cursor.lastrowid
        cursor.close()
        conn.close()

        # Dynamic semantic vector synchronization
        sync_single_faq_embedding(new_id, category, question, answer, keywords)

        return True, f"FAQ #{new_id} successfully added."
    except mysql.connector.IntegrityError:
        return False, "An FAQ with this exact question already exists. Please choose a unique question."
    except Error as e:
        return False, f"Database error: {str(e)}"


def update_faq(faq_id, category, question, answer, keywords):
    """
    Updates an existing campus FAQ in MySQL using parameterized SQL.
    Immediately re-generates semantic embedding and updates cache without restart.
    """
    category = category.strip() if category else ""
    question = question.strip() if question else ""
    answer = answer.strip() if answer else ""
    keywords = keywords.strip() if keywords else ""

    if not category or not question or not answer:
        return False, "Category, Question, and Answer fields are required."

    try:
        conn = get_db_connection(use_database=True)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE campus_faqs
            SET category = %s, question = %s, answer = %s, keywords = %s
            WHERE id = %s;
            """,
            (category, question, answer, keywords, faq_id)
        )
        rows_affected = cursor.rowcount
        cursor.close()
        conn.close()

        # Dynamic semantic vector synchronization
        sync_single_faq_embedding(faq_id, category, question, answer, keywords)

        if rows_affected > 0:
            return True, f"FAQ #{faq_id} successfully updated."
        return True, "No changes were made to FAQ."
    except mysql.connector.IntegrityError:
        return False, "Another FAQ already has this exact question."
    except Error as e:
        return False, f"Database error: {str(e)}"


def delete_faq(faq_id):
    """
    Deletes an FAQ record from MySQL using parameterized SQL.
    MySQL CASCADE foreign key automatically deletes vector from faq_embeddings.
    Immediately evicts the vector from in-memory cache without restart.
    """
    global _FAQ_EMBEDDINGS_CACHE
    try:
        conn = get_db_connection(use_database=True)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM campus_faqs WHERE id = %s;", (faq_id,))
        rows_affected = cursor.rowcount
        cursor.close()
        conn.close()

        # Evict from in-memory cache
        _FAQ_EMBEDDINGS_CACHE.pop(faq_id, None)

        if rows_affected > 0:
            return True, f"FAQ #{faq_id} deleted successfully."
        return False, f"FAQ #{faq_id} not found."
    except Error as e:
        return False, f"Database error: {str(e)}"


# =============================================================================
# HYBRID NATURAL-LANGUAGE & SEMANTIC SEARCH ENGINE
# =============================================================================
def search_faqs_in_db(user_query):
    """
    Hybrid Natural-Language & Semantic Search Engine:
    1. Conversational greetings and polite appreciation handling.
    2. Lazy-loads _FAQ_EMBEDDINGS_CACHE if empty.
    3. Semantic vector search (models/gemini-embedding-001 + Cosine Similarity).
    4. Fuzzy typo-tolerant lexical matching (SequenceMatcher + token overlap).
    5. Strict relevance threshold to prevent false positives on unknown/unrelated queries.
    
    Returns: (answer_text, list_of_suggestion_strings, matched_category_or_none)
    """
    if not user_query or not isinstance(user_query, str) or not user_query.strip():
        return None, [], None

    query = user_query.strip()
    lowered = query.lower()

    # Rule 1: Greeting check
    if any(greet in lowered for greet in ["hi", "hello", "hey", "greetings", "good morning", "good afternoon", "good evening"]):
        return (
            "Hello! 👋 I'm **CampusBot**, your virtual assistant for Horizon Institute. How can I assist you with your admissions, academic courses, examinations, or campus life today?",
            [
                "How can I apply for admission?",
                "Where can I find placement information?",
                "What academic programs are offered?"
            ],
            "Greetings"
        )

    # Rule 2: Thank you check
    if any(word in lowered for word in ["thank", "thanks", "appreciate"]):
        return (
            "You're very welcome! 😊 Feel free to ask if you have any questions about admissions, exams, hostels, or placements.",
            [
                "When are the semester examinations conducted?",
                "Where can I find placement information?"
            ],
            "General"
        )

    global _FAQ_EMBEDDINGS_CACHE
    if not _FAQ_EMBEDDINGS_CACHE:
        sync_all_faq_embeddings()

    # If still empty (e.g. database has 0 faqs), return fallback
    if not _FAQ_EMBEDDINGS_CACHE:
        return None, [], None

    # Step A: Compute Query Embedding
    query_emb = compute_text_embedding(query)

    # Clean query tokens for fuzzy matching
    STOPWORDS = {
        "what", "where", "when", "which", "who", "whom", "whose", "why", "how",
        "can", "could", "would", "should", "does", "did", "the", "and", "for",
        "with", "about", "are", "were", "been", "being", "have", "has", "had",
        "today", "tell", "show", "give", "please", "some", "any", "find", "get",
        "info", "this", "that", "there", "their", "from", "into", "take", "place",
        "much", "many", "want", "know", "need", "about", "your"
    }
    clean_query = re.sub(r"[^\w\s]", " ", lowered)
    q_tokens = [w for w in clean_query.split() if len(w) > 2 and w not in STOPWORDS]

    best_faq = None
    best_score = -1.0
    best_source = None

    SEMANTIC_THRESHOLD = 0.58  # Cosine similarity threshold for confident semantic match
    LEXICAL_THRESHOLD = 0.65   # Typo / fuzzy token ratio threshold

    for faq in _FAQ_EMBEDDINGS_CACHE.values():
        cos_score = 0.0
        if query_emb and faq.get("embedding"):
            cos_score = cosine_similarity(query_emb, faq["embedding"])

        # Lexical & fuzzy similarity computation
        f_question = faq["question"].lower()
        f_keywords = faq["keywords"].lower()
        f_combined = f"{f_question} {f_keywords}"

        # 1. Fuzzy sequence matcher against question title
        seq_ratio = SequenceMatcher(None, clean_query, f_question).ratio()

        # 2. Token overlap & typo tolerance (matching misspelled tokens)
        token_hits = 0
        if q_tokens:
            for qt in q_tokens:
                if qt in f_combined:
                    token_hits += 1
                else:
                    # Check partial fuzzy match for typos (e.g. 'admision' vs 'admission')
                    for ft in f_combined.split():
                        if len(ft) > 3 and SequenceMatcher(None, qt, ft).ratio() >= 0.80:
                            token_hits += 1
                            break
            token_ratio = token_hits / len(q_tokens)
        else:
            token_ratio = 0.0

        fuzzy_score = max(seq_ratio, token_ratio)

        # Decide effective score
        if cos_score >= SEMANTIC_THRESHOLD:
            effective_score = cos_score
            src = "semantic"
        elif fuzzy_score >= LEXICAL_THRESHOLD:
            effective_score = fuzzy_score * 0.9
            src = "fuzzy_lexical"
        else:
            effective_score = max(cos_score, fuzzy_score * 0.5)
            src = "insufficient"

        if effective_score > best_score:
            best_score = effective_score
            best_faq = faq
            best_source = src

    # Rejection gate: if top score does not meet threshold, treat as ungrounded/unknown
    if not best_faq or (best_source == "insufficient" and best_score < SEMANTIC_THRESHOLD):
        active_questions = [f["question"] for f in _FAQ_EMBEDDINGS_CACHE.values()]
        import random
        fallback_suggestions = random.sample(active_questions, min(4, len(active_questions)))
        return None, fallback_suggestions, "Unmatched"

    # Matched FAQ: Pick 3 alternative questions for suggestions
    other_questions = [f["question"] for f in _FAQ_EMBEDDINGS_CACHE.values() if f["id"] != best_faq["id"]]
    import random
    suggestions = random.sample(other_questions, min(3, len(other_questions))) if other_questions else []

    return best_faq["answer"], suggestions, best_faq["category"]


if __name__ == "__main__":
    print("Testing MySQL connection and initializing database...")
    success, result = init_database()
    if success:
        print(f"[OK] Total FAQs: {result}")
        print("Testing verify_admin_credentials...")
        ok, user = verify_admin_credentials("admin", "Admin@Horizon2026!")
        print(f"[OK] Admin Auth Test: {ok} | User: {user}")
        metrics = get_dashboard_metrics()
        print(f"[OK] Dashboard Metrics FAQs: {metrics['total_faqs']} | Categories count: {len(metrics['categories_breakdown'])}")
    else:
        print("Initialization failed:", result)
