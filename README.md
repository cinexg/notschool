# 🚀 Notschool OS 

**An Autonomous, Multi-Agent Learning Architect**
*Built for the Google Gen AI Academy APAC 2026 Hackathon (Track 1: Agentic AI)*

## 📖 The Vision
Most AI tools just answer questions. **Notschool OS** builds complete, actionable learning systems. 

A user uploads a photo of a textbook index or handwritten syllabus. Our system uses Gemini's multimodal reasoning to read it, breaks it down into a structured daily curriculum, automatically finds the best YouTube tutorials for each topic, and schedules the study sessions (and a final exam) directly into the user's Google Calendar. 

### Hackathon Rubric Alignment 🏆
- [x] **Primary Agent + Sub-Agents:** LangGraph orchestrates the Architect, Librarian, and Scheduler agents.
- [x] **Store/Retrieve Structured Data:** SQLite implementation tracking course progression.
- [x] **Integrate Tools via MCP:** YouTube API (Content) & Google Calendar API (Scheduling).
- [x] **Multi-Step Workflows:** Upload ➡️ Scan ➡️ Draft ➡️ Save ➡️ Schedule.
- [x] **API-based System:** Core logic operates as backend Python functions separate from the frontend.

---

## 🛠️ Tech Stack
- **Orchestrator:** `langgraph`
- **LLM Engine:** `gemini-1.5-pro` (via `google-genai` SDK)
- **Frontend UI:** `streamlit` 
- **Database:** `sqlite3`
- **External Tools:** Google Calendar API, YouTube Data API v3

---

## 🧠 System Architecture (The "Loop")

We utilize a LangGraph State machine. The `NotschoolState` dictionary is passed between agents:

1. **The Input:** User drops an image into the UI with a timeframe constraint.
2. **The Architect (Gemini Vision):** Scans the image, validates the request, and outputs a strict JSON object mapping days to specific topics.
3. **The Librarian (Tool Calling):** Reads the JSON, hits the YouTube API, and appends actual Video URLs to the curriculum data.
4. **The Database Agent:** Saves the complete generated syllabus to local SQLite.
5. **The Scheduler (Tool Calling):** Hits the Google Calendar API, creates calendar events for each study day, and schedules a "Final Exam" 24 hours after completion.

---

## 💻 Quick Start & Setup

### Prerequisites
You will need API keys for:
1. Google AI Studio (Gemini)
2. YouTube Data API v3 (Google Cloud Console)
3. Google Calendar API (OAuth 2.0 Client ID)

### Installation

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/your-username/notschool-os.git](https://github.com/your-username/notschool-os.git)
   cd notschool-os
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Environment Variables:**
   Create a `.env` file in the root directory and add your keys:
   ```env
   GEMINI_API_KEY="your_gemini_key_here"
   YOUTUBE_API_KEY="your_youtube_key_here"
   # Ensure your Calendar OAuth JSON file is in the root directory
   ```

4. **Run the Application:**
   ```bash
   streamlit run ui/app.py
   ```

---

## 👥 Division of Labor

- **Lead AI Engineer [Name]:** LangGraph state machine, Gemini SDK implementation, JSON prompting.
- **API Integration Lead [Name]:** YouTube/Calendar API tool functions.
- **Frontend/DB Lead [Name]:** Streamlit UI, custom CSS, and SQLite setup.

---
*Developed by Team [Your Team Name] - April 2026*
