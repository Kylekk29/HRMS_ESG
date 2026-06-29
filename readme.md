# 🧑‍💼 AI-HR Bridge Platform

**An AI-powered Human Resources Management System**

> What if your HR software could *read resumes, evaluate interviews, and chat with you about any employee* — all powered by AI? That's what this project does.

---

## 🎯 What Is This?

This is a **complete HR management system** that combines traditional HR features (employee records, attendance, leave, payroll) with **smart AI capabilities** (resume screening, interview analysis, employee insights).

It was built as a university project to demonstrate how AI can be integrated into everyday business tools.

### 🤖 AI Features — What Makes This Special

| Feature | What It Does | How It Helps |
|---------|-------------|-------------|
| **Smart Resume Screening** | Upload up to 25 resumes, AI scores each candidate across 5 dimensions (skills, experience, education, culture fit, growth potential) | Save hours of manual resume review — AI ranks candidates and suggests interview questions |
| **Interview Analysis** | Paste an interview transcript, AI evaluates the candidate across 7 dimensions with scores and key quotes | Get an objective second opinion on interview performance |
| **Employee AI Chat** | Ask questions about any employee — "Is EMP001 at risk of leaving?" "What skills does Sarah need?" | AI pulls from all employee data (records, resumes, attendance, KPI) to give you answers |
| **Skill Gap Analysis** | AI extracts skills from resumes and identifies what's missing vs. a target role | Know exactly what training each employee needs |
| **Salary Adjustment Suggestions** | AI recommends raise amounts based on KPI scores and tenure | Fair, data-driven compensation decisions |

### 📋 Traditional HR Features

| Feature | Description |
|---------|-------------|
| **Employee Management** | Add, edit, search employees with full profiles (position, department, salary, emergency contacts) |
| **Attendance Tracking** | Check-in/check-out with automatic late detection, overtime calculation, half-day detection |
| **Leave Management** | Submit leave requests, approve/reject workflow, automatic balance tracking (complies with Taiwan Labour Standards Act) |
| **Payroll Calculation** | Automatic monthly salary computation: base + overtime + bonus − absent days − late penalties − leave deductions |
| **Dashboard** | Real-time overview: total employees, attendance status, pending approvals, payroll estimate |

---

## 🏗️ How It Works

### System Overview

```
┌─────────────────────────────────────────────┐
│          Web Browser (Frontend)              │
│    Single-page app with 14 sections          │
│    No installation needed — just open it!    │
└──────────────────┬──────────────────────────┘
                   │ HTTP requests
┌──────────────────▼──────────────────────────┐
│        Python Backend (FastAPI)              │
│    Handles all data + AI operations          │
│    86 API endpoints                          │
└──────────────────┬──────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
┌───▼───┐   ┌────▼────┐   ┌────▼────┐
│ HRMS  │   │  AI     │   │ Vector  │
│ Data  │   │ Engine  │   │ Search  │
│(JSON) │   │(DeepSeek│   │ (FAISS) │
└───────┘   │   API)  │   └─────────┘
            └─────────┘
```

### The AI Pipeline — How Resume Screening Works

1. You upload resumes (PDF/DOCX/TXT) and type a job description
2. The system reads each resume and breaks it into searchable chunks
3. It searches through these chunks + your company culture documents
4. All this context goes to the AI, which evaluates each candidate
5. You get: scores, strengths, weaknesses, hiring risks, and interview questions

---

## 🚀 Getting Started — How to Run It

### What You Need

| Requirement | Details |
|------------|---------|
| **Python** | Version 3.9 or newer (3.12 recommended) |
| **Computer** | 4GB RAM minimum, 8GB recommended |
| **Disk space** | ~2GB free (for AI model download) |
| **API Key** | A DeepSeek API key — [get one free here](https://platform.deepseek.com) |
| **Internet** | Needed for AI features and first-time model download |

### Step-by-Step Installation

#### Step 1: Download the Code

```bash
git clone https://github.com/Kylekk29/HRMS_ESG.git
cd HRMS_ESG
```

#### Step 2: Set Up Python Environment

```bash
# Create a virtual environment (keeps things clean)
python -m venv venv

# Activate it:
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

#### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

> ⏱️ This takes a few minutes — it's downloading the libraries the project needs.

#### Step 4: Configure Your API Key

```bash
# Create your config file from the template:
# Windows:
copy .env.example .env
# Mac/Linux:
cp .env.example .env
```

Then open `.env` in any text editor and replace `sk-your-deepseek-api-key-here` with your actual DeepSeek API key.

> 🔑 **Where to get the key**: Go to [platform.deepseek.com](https://platform.deepseek.com), sign up, and create an API key. DeepSeek offers free trial credits for new accounts.

#### Step 5: Start the Application

```bash
python main_api.py
```

> ⏱️ First run takes longer because it downloads the embedding model (~120MB). Subsequent runs start in seconds.

#### Step 6: Open in Browser

Go to: **http://127.0.0.1:8000**

🎉 That's it! You should see the dashboard.

### Quick Verification

```bash
# Test that the AI connection works:
python test_ai_api.py --quick
```

---

## 📁 Project Structure — What's in the Code

```
HRMS_ESG/
├── main_api.py           ← The main server (starts everything)
├── index.html            ← The entire frontend (one file!)
├── config.py             ← Settings and paths
├── requirements.txt      ← Python packages needed
├── prompts.json          ← AI prompt templates
├── .env.example          ← API key template (copy to .env)
│
├── hrms_manager.py       ← Employee, attendance, leave logic
├── payroll_manager.py    ← Salary calculation engine
├── task_router.py        ← Coordinates AI workflows
├── model_provider.py     ← Talks to the DeepSeek AI API
├── embedding_mgr.py      ← Turns documents into searchable vectors
├── version_manager.py    ← Tracks document versions
├── development_manager.py ← Skill extraction and training recommendations
│
├── sample_data/          ← Sample resumes & interview transcripts for testing
├── test_ai_api.py        ← AI connection test script
└ LICENSE               ← Apache 2.0 license
```

> 💡 **Key insight**: The frontend is a single `index.html` file (no React, no Vue, no build step). Just vanilla JavaScript + CSS. This keeps things simple and portable.

---

## 🔧 AI Configuration — DeepSeek API

### Why DeepSeek?

DeepSeek is a Chinese AI company that offers powerful language models at very affordable prices. It's OpenAI-compatible, so the code uses the standard OpenAI API format.

- **DeepSeek Chat** (`deepseek-chat`): Used for most AI tasks — fast and cost-effective
- **DeepSeek Reasoner** (`deepseek-reasoner`): Used when deeper reasoning is needed

### API Cost Estimate

| Feature | Approximate Cost per Use |
|---------|------------------------|
| Resume screening (10 resumes) | ~$0.01–0.05 |
| Interview analysis | ~$0.01–0.02 |
| Employee chat question | ~$0.005–0.01 |
| Skill extraction | ~$0.005 |

> 💰 Very affordable for a university project! DeepSeek offers free trial credits.

### If You Want to Use a Different AI Provider

The system is designed to work with any OpenAI-compatible API. Edit `.env`:

```env
BASE_URL=https://api.openai.com/v1     # or any compatible endpoint
API_KEY=sk-your-key-here                # your provider's key
AI_PROVIDER=openai                       # or custom name
```

---

## 📊 Feature Walkthrough

### 1. Dashboard

The main page shows real-time stats:
- Total / active / on leave / terminated employees
- Today's attendance breakdown
- Pending leave approvals
- Monthly payroll estimate
- Department summary

### 2. Resume Screening (AI Feature)

**How to use:**
1. Go to the **CV Screening** section
2. Type or paste a **job description** (e.g., "Senior Python Developer, 5+ years...")
3. **Drag and drop** resume files (PDF, DOCX, or TXT — up to 25 files)
4. Optionally adjust the **scoring weights** with the sliders (default: Skills 30%, Experience 25%, Education 10%, Culture Fit 15%, Growth Potential 20%)
5. Click **Run Screening**
6. Wait ~15–30 seconds — AI evaluates each candidate
7. See ranked results with scores, analysis, and suggested interview questions

**Try it with sample data:** Use the resumes in `sample_data/resumes/` and the sample job description in `sample_data/README.md`.

### 3. Company Culture Index (AI Feature)

**How to use:**
1. Go to **Company Culture** section
2. Upload your company handbook, values document, or policy PDF
3. The system indexes it and uses it during resume screening for culture-fit scoring

### 4. Interview Analysis (AI Feature)

**How to use:**
1. Go to **Interview Assist** section
2. Paste the **job description**
3. Paste the **interview transcript** (the actual conversation)
4. Optionally specify **competency requirements**
5. Click **Analyze**
6. Get a 7-dimension evaluation with scores, key quotes, red flags, and hiring recommendation

**Try it:** Use the sample transcripts in `sample_data/interviews/`.

### 5. Employee AI Chat (AI Feature)

**How to use:**
1. Go to **Employee Chat** section
2. Select an employee from the dropdown
3. Ask any question: "What are their strengths?" "Are they at risk?" "What training do they need?"
4. AI answers using *all* available data: HRMS records, attendance, KPI, leave history, and uploaded documents
5. Quick actions: **Risk Check**, **Skills Review**, **Attendance Check**

### 6. Employee Management

- Add/edit/delete employees with full profiles
- Track: position, department, salary, employment type, hire date, status
- Emergency contacts, KPI entries, notes

### 7. Attendance

- **Check In**: Records arrival time, auto-detects late (>9:30 AM)
- **Check Out**: Calculates work hours, detects overtime (>8h) and half-days (<4h)
- View daily summary or monthly history per employee

### 8. Leave Management

- **5 leave types**: Annual, Sick, Personal, Maternity, Special
- Automatic balance tracking with tenure-based annual leave (Taiwan Labour Standards Act)
- Submit → Approve/Reject workflow
- Date overlap detection

### 9. Payroll

- Automatic monthly calculation with all adjustments
- **Formula**: Base + Overtime + Bonus − Absent days − Late penalties − Leave deductions (sick leave exempt)
- Payslip generation
- Department-level aggregation
- **AI salary adjustment suggestions** based on KPI + tenure

---

## 🧪 Testing with Sample Data

The project includes sample data so you can try all features immediately:

### Sample Resumes
10 fictional resumes in `sample_data/resumes/` with varying skill levels:
- **Strong candidates**: Zhang Wei (Senior Python), Emily Chen (Data Scientist)
- **Partial matches**: Michael Wong (DevOps), Sarah Liu (Frontend)
- **Weak candidates**: David Chan (Junior)

### Sample Interview Transcripts
2 transcripts in `sample_data/interviews/`:
- Zhang Wei: strong technical answers, leadership examples
- David Chan: vague answers, lacks depth

### Sample Job Description
```
Senior Python Developer
5+ years experience
Required: Python, FastAPI or Django, PostgreSQL, Docker, AWS
Preferred: Kafka, Kubernetes, Team leadership, Microservices architecture
```

---

## ⚠️ Important Notes

### Security
- **Never commit your `.env` file** — it contains your API key. The `.gitignore` file prevents this.
- The `.env.example` file is safe to share — it only has placeholder values.

### Data Storage
- All HR data is stored as **JSON files** (no database server needed)
- AI vector data is stored as **FAISS indexes** (binary files)
- Data is created at runtime in the `data/` folder — not included in the repo
- First run creates all necessary folders automatically

### Embedding Model
- The `paraphrase-multilingual-MiniLM-L12-v2` model (~120MB) downloads automatically on first use
- It supports **English and Chinese** text
- Stored locally in `AImodels/embedding_model/` (not in repo — auto-downloaded)

### Performance Expectations
| What | How Long |
|------|----------|
| Starting the server | 5–10 seconds (first run: ~30s for model download) |
| Screening 10 resumes | 15–30 seconds |
| Screening 25 resumes | 30–60 seconds |
| Employee chat question | 2–5 seconds |
| Interview analysis | 8–15 seconds |
| Payroll calculation | Instant (<1 second) |

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---------|----------|
| "API key not found" | Make sure `.env` file exists with your real API key |
| "Command not found: python" | Install Python 3.9+ from [python.org](https://python.org) |
| Slow first startup | Normal — downloading the embedding model (~120MB) |
| AI features return errors | Check your DeepSeek API key and account credits |
| "Module not found" errors | Run `pip install -r requirements.txt` inside the activated venv |
| FAISS index errors | Re-upload the document — the system rebuilds indexes automatically |
| Page doesn't load | Make sure `main_api.py` is running, then go to http://127.0.0.1:8000 |

---

## 📚 Technical Details (For the Curious)

<details>
<summary>Click to expand technical architecture details</summary>

### Tech Stack
- **Backend**: Python + FastAPI + Uvicorn
- **AI**: DeepSeek API via LangChain (OpenAI-compatible)
- **Embeddings**: HuggingFace sentence-transformers → FAISS vector database
- **Frontend**: Vanilla JavaScript + CSS variables + Chart.js
- **Storage**: JSON files for HR data, FAISS binary indexes for AI search

### Key Design Decisions
1. **Single HTML file frontend** — No build tools, no framework overhead, easy to modify
2. **JSON file storage** — No database server needed, perfect for demo/academic use
3. **DeepSeek over OpenAI** — 10-100x cheaper, Chinese language support, same API format
4. **Local embedding model** — No external embedding API calls, multilingual support
5. **Version-controlled vectors** — SHA-256 hashing ensures identical documents reuse existing indexes

### API Endpoints (86 total)
The backend provides 86 REST API endpoints covering all features. See the full list in the source code (`main_api.py`).

</details>

---

## 📄 License

Apache License 2.0 — See [LICENSE](LICENSE) file.

---

**Version**: 4.1  
**Built by**: Kyle  
**University Project**: AI + HRMS Integration Demonstration