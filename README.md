
# Vibe Code Intelligence

See where AI made decisions. Know where your judgment matters. Get a plan to make it a real product.

## What this does

Evaluates your vibe-coded prototype against your product doc or prompt. Shows you what was built, what was missed, what decisions the AI made without telling you, and gives you a staged plan to turn it into a real product.

## What you need

- Python 3 (download at https://www.python.org/downloads/)
- An Anthropic API key (get one at https://console.anthropic.com/)
  - Free tier gives you $5 in credits to start
  - Each analysis costs roughly $0.05

## Setup (5 minutes)

**Step 1: Download this folder**

Click the green "Code" button above → "Download ZIP" → unzip to a folder on your computer.

**Step 2: Install dependencies**

Open Command Prompt (Windows) or Terminal (Mac) and navigate to the folder:

cd path/to/vibe-code-intelligence pip install flask flask-cors anthropic

If `pip` doesn't work, try `python -m pip install flask flask-cors anthropic`

**Step 3: Set your API key**

Windows:
set ANTHROPIC_API_KEY=your-key-here

Mac/Linux:
export ANTHROPIC_API_KEY=your-key-here

**Step 4: Run it**

python app.py

You should see:

Serving Flask app 'app'
Running on http://127.0.0.1:8080


**Step 5: Open in browser**

Go to http://localhost:8080

## How to use

1. Enter a project name (optional — helps track history)
2. Paste your product doc or vibe code prompt in the left box
3. Paste your generated codebase in the right box
4. Click "+ New evaluation"
5. Wait 30-60 seconds for the analysis

## Privacy

Your code and product doc are sent directly from your computer to Claude (Anthropic) for analysis. They are:
- **NOT sent to me** — I never see your inputs
- **NOT stored on any server I control**
- **NOT accessible to anyone else**
- **NOT used for AI training** (per Anthropic's API data policy)

Your evaluation history is stored in your browser only (localStorage) and never leaves your machine.

## Live demo

Don't want to set up locally? Try the hosted version at https://prototype-intelligence.onrender.com

Note: The hosted version runs through my server, so your inputs pass through Render. For sensitive/proprietary code, use the local setup above.

## Cost

Each analysis uses approximately 15,000 tokens (~$0.05 on the Anthropic API). The free tier gives you enough for ~100 analyses.

