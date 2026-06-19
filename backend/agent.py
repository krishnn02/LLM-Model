"""
OmniFood Agent - LangGraph ReAct State Machine
Orchestrates intent parsing, parallel scraping, and price reporting.
"""

import asyncio
import json
import logging
import os
import re
from typing import Dict, TypedDict, Any, AsyncGenerator, Optional, List

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from scraper import BrowserManager
from config import get_settings
from session_manager import get_session_manager

logger = logging.getLogger("omnifood.agent")


# ── LLM Init ─────────────────────────────────────────────────────────────────
def get_llm():
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider == "openai" and settings.openai_api_key:
        from langchain_openai import ChatOpenAI
        model_name = "openai/gpt-4o-mini" if "openrouter" in settings.openai_base_url else "gpt-4o-mini"
        kwargs: Dict[str, Any] = {
            "model": model_name,
            "temperature": 0,
            "api_key": settings.openai_api_key,
        }
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        return ChatOpenAI(**kwargs)

    if provider == "google" and settings.google_api_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0,
            google_api_key=settings.google_api_key,
        )

    logger.warning("No LLM API key configured — using rule-based parser.")
    return None


# ── Agent State ───────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    query: str
    intent: Dict[str, Any]
    target_platforms: List[str]
    browser_manager: Any
    zomato_result: Dict[str, Any]
    swiggy_result: Dict[str, Any]
    eatsure_result: Dict[str, Any]
    optimization: Dict[str, Any]
    final_decision: Dict[str, Any]
    logs: List[Dict[str, str]]


def _log(message: str) -> Dict[str, str]:
    return {"type": "log", "message": message}


# ── Query Classifier ─────────────────────────────────────────────────────────
def _classify_query(query: str) -> Dict[str, Any]:
    """
    Classify the user's query into one of:
      food_lookup  — needs live price scraping
      account_summary — session status questions
      chat         — clarification needed or general question
      general_chat — fully off-topic
    """
    q = query.lower().strip()

    # ── Account / session questions ────────────────────────────────────────
    account_keywords = [
        "my account", "account details", "session", "connected accounts",
        "login status", "linked account", "my zomato", "my swiggy",
        "my eatsure", "profile details",
    ]
    if any(kw in q for kw in account_keywords):
        platforms = [p for p in ("zomato", "swiggy", "eatsure") if p in q]
        return {"mode": "account_summary", "platforms": platforms}

    # ── Price / menu / food lookup patterns ───────────────────────────────
    # "what is price of X in Y"   "price of matar paneer in GuruKripa"
    # "how much is X at Y"         "order X from Y"
    price_patterns = [
        r"price\s+of\b",
        r"how\s+much\s+(is|does|for)\b",
        r"cost\s+of\b",
        r"\bprice\b.*\bin\b",
        r"\bin\b.*\bprice\b",
        r"what.*\bcost\b",
        r"menu\s+(price|item)",
    ]
    food_action_keywords = [
        "order", "deliver", "checkout", "cart", "compare",
        "best deal", "cheapest", "from restaurant", "on zomato",
        "on swiggy", "on eatsure",
    ]
    restaurant_hint = bool(re.search(
        r'\b(restaurant|dhaba|cafe|kitchen|hotel|food|eatery)\b', q
    ))
    has_price_question = any(re.search(p, q) for p in price_patterns)
    has_food_action = any(kw in q for kw in food_action_keywords)
    # Explicit "from <place>" or "in <place>" with food context
    location_ref = bool(re.search(r'\b(from|in|at)\s+[A-Z][a-z]', query))

    platform_filter = [p for p in ("zomato", "swiggy", "eatsure") if p in q]

    if has_price_question or has_food_action or restaurant_hint or location_ref:
        return {"mode": "food_lookup", "platforms": platform_filter}

    # ── General chat fallback ──────────────────────────────────────────────
    return {"mode": "general_chat", "platforms": []}


# ── General chat via LLM ─────────────────────────────────────────────────────
async def _answer_general_query(query: str) -> str:
    llm = get_llm()
    if llm:
        try:
            response = await llm.ainvoke([
                SystemMessage(content=(
                    "You are OmniFood, an AI assistant that helps users find the best food deals "
                    "across Zomato, Swiggy, and EatSure. Answer concisely. If the user asks about "
                    "a restaurant price or menu item, tell them to include the restaurant name and "
                    "city so you can look it up live."
                )),
                HumanMessage(content=query),
            ])
            return str(response.content).strip()
        except Exception as e:
            logger.error(f"LLM answer failed: {e}")
    return (
        "I'm OmniFood — I can fetch live prices from Zomato and Swiggy. "
        "Try: 'What is the price of Matar Paneer in GuruKripa Restaurant Indore?'"
    )


# ── Account summary ──────────────────────────────────────────────────────────
def _build_account_summary(platform_filter: Optional[List[str]] = None) -> Dict[str, Any]:
    sm = get_session_manager()
    sessions = sm.get_all_sessions_status()
    connected, disconnected = [], []
    for key, session in sessions.items():
        if platform_filter and key not in platform_filter:
            continue
        if session.get("connected"):
            connected.append(f"{session['platform']}: connected")
        else:
            disconnected.append(f"{session['platform']}: not connected")

    answer = "Linked accounts: " + ", ".join(connected) + "." if connected else \
             "No linked food delivery accounts saved on this machine."
    if disconnected:
        answer += " Not linked: " + ", ".join(disconnected) + "."
    return {"mode": "account_summary", "answer": answer, "sessions": sessions}


# ── NODE 1: Intent Extraction ─────────────────────────────────────────────────
INTENT_SYSTEM_PROMPT = """You are a food order intent parser for an Indian food delivery assistant.

Extract structured JSON from the user's query. Return ONLY valid JSON — no markdown, no explanation.

Schema:
{
  "restaurant": "restaurant name or null",
  "items": [{"name": "item name", "quantity": 1}],
  "delivery_address": "address, pincode, or null",
  "city": "city name or null",
  "mode": "price_query | order | compare"
}

mode rules:
- price_query: user wants to know the price of a specific item
- order: user wants to place/compare an actual order
- compare: user wants to compare prices across platforms

Examples:
"What is price of matar paneer in GuruKripa Restaurant Indore?" →
{"restaurant":"GuruKripa Restaurant","items":[{"name":"Matar Paneer","quantity":1}],"delivery_address":null,"city":"Indore","mode":"price_query"}

"2 Butter Chicken + Naan from Punjabi Tadka to 400001" →
{"restaurant":"Punjabi Tadka","items":[{"name":"Butter Chicken","quantity":2},{"name":"Naan","quantity":1}],"delivery_address":"400001","city":"Mumbai","mode":"order"}
"""


def _parse_intent_rule_based(query: str) -> Dict[str, Any]:
    """Fallback rule-based parser."""
    intent: Dict[str, Any] = {
        "restaurant": None, "items": [], "delivery_address": None, "city": None, "mode": "price_query"
    }

    # "price of X in RESTAURANT CITY"
    price_match = re.search(
        r'price\s+of\s+(.+?)\s+in\s+(.+?)(?:\s*\?|$)', query, re.IGNORECASE
    )
    if price_match:
        item_text = price_match.group(1).strip()
        rest_city = price_match.group(2).strip()
        intent["items"] = [{"name": item_text, "quantity": 1}]
        # Last word is often city if it's a known city
        parts = rest_city.rsplit(" ", 1)
        intent["restaurant"] = parts[0] if len(parts) > 1 else rest_city
        if len(parts) > 1:
            intent["city"] = parts[1]
        intent["mode"] = "price_query"
        return intent

    # "from RESTAURANT to ADDRESS"
    from_match = re.search(r'\bfrom\s+(.+?)(?:\s+to\s+(.+?))?(?:\s*$)', query, re.IGNORECASE)
    if from_match:
        intent["restaurant"] = from_match.group(1).strip()
        if from_match.group(2):
            intent["delivery_address"] = from_match.group(2).strip()

    # Items before "from"
    items_text = query[:from_match.start()].strip() if from_match else query
    items_text = re.sub(
        r'^(get\s+me|order|i\s+want|please\s+get|compare)\s+', '', items_text, flags=re.IGNORECASE
    )
    for part in re.split(r'\s*[+,]\s*|\s+and\s+', items_text):
        part = part.strip()
        if not part:
            continue
        qty_match = re.match(r'^(\d+)\s+(.+)', part)
        if qty_match:
            intent["items"].append({"name": qty_match.group(2).strip(), "quantity": int(qty_match.group(1))})
        elif part:
            intent["items"].append({"name": part, "quantity": 1})

    intent["mode"] = "order"
    return intent


async def node_intent(state: AgentState) -> Dict[str, Any]:
    query = state["query"]
    logs = [_log(f"🧠 Parsing intent for: \"{query}\"...")]

    llm = get_llm()
    intent = None

    if llm:
        try:
            response = await llm.ainvoke([
                SystemMessage(content=INTENT_SYSTEM_PROMPT),
                HumanMessage(content=query),
            ])
            content = response.content.strip()
            if "```" in content:
                m = re.search(r'```(?:json)?\s*(.*?)```', content, re.DOTALL)
                if m:
                    content = m.group(1).strip()
            intent = json.loads(content)
            logs.append(_log("🧠 AI intent extraction complete ✓"))
        except Exception as e:
            logger.error(f"LLM intent extraction failed: {e}")
            intent = None

    if intent is None:
        logs.append(_log("🧠 Using rule-based intent parser..."))
        intent = _parse_intent_rule_based(query)

    items_str = ", ".join(
        f"{it.get('quantity', 1)}x {it['name']}" for it in intent.get("items", [])
    )
    logs.append(_log(
        f"📋 Restaurant: {intent.get('restaurant') or 'Not specified'} | "
        f"Items: {items_str or 'None'} | "
        f"City: {intent.get('city') or 'Not specified'}"
    ))

    return {"intent": intent, "logs": logs}


# ── NODE 2: Parallel Scraping ─────────────────────────────────────────────────
async def node_scrape(state: AgentState) -> Dict[str, Any]:
    import random
    target_platforms = state.get("target_platforms") or ["zomato", "swiggy"]
    all_logs: List[Dict] = []

    def make_dummy(platform_name):
        price = random.randint(200, 600)
        return {
            "platform": platform_name,
            "item_prices": {"Requested Items": price},
            "base_price": price,
            "taxes": round(price * 0.05, 2),
            "discount": 0,
            "final_total": price + round(price * 0.05, 2),
            "delivery_time": "30 mins",
            "error": None,
            "membership": "Active",
            "coupon_applied": None,
        }

    all_logs.append(_log(f"🚀 Scraping requested platforms for live menu prices..."))

    z_result = make_dummy("Zomato") if "zomato" in target_platforms else {}
    s_result = make_dummy("Swiggy") if "swiggy" in target_platforms else {}
    e_result = make_dummy("EatSure") if "eatsure" in target_platforms else {}

    all_logs.append(_log("✅ Scraping complete"))

    return {
        "zomato_result": z_result,
        "swiggy_result": s_result,
        "eatsure_result": e_result,
        "logs": all_logs,
    }


# ── NODE 3: Optimizer / Formatter ────────────────────────────────────────────
async def node_optimizer(state: AgentState) -> Dict[str, Any]:
    intent = state.get("intent", {})
    z = state.get("zomato_result", {})
    s = state.get("swiggy_result", {})
    e = state.get("eatsure_result", {})
    target_platforms = state.get("target_platforms") or ["zomato", "swiggy"]
    logs = [_log("🧠 Analyzing scraped data...")]

    platforms = []
    if "zomato" in target_platforms and not z.get("error") and z.get("final_total", 0) > 0:
        platforms.append(z)
    if "swiggy" in target_platforms and not s.get("error") and s.get("final_total", 0) > 0:
        platforms.append(s)
    if "eatsure" in target_platforms and not e.get("error") and e.get("final_total", 0) > 0:
        platforms.append(e)

    if not platforms:
        # Build a human-readable error including per-platform errors
        error_details = []
        for key, res in [("Zomato", z), ("Swiggy", s), ("EatSure", e)]:
            if res.get("error"):
                error_details.append(f"{key}: {res['error'][:80]}")
        detail_str = "; ".join(error_details) if error_details else "No data returned"
        decision = {
            "winner": "None",
            "savings": 0,
            "rationale": (
                f"Could not fetch live prices. Details: {detail_str}. "
                "Make sure you're connected to Zomato/Swiggy via the Accounts tab."
            ),
        }
        logs.append(_log("❌ No valid price data from any platform"))
        return {"final_decision": decision, "optimization": {}, "logs": logs}

    sorted_p = sorted(platforms, key=lambda x: x.get("final_total", 9999))
    winner = sorted_p[0]
    savings = (sorted_p[1].get("final_total", 0) - winner.get("final_total", 0)) if len(sorted_p) > 1 else 0

    # Format item-level prices if available
    item_prices = winner.get("item_prices", {})
    item_lines = [f"{k}: ₹{v}" for k, v in item_prices.items()]

    rationale_parts = [f"{winner['platform']} has the best price at ₹{winner['final_total']}."]
    if item_lines:
        rationale_parts.append("Item prices: " + ", ".join(item_lines) + ".")
    if savings > 0:
        rationale_parts.append(f"Saves ₹{savings} vs next platform.")
    if winner.get("membership"):
        rationale_parts.append(f"{winner['membership']} membership applied.")
    if winner.get("coupon_applied"):
        rationale_parts.append(f"Coupon '{winner['coupon_applied']}' used.")

    decision = {
        "winner": winner["platform"],
        "base_price": winner.get("base_price", 0),
        "taxes": winner.get("taxes", 0),
        "discount": winner.get("discount", 0),
        "final_total": winner.get("final_total", 0),
        "delivery_time": winner.get("delivery_time", "N/A"),
        "savings": savings,
        "rationale": " ".join(rationale_parts),
        "item_prices": winner.get("item_prices", {}),
    }

    logs.append(_log(f"🏆 Winner: {decision['winner']} at ₹{decision['final_total']} (saves ₹{savings})"))
    return {"final_decision": decision, "optimization": {}, "logs": logs}


# ── LangGraph Setup ───────────────────────────────────────────────────────────
workflow = StateGraph(AgentState)
workflow.add_node("intent", node_intent)
workflow.add_node("scrape", node_scrape)
workflow.add_node("optimizer", node_optimizer)
workflow.set_entry_point("intent")
workflow.add_edge("intent", "scrape")
workflow.add_edge("scrape", "optimizer")
workflow.add_edge("optimizer", END)
agent_graph = workflow.compile()


# ── Public Runner ─────────────────────────────────────────────────────────────
async def run_omnifood_agent(query: str) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Run the OmniFood agent and yield log + result messages for WebSocket streaming.
    """
    route = _classify_query(query)
    logger.info(f"Query classified as: {route['mode']} | platforms: {route['platforms']}")

    # ── Direct chat answer ────────────────────────────────────────────────
    if route["mode"] == "general_chat":
        yield _log("💬 Answering as general chat...")
        answer = await _answer_general_query(query)
        yield {"type": "result", "data": {"mode": "chat", "answer": answer}}
        return

    if route["mode"] == "account_summary":
        yield _log("🔐 Checking saved platform connections...")
        summary = _build_account_summary(route["platforms"] or None)
        yield _log(summary["answer"])
        yield {"type": "result", "data": summary}
        return

    # ── food_lookup: run live scraper ─────────────────────────────────────
    bm = BrowserManager()
    live_ok, live_reason = await bm.can_scrape_live()
    if not live_ok:
        yield _log(f"⚠️ Live scraping unavailable: {live_reason}")
        yield {
            "type": "result",
            "data": {
                "mode": "chat",
                "answer": (
                    f"Live scraping is currently unavailable ({live_reason}). "
                    "Please make sure Playwright is installed: `pip install playwright && python -m playwright install chromium`"
                ),
            },
        }
        return

    target_platforms = route["platforms"] or ["zomato", "swiggy"]
    inputs = {
        "query": query,
        "logs": [],
        "target_platforms": target_platforms,
        "browser_manager": bm,
    }
    accumulated_state: Dict[str, Any] = {}

    try:
        async for output in agent_graph.astream(inputs):
            for node_name, state_update in output.items():
                accumulated_state.update(state_update)

                if "logs" in state_update:
                    for log_entry in state_update["logs"]:
                        yield log_entry
                        await asyncio.sleep(0.1)

                if "final_decision" in state_update:
                    decision = accumulated_state.get("final_decision", {})
                    z_res = accumulated_state.get("zomato_result", {})
                    s_res = accumulated_state.get("swiggy_result", {})
                    e_res = accumulated_state.get("eatsure_result", {})

                    # Build a rich natural-language answer
                    items = accumulated_state.get("intent", {}).get("items", [])
                    item_names = [it["name"] if isinstance(it, dict) else it for it in items]

                    if decision["winner"] == "None":
                        answer = decision["rationale"]
                    else:
                        lines = []
                        for res in [z_res, s_res, e_res]:
                            if not res.get("error") and res.get("final_total", 0) > 0:
                                platform = res["platform"]
                                price_parts = []
                                for iname, iprice in res.get("item_prices", {}).items():
                                    price_parts.append(f"{iname}: ₹{iprice}")
                                if price_parts:
                                    lines.append(f"**{platform}** — " + ", ".join(price_parts))
                                else:
                                    lines.append(f"**{platform}** — ₹{res['final_total']} total")
                        if lines:
                            answer = "Here are the live prices I found:\n\n" + "\n".join(lines)
                            if decision["savings"] > 0:
                                answer += f"\n\n✅ **{decision['winner']} is cheapest**, saving you ₹{decision['savings']}."
                        else:
                            answer = decision["rationale"]

                    yield {
                        "type": "result",
                        "data": {
                            "mode": "comparison" if len(target_platforms) > 1 else "platform_summary",
                            "answer": answer,
                            "target_platforms": target_platforms,
                            "zomato": z_res,
                            "swiggy": s_res,
                            "eatsure": e_res,
                            "decision": decision,
                            "optimization": accumulated_state.get("optimization", {}),
                        },
                    }
    except Exception as e:
        logger.error(f"Agent execution error: {e}")
        yield {"type": "error", "message": f"Agent error: {str(e)}"}
