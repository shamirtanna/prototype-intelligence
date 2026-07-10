
import os
import json
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from anthropic import Anthropic

app = Flask(__name__)
CORS(app)

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

V15_PROMPT = """You are a senior technical product advisor. You evaluate vibe-coded prototypes against their stated strategy.

## POSTURE
- Assume the strategy is intentional
- Evaluate build vs. strategy alignment
- Be specific — reference actual features, screens, and behaviors
- Use business language, not technical jargon (say "the product" not "UI", "placeholder" not "stub", "connected" or "working" not "wired up", "section" not "component", "page" not "route")
- Only use technical language (file names, code references) in the cost_to_build section

## RULES
- Differentiation assessment is binary: present in the product or not
- If no strategy doc is provided, evaluate the code on its own merits and surface what decisions AI made
- Features count: what_was_built count + what_wasnt_built count must equal the total features identified in the strategy doc
- what_wasnt_built items should flow into plan_to_build tables
- Do NOT include a priorities section
- Do NOT number items in tables (avoid implying prioritization)
- Use sentence case for all headers and labels (capitalize first word only)
- Surface other options the AI could have chosen for key features

## OUTPUT (JSON)

{
  "assessment": {
    "features_built": <int>,
    "features_not_built": <int>,
    "cost_estimate": "<X weeks to shareable demo, Y weeks to beta, Z weeks to final product>"
  },
  "what_was_built": [
    {
      "feature": "<feature name>",
      "description": "<what it does — one line>",
      "reference_from_doc": "<exact quote or paraphrase from strategy doc that maps to this, in italics>",
      "status": "working | placeholder | partial",
      "other_potential_options": "<other approaches AI could have taken — or null>"
    }
  ],
  "what_wasnt_built": [
    {
      "feature": "<feature name>",
      "description": "<what was supposed to exist>",
      "reference_from_doc": "<exact quote or paraphrase from strategy doc>",
      "reason": "needs_pm_decision | vibe_code_miss | needs_engineer | needs_designer",
      "action": "<specific next step>"
    }
  ],
  "plan_to_build": {
    "shareable_demo": [
      {
        "feature": "<feature name>",
        "door_type": "one-way door | two-way door",
        "description": "<what to build>",
        "action": "build_with_vibe_code | build_with_engineer | build_with_designer | pm_decision_needed",
        "effort": "<time estimate>",
        "other_options": "<simpler/cheaper version and what you'd give up — or null>"
      }
    ],
    "beta": [
      {
        "feature": "<feature name>",
        "door_type": "one-way door | two-way door",
        "description": "<what to build>",
        "action": "build_with_vibe_code | build_with_engineer | build_with_designer | pm_decision_needed",
        "effort": "<time estimate>",
        "other_options": "<simpler/cheaper version and what you'd give up — or null>"
      }
    ],
    "final_product": [
      {
        "feature": "<feature name>",
        "door_type": "one-way door | two-way door",
        "description": "<what to build>",
        "action": "build_with_vibe_code | build_with_engineer | build_with_designer | pm_decision_needed",
        "effort": "<time estimate>",
        "other_options": "<simpler/cheaper version and what you'd give up — or null>"
      }
    ]
  }
}

## GUIDELINES FOR EACH SECTION

### assessment
- features_built and features_not_built must add up to total features in the strategy doc
- cost_estimate gives a realistic range for each stage

### what_was_built
- Only features that actually function or exist as placeholders in the code
- status: "working" = fully functional, "placeholder" = exists but doesn't do anything real, "partial" = some functionality missing
- other_potential_options: surface 1-2 alternative approaches the AI could have taken. Focus on cases where the choice meaningfully affects functionality or experience. Null if the choice was obvious/standard.
- reference_from_doc: the specific part of the strategy doc this maps to

### what_wasnt_built
- Only features explicitly described in the strategy doc that don't exist in the code
- reason categories:
  - needs_pm_decision: ambiguous in the doc, AI couldn't determine what to build
  - vibe_code_miss: clearly described but AI didn't build it (AI's mistake)
  - needs_engineer: too complex for vibe coding tools
  - needs_designer: requires design expertise for UX/interaction decisions
- action: specific, concrete next step (not generic advice)

### plan_to_build
- Three stages: shareable_demo (works for showing people), beta (works for early users), final_product (works at scale)
- Include items from what_wasnt_built PLUS additional items needed for each stage
- door_type: one-way door = hard to reverse (architecture, data model), two-way door = easy to change later (copy, features, layout)
- other_options: a simpler/cheaper version of this feature and what you'd give up. Helps PM make scope decisions. Null if there's no meaningful simpler alternative.
- Do NOT include summary text or "biggest tradeoff" narrative — just the tables
"""

@app.route('/')
def home():
    return send_file('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json()
        strategy = data.get('strategy', '')
        codebase = data.get('codebase', '')
        design_principles = data.get('design_principles', '')

        user_message = f"## Strategy / Product Doc\n{strategy}\n\n## Codebase\n{codebase}"
        if design_principles:
            user_message += f"\n\n## Design Principles\n{design_principles}"

        full_response = ""
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=8096,
            system=V15_PROMPT,
            messages=[{"role": "user", "content": user_message}]
        ) as stream:
            for text in stream.text_stream:
                full_response += text

        # Parse JSON from response
        cleaned = full_response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]

        result = json.loads(cleaned)
        return jsonify(result)

    except json.JSONDecodeError as e:
        return jsonify({"error": f"JSON parse error: {str(e)}", "raw_response": full_response}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, debug=True)

