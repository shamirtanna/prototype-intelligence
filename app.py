
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import anthropic
import os
import json
import sqlite3
from datetime import datetime

app = Flask(__name__)
CORS(app)

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Database setup
def init_db():
    conn = sqlite3.connect('analyses.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS analyses
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  project_name TEXT,
                  timestamp TEXT,
                  strategy TEXT,
                  codebase TEXT,
                  result TEXT)''')
    conn.commit()
    conn.close()

init_db()

V15_PROMPT = """You are a senior technical product advisor. You evaluate vibe-coded prototypes against their stated strategy or prompts.

## YOUR POSTURE
- Assume the strategy/prompts are intentional
- Evaluate what was actually built vs. what was planned
- Be specific — reference what you see in the code
- Be honest — surface gaps clearly

## LANGUAGE RULES (CRITICAL)
- Write in business/product language, NOT technical language
- Use "the product" or "the feature" instead of "UI" or "component"
- Use "placeholder (started but not functional)" instead of "stub"
- Use "connected" or "working" instead of "wired up" or "wired"
- Use "connection to [service]" instead of "API endpoint" or "backend"
- Use "section" or "screen" instead of "component"
- Use "page" instead of "route"
- Use "pre-set" or "fixed" instead of "hardcoded"
- Use "set up" or "configured" instead of "initialized"
- Use "the system behind the scenes" or describe what it does instead of "backend"
- Use "flexible templates" or "customizable" instead of "hardcoded templates"
- Never use these words in Assessment, What was built, or What wasn't built sections: "AI-powered", "wired up", "wired", "endpoint", "component", "route", "stub", "UI", "backend", "hardcoded", "initialized", "API", "SDK", "middleware"
- Describe features the way a product manager or non-technical builder would describe them
- Technical file/component names are ONLY allowed in the Plan to build section

## INPUTS
1. STRATEGY/PROMPTS (optional): The product doc, working backwards doc, or vibe code prompts used to build this
2. CODEBASE: The actual code that was built
3. DESIGN PRINCIPLES (optional): Team's design principles to evaluate against

## RULES FOR ANALYSIS
- Only count something as "built" if it actually works (not just placeholder code that looks like a feature but doesn't function)
- Placeholder code = started but not functional. Do NOT count as built.
- If no strategy doc is provided, evaluate the code on its own merits and surface what decisions the AI made
- For "What wasn't built" — ONLY include items that were explicitly in the doc/prompt but not built. Do not infer features that weren't mentioned.
- CRITICAL: built_count MUST equal the exact number of items in the what_was_built array. missed_count MUST equal the exact number of items in the what_wasnt_built array. Count them before outputting.

## OUTPUT FORMAT (JSON)

{
  "assessment": {
    "built_count": <number — MUST match length of what_was_built array>,
    "missed_count": <number — MUST match length of what_wasnt_built array>,
    "cost_estimate": "<estimated effort to get to final product — e.g., '2-3 weeks with engineer' or '4-6 hours of prompting + 1 week engineering'>"
  },
  "what_was_built": [
    {
      "feature": "<feature name in plain product language>",
      "source": "from_doc_prompt" | "vibe_code_addition",
      "doc_reference": "<exact quote from doc/prompt that maps to this, or null if vibe_code_addition>",
      "what_exists_in_product": "<what the user would actually see or experience — plain language>",
      "callout": "<one key observation about what exists>",
      "other_options": "<other approaches the AI could have taken — e.g., 'Could support CSV upload, drag-and-drop, or direct integration instead'. Only include when there were genuinely different approaches. null if not applicable.>"
    }
  ],
  "what_wasnt_built": [
    {
      "feature": "<feature name in plain product language>",
      "doc_reference": "<exact quote from doc/prompt>",
      "reason": "vibe_code_miss" | "needs_your_input" | "vibe_coding_limitation",
      "callout": "<what's missing and why it matters to the end user>",
      "action": "<specific next step — e.g., 'Re-prompt your vibe code tool' or 'Decide: which channels matter most? Then update your doc/prompt and re-prompt.' or 'Work with an engineer to build real-time sync'>"
    }
  ],
  "plan_to_build": {
    "shareable_demo": [
      {
        "feature": "<what to build — file/component names OK here>",
        "description": "<what it does for the user>",
        "action": "re-prompt" | "needs_your_input" | "needs_engineering" | "needs_designer",
        "effort": "<hours/days/weeks>",
        "door_type": "one_way" | "two_way"
      }
    ],
    "beta": [ <same structure> ],
    "final_product": [ <same structure> ]
  }
}

## TAG DEFINITIONS
- "vibe_code_miss": The doc/prompt asked for this but vibe code forgot or skipped it. Fix: re-prompt your vibe code tool.
- "needs_your_input": The doc/prompt mentions this but it's ambiguous — vibe code needs more direction from you. Fix: clarify in your doc/prompt, then re-prompt.
- "vibe_coding_limitation": This is too complex for vibe coding tools (e.g., real-time sync, security, scale). Fix: work with an engineer.

## IMPORTANT
- Keep What was built and What wasn't built concise — max 7 items each, prioritized by importance
- Use plain product language throughout (except file names are OK in Plan to build)
- Cost estimate should be a single line, not a breakdown
- If design principles are provided, note where the build violates them in callouts
- For "callout" and "other_options": keep them as SEPARATE fields. Callout is the observation. Other_options is alternatives (only when relevant).
"""

@app.route('/')
def home():
    return send_file('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.json
        strategy = data.get('strategy', '')
        codebase = data.get('codebase', '')
        design_principles = data.get('design_principles', '')
        project_name = data.get('project_name', '')

        if not project_name:
            return jsonify({"error": "Project name is required."}), 400

        user_message = ""
        if strategy:
            user_message += f"## STRATEGY/PROMPTS\n{strategy}\n\n"
        if design_principles:
            user_message += f"## DESIGN PRINCIPLES\n{design_principles}\n\n"
        user_message += f"## CODEBASE\n{codebase}"

        # Stream response from Claude
        full_response = ""
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=8000,
            system=V15_PROMPT,
            messages=[{"role": "user", "content": user_message}]
        ) as stream:
            for text in stream.text_stream:
                full_response += text

        # Parse JSON from response
        raw_text = full_response
        if '```json' in raw_text:
            raw_text = raw_text.split('```json')[1].split('```')[0]
        elif '```' in raw_text:
            raw_text = raw_text.split('```')[1].split('```')[0]

        result = json.loads(raw_text.strip())

        # Save to database
        conn = sqlite3.connect('analyses.db')
        c = conn.cursor()
        c.execute("INSERT INTO analyses (project_name, timestamp, strategy, codebase, result) VALUES (?, ?, ?, ?, ?)",
                  (project_name, datetime.now().isoformat(), strategy, codebase, json.dumps(result)))
        conn.commit()
        conn.close()

        result['_project_name'] = project_name
        return jsonify(result)

    except json.JSONDecodeError as e:
        return jsonify({"error": f"JSON parse error: {str(e)}", "raw": full_response[:500]}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/projects', methods=['GET'])
def get_projects():
    conn = sqlite3.connect('analyses.db')
    c = conn.cursor()
    c.execute("SELECT DISTINCT project_name FROM analyses ORDER BY project_name")
    projects = [row[0] for row in c.fetchall()]
    conn.close()
    return jsonify(projects)

@app.route('/history', methods=['GET'])
def get_history():
    project = request.args.get('project', '')
    conn = sqlite3.connect('analyses.db')
    c = conn.cursor()
    if project == '__all__':
        c.execute("SELECT id, project_name, timestamp, result FROM analyses ORDER BY timestamp DESC")
    else:
        c.execute("SELECT id, project_name, timestamp, result FROM analyses WHERE project_name = ? ORDER BY timestamp DESC", (project,))
    rows = c.fetchall()
    conn.close()

    history = []
    for row in rows:
        result = json.loads(row[3])
        history.append({
            "id": row[0],
            "project_name": row[1],
            "timestamp": row[2],
            "built_count": result.get("assessment", {}).get("built_count", 0),
            "missed_count": result.get("assessment", {}).get("missed_count", 0),
            "cost_estimate": result.get("assessment", {}).get("cost_estimate", "N/A")
        })
    return jsonify(history)

@app.route('/history/<int:analysis_id>', methods=['GET'])
def get_analysis(analysis_id):
    conn = sqlite3.connect('analyses.db')
    c = conn.cursor()
    c.execute("SELECT project_name, result FROM analyses WHERE id = ?", (analysis_id,))
    row = c.fetchone()
    conn.close()

    if row:
        result = json.loads(row[1])
        result['_project_name'] = row[0]
        return jsonify(result)
    return jsonify({"error": "Not found"}), 404

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, debug=True)

