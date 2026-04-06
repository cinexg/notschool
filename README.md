# Notschool

**Multi-Agent Learning Architect**
*Built for the Google Gen AI Academy APAC 2026 Hackathon (Track 1: Agentic AI)*

## Overview
Most AI educational tools act as simple question-answering bots. Notschool OS is designed to build complete, actionable learning systems. 

When a user uploads a photo of a textbook index or a handwritten syllabus, the system uses multimodal reasoning to read it. It then breaks the content down into a daily curriculum, finds the best YouTube tutorials for each topic, and schedules the study sessions directly into the user's Google Calendar.

### Hackathon Alignment
- [x] **Primary Agent + Sub-Agents:** LangGraph orchestrates the Architect, Librarian, and Scheduler agents.
- [x] **Store/Retrieve Structured Data:** SQLite tracks course progression and user data.
- [x] **Integrate Tools via MCP:** Utilizes YouTube API (Content) and Google Calendar API (Scheduling).
- [x] **Multi-Step Workflows:** Upload -> Scan -> Draft -> Save -> Schedule.
- [x] **API-based System:** Core logic operates as backend Python functions.

---

## Tech Stack
- **Orchestrator:** `langgraph`
- **LLM Engine:** `gemini-1.5-pro` (via `google-genai` SDK)
- **Frontend UI:** `streamlit` 
- **Database:** `sqlite3`
- **External Tools:** Google Calendar API, YouTube Data API v3

---

## System Architecture

We use a LangGraph state machine to handle the workflow. Information is passed between agents using a shared state dictionary:

1. **Input:** The user uploads an image with a specific timeframe constraint.
2. **The Architect (Vision Agent):** Scans the image, validates the request, and outputs a JSON object mapping the days to specific topics.
3. **The Librarian (Tool Agent):** Reads the JSON, searches the YouTube API, and appends relevant tutorial URLs to the curriculum.
4. **The Database Agent:** Saves the complete generated syllabus to a local SQLite database.
5. **The Scheduler (Tool Agent):** Connects to the Google Calendar API, creates events for each study day, and schedules a final exam 24 hours after completion.

---

## Setup Instructions

### Prerequisites
You will need API keys for the following services:
1. Google AI Studio (Gemini)
2. YouTube Data API v3 
3. Google Calendar API (OAuth 2.0 Client ID)

### Installation

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/cinexg/notschool-os.git](https://github.com/cinexg/notschool-os.git)
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
   # Place your Calendar OAuth JSON file in the root directory
   ```

4. **Run the Application:**
   ```bash
   streamlit run ui/app.py
   ```

---

## Team Roles

- **Lead AI Engineer [Name]:** Manages the LangGraph state machine, Gemini SDK implementation, and agent prompts.
- **API Integration Lead [Name]:** Handles YouTube and Calendar API connections and tool functions.
- **Frontend & Database Lead [Name]:** Develops the Streamlit UI and sets up the SQLite database schema.
