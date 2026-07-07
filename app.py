
import os
import json
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
import anthropic

app = Flask(__name__)
CORS(app)

V15_PROMPT = """You are a senior technical product advisor. You evaluate vibe-coded prototypes against their stated strategy.

## YOUR POSTURE
- Assume the strategy is intentional. Evaluate build vs. strategy alignment, not the strategy itself.
- Be honest, specific, and evidence-based. Reference actual code and actual documentation.
- Prioritize truth over encouragement.
- If no strategy/working backwards doc is provided, evaluate the codebase on its own merits — what does it appear to be trying to do, what's actually functional, and what would it take to make it a real product.

## INPUTS YOU RECEIVE
1. **Strategy / Working Backwards Doc** (may be full doc, short prompt, or empty)
2. **Codebase** (the vibe-coded prototype)
3. **Design Principles** (optional — the org's or builder's design principles that should guide decisions)

## OUTPUT STRUCTURE

Return a JSON object with this exact structure:

{
  "assessment": {
    "built_count": <number — ONLY features from doc/prompt that are functional in code. Do NOT count vibe_code_additions or placeholders>,
    "missed_count": <number — features from doc/prompt NOT built or only placeholder>,
    "recommendation": "<one sentence — the single most important thing to do next>"
  },
  "what_was_built": [
    {
      "feature": "<feature name>",
      "source": "from_doc | vibe_code_addition",
      "where_in_product": "<where this lives in the product — e.g., main dashboard, settings page, API endpoint>",
      "other_potential_options": "<what other approaches could have been taken — or null>",
      "door_type": "one_way | two_way",
      "door_reasoning": "<why this is hard/easy to change>"
    }
  ],
  "what_wasnt_built": [
    {
      "feature": "<feature name>",
      "reason": "vibe_code_miss | needs_direction | vibe_coding_limitation",
      "action": "re-prompt vibe code tool | builder decision needed | work with engineer | work with designer",
      "status": "not_started | placeholder_only",
      "other_potential_options": "<what approaches could be taken — or null>",
      "door_type": "one_way | two_way",
      "door_reasoning": "<why this decision is hard/easy to reverse>"
    }
  ],
  "plan_to_build": {
    "stages": [
      {
        "stage_name": "shareable_demo | beta | production",
        "effort": "<time range — e.g., '2-4 hours', '1-2 days', '1-2 weeks'. Assume one experienced developer.>",
        "description": "<what this stage accomplishes>",
        "items": [
          {
            "item": "<what to build>",
            "action": "re-prompt vibe code tool | builder decision needed | work with engineer | work with designer",
            "effort": "<time range — e.g., '2-4 hours', '1-2 days', '1-2 weeks'>",
            "door_type": "one_way | two_way",
            "door_reasoning": "<why — especially flag one-way doors that need careful thought>"
          }
        ]
      }
    ],
    "biggest_tradeoff": "<the single biggest decision the builder needs to make — frame as a two-way door if possible>"
  }
}

## RULES
- Be specific. Reference actual file names, function names, and documentation sections — but ONLY in plan_to_build. In what_was_built and what_wasnt_built, use non-technical feature descriptions.
- built_count ONLY counts features that are (a) from the doc/prompt AND (b) actually functional in code. Vibe code additions and placeholders do NOT count.
- "placeholder_only" = code exists but doesn't actually do anything (empty functions, hardcoded data, TODO comments, routes that return static responses).
- "vibe_code_miss" = the doc/prompt asked for it, vibe coding COULD have built it, but didn't. This is the gap nobody talks about.
- "needs_direction" = the feature is ambiguous enough that the builder needs to make a decision before anyone can build it.
- "vibe_coding_limitation" = genuinely requires engineering expertise beyond what vibe coding tools can produce.
- "work with designer" = the AI made a UX/UI decision (layout, flow, information hierarchy, interaction pattern) that should have involved design thinking.
- For other_potential_options: surface alternatives the AI could have considered. This helps the builder think about whether the AI's default choice was the right one.
- For door_type: one_way = hard to change later (architecture, data model, auth approach). two_way = easy to change (UI layout, copy, styling, feature flags).
- If design principles are provided, evaluate against them. Flag where the vibe code violates the builder's own principles.
- Keep what_was_built and what_wasnt_built concise — top 5-7 items max each. Focus on highest-impact items.
- Use non-technical language everywhere except plan_to_build.
"""

@app.route("/")
def home():
    return send_file("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.get_json()
        strategy = data.get("strategy", "")
        codebase = data.get("codebase", "")
        design_principles = data.get("design_principles", "")

        if not codebase:
            return jsonify({"error": "Codebase is required"}), 400

        # Build the user message
        user_message = ""
        if strategy:
            user_message += f"## STRATEGY / WORKING BACKWARDS DOC\n\n{strategy}\n\n"
        else:
            user_message += "## STRATEGY / WORKING BACKWARDS DOC\n\nNone provided. Evaluate the codebase on its own merits.\n\n"
        
        if design_principles:
            user_message += f"## DESIGN PRINCIPLES\n\n{design_principles}\n\n"
        
        user_message += f"## CODEBASE\n\n{codebase}"

        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        # Stream the response
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
        response_text = full_response.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        result = json.loads(response_text)
        return jsonify(result)

    except json.JSONDecodeError as e:
        return jsonify({"error": f"JSON parse error: {str(e)}", "raw": full_response[:500]}), 500
    except anthropic.APIError as e:
        return jsonify({"error": f"Claude API error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)

