"""
=============================================================================
HORIZON INSTITUTE - AI / NLP SERVICE LAYER (Phase 4)
=============================================================================
Combines MySQL FAQ retrieval with Google Gemini Generative AI:
1. Input validation & prompt injection defenses.
2. Grounded generation: Answers are strictly derived from verified MySQL records.
3. Anti-hallucination safeguards: Never invents dates, fees, or campus policies.
4. Resilient auto-fallback: Works with live Gemini AI or falls back to MySQL.
"""

import os
import re
from dotenv import load_dotenv
from database import search_faqs_in_db

# Load environment variables
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# Import google.genai if available
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


# Known prompt-injection and jailbreak patterns to defend against
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior|above)",
    r"forget\s+(all\s+)?(previous|prior|system)\s+prompt",
    r"system\s+prompt",
    r"jailbreak",
    r"dan\s+mode",
    r"developer\s+mode",
    r"pretend\s+you\s+are",
    r"you\s+are\s+now",
    r"act\s+as\s+an\s+unrestricted",
    r"bypass\s+restrictions"
]


def validate_and_sanitize_input(raw_query):
    """
    Validates input length and screens for prompt injection attempts.
    Returns: (is_valid, sanitized_text, error_message)
    """
    if not raw_query or not isinstance(raw_query, str):
        return False, "", "Please enter a valid campus question."

    text = raw_query.strip()

    # Rule 1: Length constraints
    if len(text) == 0:
        return False, "", "Please enter a valid campus question."
    if len(text) > 350:
        return False, "", "Your question is too long. Please keep it under 350 characters."

    # Rule 2: Screening against prompt injection & override attempts
    lowered = text.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lowered):
            return False, "", (
                "🛡️ CampusBot is designed strictly to assist with Horizon Institute "
                "admissions, courses, placements, and campus life. "
                "How may I assist you with your studies or campus questions today?"
            )

    return True, text, None


def get_gemini_api_key():
    """Retrieves the current GEMINI_API_KEY from .env dynamically."""
    load_dotenv(override=True)
    return os.getenv("GEMINI_API_KEY", "").strip()


def is_gemini_configured():
    """Checks whether a valid non-placeholder Gemini API key is configured."""
    key = get_gemini_api_key()
    return (
        GENAI_AVAILABLE
        and bool(key)
        and not key.startswith("your_")
        and len(key) > 10
    )


def generate_campus_ai_response(user_query):
    """
    Processes a student query through the RAG (Retrieval-Augmented Generation) pipeline:
    1. Validates and sanitizes query against prompt injection.
    2. Queries MySQL database for verified campus records.
    3. If not found in MySQL: Returns official fallback (never hallucinates).
    4. If found in MySQL: Grounds Gemini response using verified context.
    5. If Gemini is unconfigured or fails: Falls back directly to MySQL record.
    """
    # Step 1: Input Validation & Sanitization
    is_valid, clean_text, validation_error = validate_and_sanitize_input(user_query)
    if not is_valid:
        return {
            "success": True,
            "reply": validation_error,
            "suggestions": [
                "How can I apply for admission?",
                "Where can I find placement information?",
                "What academic programs are offered?"
            ],
            "source": "safety_filter",
            "matched_category": "Security"
        }

    # Step 2: Retrieve Source of Truth from MySQL Database (Semantic Vector + Fuzzy)
    retrieved_answer, suggestions, matched_category = search_faqs_in_db(clean_text)

    # Step 3: Anti-Hallucination Guard:
    # If no relevant record was found in the campus database, return the grounded fallback directly
    # rather than letting the LLM fabricate or invent campus details.
    if not retrieved_answer:
        return {
            "success": True,
            "reply": (
                "I couldn't find verified campus information regarding that question in our official database. "
                "For specific questions regarding college policies, special approvals, or topics not listed in our FAQs, "
                "please contact the campus helpdesk at **helpdesk@horizon.edu** or visit the **Administration Office (Block A)**."
            ),
            "suggestions": suggestions if suggestions else [
                "How can I apply for admission?",
                "What academic programs are offered?",
                "When are the semester examinations conducted?"
            ],
            "source": "mysql_fallback",
            "matched_category": "Unmatched"
        }

    # Quick greetings / thanks handler
    if any(greet in clean_text.lower() for greet in ["hi", "hello", "hey", "greetings", "good morning", "good afternoon", "thanks", "thank you"]):
        return {
            "success": True,
            "reply": retrieved_answer,
            "suggestions": suggestions,
            "source": "greeting",
            "matched_category": matched_category or "General"
        }

    # Step 4: Grounded AI Generation (if Gemini API key is configured)
    if is_gemini_configured():
        try:
            api_key = get_gemini_api_key()
            client = genai.Client(api_key=api_key, http_options={"timeout": 30000})

            system_instruction = (
                "You are CampusBot, the friendly, professional virtual assistant for Horizon Institute of Technology.\n\n"
                "STRICT GROUNDING & NATURAL-LANGUAGE RULES:\n"
                "1. Answer the student's question in a clear, natural, and helpful tone strictly using ONLY the provided Verified Campus Information.\n"
                "2. Directly answer their specific phrasing (for example, if they ask 'When does college start?' or 'When do classes begin?', address the orientation / semester schedule in the verified context).\n"
                "3. NEVER invent, assume, or fabricate any dates, admission deadlines, fee amounts, hostel details, or policies not stated in the verified context.\n"
                "4. If the student asks about specific facilities, policies, or fees NOT mentioned in the verified context, you MUST explicitly state that this information is not available in our verified campus records and direct them to contact helpdesk@horizon.edu.\n"
                "5. Format your response cleanly using markdown bullet points where appropriate."
            )

            prompt = (
                f"[VERIFIED CAMPUS INFORMATION]:\n"
                f"Category: {matched_category}\n"
                f"Content: {retrieved_answer}\n\n"
                f"[STUDENT QUESTION]:\n"
                f"{clean_text}\n\n"
                f"Please provide a helpful, natural response strictly grounded in the verified information above."
            )

            # Resilient Model Failover: Try gemini-3-flash-preview first (active, fastest), fallback to gemini-3.8-flash
            candidate_models = ["models/gemini-3-flash-preview", "models/gemini-3.8-flash"]
            for model_name in candidate_models:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            temperature=0.2  # Low temperature for strict factual grounding
                        )
                    )
                    if response and response.text:
                        return {
                            "success": True,
                            "reply": response.text.strip(),
                            "suggestions": suggestions,
                            "source": "gemini_grounded",
                            "matched_category": matched_category or "General"
                        }
                except Exception as model_err:
                    print(f"[WARN] {model_name} call failed: {model_err}")
                    continue

        except Exception as err:
            # If all Gemini calls fail (network issue, rate limit, invalid key),
            # gracefully fall back to verified MySQL answer without crashing
            print(f"[WARN] Gemini generation failed, falling back to verified MySQL context: {err}")

    # Fallback: Return the verified MySQL record directly (Guaranteed 100% factual uptime)
    return {
        "success": True,
        "reply": retrieved_answer,
        "suggestions": suggestions,
        "source": "mysql_grounded",
        "matched_category": matched_category or "General"
    }


def get_ai_service_status():
    """Returns the current status of the AI engine."""
    if is_gemini_configured():
        return "Google Gemini (Grounded RAG Mode)"
    else:
        return "MySQL Grounded Engine (Active - Paste GEMINI_API_KEY in .env to enable generative AI)"
