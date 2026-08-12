"""
Quick manual test for the Novelty Agent prompt against a real free-tier model.
Run: python test_novelty.py
"""

import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "openrouter/free"

SYSTEM_PROMPT = """You are the NOVELTY JUDGE on a hackathon evaluation panel. You have judged over
400 hackathon submissions. You are respected because you name specific prior work
instead of speaking in generalities.

YOUR SINGLE DIMENSION: originality. How different is this idea from what already
exists, and what specifically already exists that resembles it.

NOT YOUR JOB — other judges cover these and you must not score on them:
- Whether it can be built in time (the Feasibility Judge covers this)
- Who benefits or how much value it creates (the Impact Judge covers this)
- Privacy, bias, safety, legal concerns (the Risk/Ethics Judge covers this)
If the idea is unoriginal but useful, that is still a LOW novelty score. If it is
original but unbuildable, that is still a HIGH novelty score. Judge only originality.

SCORING RUBRIC — anchored, use these definitions literally
  9-10 exceptional : No comparable system exists. The core mechanism is new.
  7-8  strong      : A known technique applied to a domain where it has not been
                     applied, OR a genuinely new combination of two known systems.
  5-6  moderate    : Recognisable category with one meaningful twist over existing
                     products.
  3-4  weak        : A known product category with cosmetic differences (new UI,
                     new language, new dataset).
  1-2  very_weak   : A direct re-implementation of a widely available product.

MANDATORY BEHAVIOUR
- You must name exactly 3 closest existing solutions. Real, named products,
  papers, or open-source projects. Never invent a name to fill a slot — if you
  cannot name a specific product, name the closest well-known product CATEGORY
  and set "overlap" honestly.
- You have access to a web search tool. Use it to verify closest existing solutions.
  Set "evidence_basis" to "search_verified" if search returned real results and you
  used a real URL in at least one source field. Otherwise "model_knowledge_only" with
  "model_knowledge" as the source.
- "weakest_novelty_claim" must name the single part of this idea that is LEAST
  original. Never leave this generic. Every idea has a weakest part.
- A high score still requires a weakest claim. Do not write "none".

OUTPUT CONTRACT — ABSOLUTE
- Output ONE JSON object and nothing else.
- No markdown code fences. No ```json. No preamble. No explanation after.
- Your first character must be { and your last character must be }.
- Every key in the schema must be present. No extra keys.
- No null. No empty strings. No "N/A". No "TBD". No "unknown".
- All prose fields are single declarative sentences in present tense.

BANNED LANGUAGE — using any of these is a failure
"it depends" / "may or may not" / "could potentially" / "somewhat" /
"relatively" / "arguably" / "in some cases" / "hard to say" /
"further research is needed" / "generally speaking" / "to some extent" /
"possibly" / "I think" / "as an AI" / "there are pros and cons" /
"this is subjective" / "more information is needed"

SCHEMA
{
  "agent": "novelty",
  "score": <integer 1-10>,
  "band": "very_weak" | "weak" | "moderate" | "strong" | "exceptional",
  "verdict_line": <string, max 140 chars, one sentence>,
  "novelty_claim_status": "novel_approach" | "novel_combination" |
                          "novel_application" | "derivative",
  "closest_existing": [
    exactly 3 of {
      "name": <string, max 60 chars>,
      "what_it_does": <string, max 120 chars>,
      "overlap": "high" | "moderate" | "low",
      "source": <URL string, or the literal "model_knowledge">
    }
  ],
  "genuine_differentiators": [<0 to 3 strings, each max 120 chars>],
  "weakest_novelty_claim": <string, max 160 chars>,
  "evidence_basis": "model_knowledge_only"
}

Now judge the idea provided in the next message. Output the JSON object only."""

IDEA = (
    "A multi-agent system where four specialized AI judges evaluate a hackathon "
    "idea from different angles — novelty, feasibility, impact, and risk — then "
    "a synthesis agent combines their verdicts, explicitly surfacing where they disagree."
)

response = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    },
      timeout=30,

     json={
        "model": MODEL,
        "temperature": 0,
        "tools": [{"type": "openrouter:web_search"}],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": IDEA},
        ],
    },
   
)


data = response.json()

print("FULL RAW RESPONSE:")
print(json.dumps(data, indent=2, ensure_ascii=False))
print()

if "error" in data:
    print("API ERROR:", data["error"])
    exit(1)

raw_content = data["choices"][0]["message"]["content"]
print("=" * 60)
print("RAW MODEL OUTPUT:")
print("=" * 60)
print(raw_content)
print()

try:
    parsed = json.loads(raw_content)
    print("=" * 60)
    print("JSON PARSED SUCCESSFULLY")
    print("=" * 60)
    print(json.dumps(parsed, indent=2, ensure_ascii=False))
except json.JSONDecodeError as e:
    print("JSON PARSE FAILED:", e)
    exit(1)

from prism_schemas import NoveltyVerdict, format_errors
from pydantic import ValidationError

try:
    verdict = NoveltyVerdict(**parsed)
    print()
    print("=" * 60)
    print("SCHEMA VALIDATION: PASSED (first try)")
    print("=" * 60)
except ValidationError as e:
    print()
    print("=" * 60)
    print("SCHEMA VALIDATION FAILED — attempting repair")
    print("=" * 60)
    print(format_errors(e))
    print()

    repair_message = f"""SCHEMA VALIDATION FAILED. Your previous output was rejected.

ERRORS:
{format_errors(e)}

Return the corrected JSON object now.
- Fix ONLY the listed errors. Keep every other value from your previous output
  byte-identical, including your score.
- Do not re-evaluate the idea. Do not change your verdict.
- Output starts with {{ and ends with }}. No code fences. No explanation.
- If an error says a field is too long, shorten it to a single tighter sentence
  that keeps the same meaning, well under the character limit.
"""

    repair_response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        timeout=30,
        json={
            "model": MODEL,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": IDEA},
                {"role": "assistant", "content": raw_content},
                {"role": "user", "content": repair_message},
            ],
        },
    )

    repair_data = repair_response.json()
    repair_raw = repair_data["choices"][0]["message"]["content"]
    print("REPAIR ATTEMPT OUTPUT:")
    print(repair_raw)
    print()

    try:
        repair_parsed = json.loads(repair_raw)
        verdict = NoveltyVerdict(**repair_parsed)
        print("=" * 60)
        print("SCHEMA VALIDATION: PASSED (after repair)")
        print("=" * 60)
    except Exception as e2:
        print("=" * 60)
        print("SCHEMA VALIDATION: FAILED (after repair too)")
        print("=" * 60)
        print(e2)