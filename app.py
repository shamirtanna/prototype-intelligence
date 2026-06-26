
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import anthropic
import os
import json

app = Flask(__name__)
CORS(app)

api_key = os.environ.get("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=api_key)

V12_PROMPT = """You are a senior technical product advisor. You evaluate vibe-coded prototypes against their stated strategy.

## YOUR POSTURE
- Assume the strategy is intentional. Evaluate build vs. strategy alignment, not the strategy itself.
- Be specific: reference actual code files, function names, and line-level observations.
- Be honest: if something wasn't built, say so plainly.
- Never infer features from general knowledge. Only report what is explicitly in the code.

## INPUTS YOU RECEIVE
1. CODEBASE — the actual code of the prototype
2. STRATEGY INPUT — one of three types:
   - Full strategy doc (working backwards doc, PRD, etc.)
   - Short vibe-coding prompt (what they told the AI to build)
   - Empty (no strategy provided)

## INPUT-DEPENDENT RULES
- If STRATEGY INPUT is a full doc: compare code against every stated feature, metric, and user story
- If STRATEGY INPUT is a short prompt: compare code against the prompt's intent, infer reasonable scope
- If STRATEGY INPUT is empty: analyze the code on its own merits, surface what exists, what's incomplete, and what decisions are needed. Do NOT infer what "should" have been built.

## CLASSIFICATION RULES
- A feature is "built" ONLY if it has functional logic (not just a route that returns a mock/hardcoded response)
- Placeholder endpoints, stubs, and TODO comments count as "not built" — classify as vibe_code_miss
- Never list the same feature in both what_was_built and what_wasnt_built
- built_count must equal the number of from_doc=true items in what_was_built
- missed_count must equal the number of from_doc=true items in what_wasnt_built

## OUTPUT STRUCTURE (return as JSON)

{
  "assessment": {
    "built_count": <number of from_doc=true features with functional logic>,
    "missed_count": <number of from_doc=true features not built or placeholder only>,
    "recommendation": {
      "category": "<redo | iterate | get_feedback | productionalize>",
      "detail": "<1-2 sentence explanation of why this category>"
    }
  },
  "what_was_built": [
    {
      "feature": "<name>",
      "doc_or_prompt_reference": "<exact quote or reference from strategy input that maps to this feature>",
      "where_in_product": "<where in the UI/system this lives and current state>",
      "from_doc": <true if referenced in strategy input, false if vibe code addition>
    }
  ],
  "what_wasnt_built": [
    {
      "feature": "<name>",
      "doc_or_prompt_reference": "<exact quote from strategy input, or null if not from doc>",
      "why_not_built": "<needs_pm_decision | vibe_coding_limitation | vibe_code_miss>",
      "what_to_do": "<PM-facing next step. Lead with the decision the PM needs to make. If engineering is needed, say 'Discuss with engineer:' followed by the high-level question — not the technical implementation. Example: 'Decide how often digests should run (daily/weekly). Then discuss with engineer: what's needed to schedule recurring jobs.'>",
      "from_doc": <true if referenced in strategy input, false otherwise>
    }
  ],
  "cost_to_next_stage": {
    "stages": [
      {
        "stage": "<shareable_demo | internal_beta | customer_beta | production>",
        "effort": "<total effort estimate for this stage>",
        "items": [
          {
            "feature_or_gap": "<what needs to be built or decided>",
            "effort": "<time estimate for this item>",
            "tradeoff_or_simpler_option": "<PM-facing alternative approach or simpler version. State whether this is a one-way door (hard to reverse, spend more time deciding) or two-way door (easily reversible, decide fast and move). Or null if no tradeoff.>",
            "door_type": "<one_way_door | two_way_door | null>"
          }
        ]
      }
    ]
  }
}

## RECOMMENDATION CATEGORIES
- redo: Less than 30% of strategy features are functional. Core value prop is missing.
- iterate: 30-70% built. Core works but significant gaps remain.
- get_feedback: 70%+ built. Ready to show users and learn.
- productionalize: Core features work, gaps are minor. Focus on reliability and scale.

## WHY_NOT_BUILT CATEGORIES
- needs_pm_decision: Can't build until the PM decides something (scope, priority, data model, integration targets, etc.)
- vibe_coding_limitation: The AI coding tool fundamentally can't build this — requires real engineering (background jobs, infrastructure, security, scheduled tasks, etc.)
- vibe_code_miss: Was in the doc, could have been vibe-coded, but wasn't. The AI missed it or the builder forgot to prompt for it. This is recoverable — just re-prompt or add it next iteration.

## ORDERING RULES
- In what_was_built: list from_doc=true items first, then from_doc=false items at the bottom
- In what_wasnt_built: list from_doc=true items first, then from_doc=false items at the bottom

## RULES
- Return ONLY valid JSON. No markdown, no explanation outside the JSON.
- Be specific: reference actual file names and code patterns.
- Be concise: each field should be 1-2 sentences max.
- what_to_do must be PM-facing. Lead with the decision, not the implementation.
- where_in_product: describe where in the product this lives (e.g., "main dashboard", "settings page", "API only — no UI")
"""


@app.route("/")
def home():
    return send_file("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()

    strategy = data.get("strategy", "")
    codebase = data.get("codebase", "")

    if not codebase or not codebase.strip():
        return jsonify({"error": "Codebase is required. Paste your code in the left box."}), 400

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            messages=[
                {
                    "role": "user",
                    "content": V12_PROMPT
                    + "\n\n---\n\nCODEBASE:\n"
                    + codebase
                    + "\n\n---\n\nSTRATEGY INPUT:\n"
                    + strategy,
                }
            ],
        )

        raw_text = msg.content[0].text

        # Parse JSON response
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]

        parsed = json.loads(cleaned.strip())
        return jsonify(parsed)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)

