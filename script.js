/**
 * ==============================================================================
 * HORIZON INSTITUTE - CAMPUS ASSISTANCE CHATBOT
 * Frontend Script with Decoupled Architecture for Future Python Flask Integration
 * ==============================================================================
 * 
 * ARCHITECTURE OVERVIEW:
 * 1. CAMPUS_DEMO_DATA: Mock knowledge base (Admissions, Academics, Placements, etc.)
 * 2. CampusBotService: Service layer handling query matching & answers.
 *    -> Swappable for a Python Flask / FastAPI backend via fetch('/api/chat').
 * 3. ChatUIController: Manages message bubbles, scrolling, typing dots, and inputs.
 * 4. PageController: Handles mobile navbar, section smooth scrolls, and page buttons.
 */

// ==============================================================================
// 1. DEMO CAMPUS KNOWLEDGE BASE
// ==============================================================================
const CAMPUS_DEMO_DATA = {
  institution: "Horizon Institute of Technology",
  admissions: {
    overview: "Admissions for Academic Year 2026-27 are currently open for Undergraduate (B.Tech) and Postgraduate (M.Tech, MBA, MCA) programs.",
    process: "Application steps:\n1. Register at admissions.horizon.edu\n2. Fill academic details and upload grade transcripts\n3. Submit national entrance scores (or appear for Horizon Entrance Test)\n4. Attend online counseling and confirm seat reservation.",
    deadlines: "Early round deadline: June 15, 2026. Regular admission round closes on July 30, 2026.",
    eligibility: "Undergraduate programs require a minimum of 60% aggregate in Physics, Chemistry, and Mathematics (10+2).",
    scholarships: "Merit scholarships up to 50% tuition waiver are available for top 5% rank holders, state sports medalists, and distinguished STEM candidates."
  },
  academics: {
    programs: [
      "B.Tech in Computer Science & Artificial Intelligence",
      "B.Tech in Electronics & IoT Systems",
      "B.Tech in Data Science & Big Data Analytics",
      "B.Tech in Mechanical & Mechatronics Engineering",
      "M.Tech in Autonomous Systems & Robotics",
      "Master of Business Administration (MBA - Tech Management)"
    ],
    curriculum: "The academic curriculum features hands-on laboratory modules, mandatory industrial internships, and semester-long capstone projects."
  },
  placements: {
    stats: "For 2025-26, our demo campus recorded an overall 92% placement rate across all engineering departments.",
    packages: "Highest Package: $38,000 / year (Demo). Average Package: $14,500 / year (Demo).",
    recruiters: "Top demo recruiters include TechNova Labs, Apex Cloud Systems, CyberCore Global, DataPulse Analytics, and GreenTech Dynamics.",
    cellContact: "Career Development Cell: careers@horizon.edu | Room 302, Student Activity Building."
  },
  facilities: {
    hostels: "Separate air-conditioned and non-AC residential blocks for men and women, featuring high-speed Wi-Fi, 24/7 security, and hygienic cafeterias.",
    library: "The Central Digital Library houses over 80,000 physical volumes, 250,000 e-journals, and private research study pods."
  },
  events: {
    upcoming: [
      "Nov 18, 2026: 36-Hour Hackathon on Community AI Solutions",
      "Dec 05, 2026: International Tech Symposium & Future of AI Forum",
      "Jan 14, 2027: Annual Spring Campus Placement Fair"
    ]
  },
  contact: {
    address: "100 Knowledge Boulevard, Innovation District, Tech City 560001",
    email: "admissions@horizon.edu / helpdesk@horizon.edu",
    phone: "+1 (800) 555-0199 (Mon-Fri, 9:00 AM - 5:00 PM)"
  }
};

// ==============================================================================
// 2. CHATBOT SERVICE LAYER (BACKEND-READY)
// ==============================================================================
/**
 * CampusBotService is responsible for taking a user message and returning
 * an answer.
 * 
 * FUTURE FLASK / AI INTEGRATION:
 * When you build your Python Flask backend, simply set `USE_LOCAL_ENGINE = false`
 * and point `API_ENDPOINT` to your Flask route (e.g. 'http://127.0.0.1:5000/api/chat').
 * No UI code needs to be modified!
 */
class CampusBotService {
  constructor() {
    // Set to false to communicate directly with our running Python Flask backend
    this.USE_LOCAL_ENGINE = false;
    this.API_ENDPOINT = "/api/chat";
    this.updateStatusBadge();
  }

  updateStatusBadge() {
    const badge = document.getElementById("backend-status-pill");
    if (badge) {
      if (!this.USE_LOCAL_ENGINE) {
        badge.textContent = "Flask + MySQL (Connected)";
        badge.style.backgroundColor = "#d1fae5";
        badge.style.color = "#065f46";
      } else {
        badge.textContent = "Local Engine (Demo)";
      }
    }
  }

  /**
   * Main dispatch method for queries
   * @param {string} userMessage - Text typed by the student
   * @returns {Promise<{text: string, suggestions: string[]}>}
   */
  async getResponse(userMessage) {
    if (!this.USE_LOCAL_ENGINE) {
      return await this.fetchFromFlaskBackend(userMessage);
    } else {
      return await this.simulateLocalResponse(userMessage);
    }
  }

  /**
   * Placeholder for future Python Flask / AI REST API integration
   */
  async fetchFromFlaskBackend(userMessage) {
    try {
      const response = await fetch(this.API_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage })
      });

      if (!response.ok) {
        throw new Error(`Server returned HTTP ${response.status}`);
      }

      const data = await response.json();
      return {
        text: data.reply || data.text,
        suggestions: data.suggestions || []
      };
    } catch (error) {
      console.warn("Backend request failed, falling back to local engine:", error);
      return {
        text: "⚠️ Could not connect to the campus backend server. Falling back to local offline mode.\n\n" + 
              this.matchLocalRules(userMessage).text,
        suggestions: ["Admissions", "Placements", "Contact"]
      };
    }
  }

  /**
   * Simulates a natural network delay (400ms - 800ms) and processes query locally
   */
  async simulateLocalResponse(userMessage) {
    return new Promise((resolve) => {
      const delay = Math.floor(Math.random() * 400) + 400; // 400-800ms typing feel
      setTimeout(() => {
        resolve(this.matchLocalRules(userMessage));
      }, delay);
    });
  }

  /**
   * Rule-based Keyword Matching Engine
   * Categorizes user input and matches it with demo data.
   */
  matchLocalRules(rawText) {
    const text = rawText.toLowerCase().trim();

    // 1. Greetings
    if (/^(hi|hello|hey|good morning|good afternoon|greetings|start)/i.test(text)) {
      return {
        text: "Hello! 👋 I'm **CampusBot**, your virtual assistant for Horizon Institute. How can I assist your campus journey today?",
        suggestions: [
          "How can I apply for admission?",
          "Where can I find placement information?",
          "What academic programs are offered?"
        ]
      };
    }

    // 2. Admissions & Applications
    if (text.includes("admission") || text.includes("apply") || text.includes("application") || text.includes("enroll")) {
      return {
        text: `🎓 **Admissions Overview:**\n${CAMPUS_DEMO_DATA.admissions.overview}\n\n**Application Steps:**\n${CAMPUS_DEMO_DATA.admissions.process}\n\n**Deadlines:** ${CAMPUS_DEMO_DATA.admissions.deadlines}`,
        suggestions: [
          "What scholarships are available?",
          "What are the eligibility criteria?",
          "What academic programs are offered?"
        ]
      };
    }

    // 3. Scholarships & Fees
    if (text.includes("scholarship") || text.includes("fee") || text.includes("tuition") || text.includes("financial aid")) {
      return {
        text: `💰 **Scholarships & Financial Aid:**\n${CAMPUS_DEMO_DATA.admissions.scholarships}\n\nFor tuition schedules and payment installments, please reach out to **finaid@horizon.edu**.`,
        suggestions: [
          "How can I apply for admission?",
          "Contact campus helpdesk"
        ]
      };
    }

    // 4. Eligibility
    if (text.includes("eligib") || text.includes("requirement") || text.includes("qualification")) {
      return {
        text: `📋 **Eligibility Requirements:**\n${CAMPUS_DEMO_DATA.admissions.eligibility}\n\nInternational applicants require an equivalent high school diploma verified by the Academic Board.`,
        suggestions: [
          "How can I apply for admission?",
          "What academic programs are offered?"
        ]
      };
    }

    // 5. Placements & Careers
    if (text.includes("placement") || text.includes("job") || text.includes("package") || text.includes("recruiter") || text.includes("internship")) {
      return {
        text: `💼 **Placements & Career Center:**\n• **Placement Rate:** ${CAMPUS_DEMO_DATA.placements.stats}\n• **Salary Packages:** ${CAMPUS_DEMO_DATA.placements.packages}\n• **Key Recruiters:** ${CAMPUS_DEMO_DATA.placements.recruiters}\n• **Contact:** ${CAMPUS_DEMO_DATA.placements.cellContact}`,
        suggestions: [
          "What academic programs are offered?",
          "What are the upcoming events?",
          "Contact campus helpdesk"
        ]
      };
    }

    // 6. Academics & Programs
    if (text.includes("academic") || text.includes("program") || text.includes("course") || text.includes("branch") || text.includes("degree")) {
      const list = CAMPUS_DEMO_DATA.academics.programs.map(p => `• ${p}`).join("\n");
      return {
        text: `📚 **Featured Academic Programs:**\n${list}\n\n${CAMPUS_DEMO_DATA.academics.curriculum}`,
        suggestions: [
          "How can I apply for admission?",
          "Where can I find placement information?",
          "What are the hostel and library facilities?"
        ]
      };
    }

    // 7. Events & Hackathons
    if (text.includes("event") || text.includes("hackathon") || text.includes("symposium") || text.includes("fest")) {
      const eventList = CAMPUS_DEMO_DATA.events.upcoming.map(e => `• ${e}`).join("\n");
      return {
        text: `📅 **Upcoming Campus Events:**\n${eventList}\n\nAll registered students can RSVP through the Student Portal.`,
        suggestions: [
          "What academic programs are offered?",
          "Contact campus helpdesk"
        ]
      };
    }

    // 8. Facilities (Hostel / Library / Sports)
    if (text.includes("hostel") || text.includes("library") || text.includes("facility") || text.includes("accommodation") || text.includes("dorm")) {
      return {
        text: `🏫 **Campus Living & Facilities:**\n\n**Residential Hostels:**\n${CAMPUS_DEMO_DATA.facilities.hostels}\n\n**Central Library:**\n${CAMPUS_DEMO_DATA.facilities.library}`,
        suggestions: [
          "How can I apply for admission?",
          "Contact campus helpdesk"
        ]
      };
    }

    // 9. Contact / Helpdesk / Phone / Email
    if (text.includes("contact") || text.includes("phone") || text.includes("email") || text.includes("address") || text.includes("location") || text.includes("helpdesk")) {
      return {
        text: `📞 **Campus Contact & Helpdesk:**\n• **Address:** ${CAMPUS_DEMO_DATA.contact.address}\n• **Email:** ${CAMPUS_DEMO_DATA.contact.email}\n• **Helpline:** ${CAMPUS_DEMO_DATA.contact.phone}`,
        suggestions: [
          "How can I apply for admission?",
          "Where can I find placement information?"
        ]
      };
    }

    // 10. Thank You
    if (/thank|thanks|appreciate/i.test(text)) {
      return {
        text: "You're very welcome! 😊 Feel free to ask if you need anything else regarding admissions, courses, or campus life.",
        suggestions: [
          "What are the upcoming events?",
          "Where can I find placement information?"
        ]
      };
    }

    // Default Fallback
    return {
      text: `I'm not quite sure about that specific query yet. As a campus assistant, I can help you with:\n\n• **Admissions & Eligibility**\n• **Academic Programs & Courses**\n• **Placements & Recruiter Stats**\n• **Campus Facilities (Hostel & Library)**\n• **Upcoming Events & Helpdesk Contact**\n\nTry clicking one of the suggested topics below!`,
      suggestions: [
        "How can I apply for admission?",
        "Where can I find placement information?",
        "What academic programs are offered?",
        "Contact campus helpdesk"
      ]
    };
  }
}

// ==============================================================================
// 3. CHATBOT UI CONTROLLER
// ==============================================================================
/**
 * ChatUIController handles all DOM elements, user events, message rendering,
 * and auto-scrolling. It interacts with CampusBotService solely through
 * promises, keeping display and business logic clean and decoupled.
 */
class ChatUIController {
  constructor(botService) {
    this.botService = botService;

    // DOM Elements
    this.launcherBtn = document.getElementById("chatbot-launcher-btn");
    this.chatWindow = document.getElementById("chatbot-window");
    this.closeBtn = document.getElementById("chat-close-btn");
    this.clearBtn = document.getElementById("chat-clear-btn");
    this.chatForm = document.getElementById("chat-form");
    this.chatInput = document.getElementById("chat-input");
    this.messagesContainer = document.getElementById("chat-messages");
    this.typingIndicator = document.getElementById("typing-indicator");
    this.suggestionsContainer = document.getElementById("chat-suggestions");
    this.notificationBadge = document.getElementById("bot-notification-badge");

    this.isOpen = false;
    this.hasGreeted = false;

    this.initEventListeners();
    this.renderWelcomeGreeting();
  }

  initEventListeners() {
    // Open/Close toggle button
    this.launcherBtn.addEventListener("click", () => this.toggleChat());
    this.closeBtn.addEventListener("click", () => this.toggleChat(false));

    // Clear history
    this.clearBtn.addEventListener("click", () => this.clearChatHistory());

    // Send on form submission (Enter key or Send button)
    this.chatForm.addEventListener("submit", (e) => {
      e.preventDefault();
      this.handleUserSubmit();
    });

    // Suggested question chips delegation
    this.suggestionsContainer.addEventListener("click", (e) => {
      const chip = e.target.closest(".chip-btn");
      if (!chip) return;
      const question = chip.getAttribute("data-question");
      if (question) {
        this.submitQuestion(question);
      }
    });

    // Close on Escape key press
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.isOpen) {
        this.toggleChat(false);
      }
    });
  }

  toggleChat(forceState = null) {
    this.isOpen = forceState !== null ? forceState : !this.isOpen;

    if (this.isOpen) {
      this.chatWindow.classList.add("open");
      this.launcherBtn.classList.add("active");
      this.chatWindow.setAttribute("aria-hidden", "false");
      
      // Hide unread badge once opened
      if (this.notificationBadge) {
        this.notificationBadge.style.display = "none";
      }

      // Auto focus input on desktop
      if (window.innerWidth > 768) {
        setTimeout(() => this.chatInput.focus(), 200);
      }
    } else {
      this.chatWindow.classList.remove("open");
      this.launcherBtn.classList.remove("active");
      this.chatWindow.setAttribute("aria-hidden", "true");
    }
  }

  renderWelcomeGreeting() {
    if (this.hasGreeted) return;
    this.hasGreeted = true;

    const welcomeText = "👋 Welcome to **Horizon Institute of Technology**! I am your 24/7 Campus Assistance Bot. How can I help you today?";
    this.appendMessage("bot", welcomeText);
  }

  clearChatHistory() {
    this.messagesContainer.innerHTML = "";
    this.hasGreeted = false;
    this.renderWelcomeGreeting();
  }

  async handleUserSubmit() {
    const rawMessage = this.chatInput.value.trim();
    if (!rawMessage) return;

    // Reset input
    this.chatInput.value = "";
    await this.submitQuestion(rawMessage);
  }

  async submitQuestion(text) {
    // 1. Render User message
    this.appendMessage("user", text);
    this.scrollToBottom();

    // 2. Show Typing Indicator
    this.showTyping(true);

    try {
      // 3. Fetch Response from Service (Local or Flask)
      const response = await this.botService.getResponse(text);

      // 4. Hide Typing & Render Bot Message
      this.showTyping(false);
      this.appendMessage("bot", response.text);

      // 5. Update dynamic suggestion chips if provided
      if (response.suggestions && response.suggestions.length > 0) {
        this.updateSuggestions(response.suggestions);
      }
    } catch (err) {
      console.error("Error retrieving response:", err);
      this.showTyping(false);
      this.appendMessage("bot", "Sorry, I encountered an issue processing your request. Please try again.");
    }

    this.scrollToBottom();
  }

  appendMessage(sender, text) {
    const row = document.createElement("div");
    row.className = `message-row ${sender === "user" ? "user-row" : "bot-row"}`;

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.innerHTML = this.formatMessageText(text);

    const meta = document.createElement("div");
    meta.className = "message-meta";
    meta.textContent = this.getCurrentTime();

    row.appendChild(bubble);
    row.appendChild(meta);

    // If bot message, attach thumbs up/down feedback buttons connected to /api/feedback
    if (sender === "bot") {
      const feedbackRow = document.createElement("div");
      feedbackRow.className = "message-feedback";
      feedbackRow.innerHTML = `
        <button type="button" class="feedback-btn" data-rating="helpful" title="Helpful answer">👍</button>
        <button type="button" class="feedback-btn" data-rating="unhelpful" title="Unhelpful answer">👎</button>
        <span class="feedback-ack"></span>
      `;
      feedbackRow.querySelectorAll(".feedback-btn").forEach(btn => {
        btn.addEventListener("click", () => this.sendFeedback(btn, feedbackRow));
      });
      row.appendChild(feedbackRow);
    }

    this.messagesContainer.appendChild(row);
    this.scrollToBottom();
  }

  async sendFeedback(btn, container) {
    const rating = btn.getAttribute("data-rating");
    const ack = container.querySelector(".feedback-ack");
    container.querySelectorAll(".feedback-btn").forEach(b => b.disabled = true);
    btn.classList.add("active");
    if (ack) ack.textContent = "Thank you for your feedback!";
    try {
      await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating: rating })
      });
    } catch (e) {
      console.warn("Feedback log error:", e);
    }
  }

  /**
   * Simple markdown-style formatter (converts bold **text**, newlines, and bullet points)
   */
  formatMessageText(raw) {
    let formatted = raw
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>") // bold
      .replace(/\n\n/g, "<br><br>")
      .replace(/\n/g, "<br>");
    return formatted;
  }

  getCurrentTime() {
    const now = new Date();
    return now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  showTyping(show) {
    if (show) {
      this.typingIndicator.classList.remove("hidden");
    } else {
      this.typingIndicator.classList.add("hidden");
    }
    this.scrollToBottom();
  }

  scrollToBottom() {
    this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
  }

  updateSuggestions(suggestionsList) {
    this.suggestionsContainer.innerHTML = "";
    suggestionsList.forEach((q) => {
      const btn = document.createElement("button");
      btn.className = "chip-btn";
      btn.setAttribute("data-question", q);
      btn.textContent = q;
      this.suggestionsContainer.appendChild(btn);
    });
  }
}

// ==============================================================================
// 4. PAGE CONTROLLER (NAVIGATION, MOBILE MENU, QUICK PROMPTS)
// ==============================================================================
class PageController {
  constructor(chatUI) {
    this.chatUI = chatUI;
    this.mobileToggle = document.getElementById("mobile-menu-toggle");
    this.navLinks = document.getElementById("nav-links");
    this.headerChatBtn = document.getElementById("header-chat-btn");
    this.heroChatTrigger = document.getElementById("hero-chat-trigger");
    this.previewOpenChat = document.getElementById("preview-open-chat");

    this.initNavigation();
  }

  initNavigation() {
    // Mobile menu toggle
    if (this.mobileToggle && this.navLinks) {
      this.mobileToggle.addEventListener("click", () => {
        const isOpen = this.navLinks.classList.toggle("mobile-open");
        this.mobileToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
      });

      // Close mobile menu when link is clicked
      this.navLinks.querySelectorAll(".nav-link").forEach((link) => {
        link.addEventListener("click", () => {
          this.navLinks.classList.remove("mobile-open");
          this.mobileToggle.setAttribute("aria-expanded", "false");
        });
      });
    }

    // Header & Hero Chat Launchers
    if (this.headerChatBtn) {
      this.headerChatBtn.addEventListener("click", () => this.chatUI.toggleChat(true));
    }
    if (this.heroChatTrigger) {
      this.heroChatTrigger.addEventListener("click", () => this.chatUI.toggleChat(true));
    }
    if (this.previewOpenChat) {
      this.previewOpenChat.addEventListener("click", () => {
        this.chatUI.toggleChat(true);
        this.chatUI.submitQuestion("How can I apply for admission?");
      });
    }

    // Active link highlighting on scroll
    window.addEventListener("scroll", () => this.highlightActiveNav());
  }

  highlightActiveNav() {
    const sections = document.querySelectorAll("section[id]");
    const scrollY = window.pageYOffset;

    sections.forEach((current) => {
      const sectionHeight = current.offsetHeight;
      const sectionTop = current.offsetTop - 120;
      const sectionId = current.getAttribute("id");

      const navItem = document.querySelector(`.nav-links a[href*="${sectionId}"]`);
      if (navItem) {
        if (scrollY > sectionTop && scrollY <= sectionTop + sectionHeight) {
          navItem.classList.add("active");
        } else {
          navItem.classList.remove("active");
        }
      }
    });
  }
}

// ==============================================================================
// 5. GLOBAL INITIALIZATION
// ==============================================================================
let appChatUI = null;

document.addEventListener("DOMContentLoaded", () => {
  // 1. Initialize Bot Service
  const botService = new CampusBotService();

  // 2. Initialize UI Controller
  appChatUI = new ChatUIController(botService);

  // 3. Initialize Page Controller
  new PageController(appChatUI);

  console.log("Horizon Campus Assistance Portal initialized successfully.");
  console.log("💡 Tip: To connect a Python Flask backend in the future, set 'USE_LOCAL_ENGINE = false' in CampusBotService.");
});

/**
 * Global helper for inline card buttons (e.g. from the Admissions cards)
 * Opens the chatbot and asks the question instantly.
 */
function handleQuickQuestion(questionText) {
  if (appChatUI) {
    appChatUI.toggleChat(true);
    appChatUI.submitQuestion(questionText);
  }
}
