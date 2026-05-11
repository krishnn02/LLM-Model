"""
OmniFood Agent - LangGraph ReAct State Machine
Orchestrates intent parsing, parallel scraping, and price optimization.
"""

import asyncio
import json
import logging
import os
from typing import Dict, TypedDict, Any, AsyncGenerator, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from scraper import BrowserManager
from config import get_settings

logger = logging.getLogger("omnifood.agent")

# ── LLM Initialization ──
def get_llm():
    """Initialize the LLM based on configuration."""
    settings = get_settings()
    provider = settings.llm_provider.lower()
    
    if provider == "openai" and settings.openai_api_key:
        from langchain_openai import ChatOpenAI
        # If openrouter is used, ensure we pass a supported model name
        model_name = "openai/gpt-4o-mini" if "openrouter" in settings.openai_base_url else "gpt-4o-mini"
        kwargs = {
            "model": model_name,
            "temperature": 0,
            "api_key": settings.openai_api_key,
        }
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        return ChatOpenAI(**kwargs)
    elif provider == "google" and settings.google_api_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0,
            google_api_key=settings.google_api_key,
        )
    else:
        logger.warning("No LLM API key configured. Using rule-based intent parser.")
        return None

# ── Agent State ──
class AgentState(TypedDict):
    query: str
    intent: Dict[str, Any]
    zomato_result: Dict[str, Any]
    swiggy_result: Dict[str, Any]
    eatsure_result: Dict[str, Any]
    optimization: Dict[str, Any]
    final_decision: Dict[str, Any]
    logs: list[Dict[str, str]]

# ── Log message helper ──
def _log(message: str) -> Dict[str, str]:
    return {"type": "log", "message": message}

# ──────────────────────────────────────────────
# NODE 1: Intent Extraction
# ──────────────────────────────────────────────
INTENT_SYSTEM_PROMPT = """You are a food order intent parser. Extract structured information from the user's natural language query about ordering food.

Return ONLY valid JSON with these fields:
{
  "restaurant": "restaurant name (string, or null if not specified)",
  "items": [{"name": "item name", "quantity": 1}],
  "delivery_address": "address or pincode (string, or null if not specified)",
  "city": "city name (string, or null if not specified)"
}

Rules:
- If the user says "2 Butter Chicken", that means quantity 2.
- If no quantity is specified, assume 1.
- Extract the city from the address if possible.
- If the user mentions a pincode, use it as delivery_address.
- Be flexible with restaurant names — extract the closest match.

Examples:
"2 Butter Chicken + Naan from Punjabi Tadka to 400001" →
{"restaurant": "Punjabi Tadka", "items": [{"name": "Butter Chicken", "quantity": 2}, {"name": "Naan", "quantity": 1}], "delivery_address": "400001", "city": "Mumbai"}

"Get me a Margherita Pizza from Dominos" →
{"restaurant": "Dominos", "items": [{"name": "Margherita Pizza", "quantity": 1}], "delivery_address": null, "city": null}
"""

def _parse_intent_rule_based(query: str) -> Dict[str, Any]:
    """
    Rule-based intent parser as fallback when no LLM is available.
    Handles common patterns like 'X from Restaurant to Address'.
    """
    import re
    
    intent = {
        "restaurant": None,
        "items": [],
        "delivery_address": None,
        "city": None,
    }
    
    query_lower = query.lower().strip()
    
    # Extract "from <restaurant>" pattern
    from_match = re.search(r'\bfrom\s+(.+?)(?:\s+to\s+|\s+deliver|\s*$)', query, re.IGNORECASE)
    if from_match:
        intent["restaurant"] = from_match.group(1).strip().rstrip('.')
    
    # Extract "to <address>" pattern
    to_match = re.search(r'\bto\s+(.+?)$', query, re.IGNORECASE)
    if to_match:
        intent["delivery_address"] = to_match.group(1).strip().rstrip('.')
    
    # Extract items: everything before "from"
    items_text = query
    if from_match:
        items_text = query[:from_match.start()]
    
    # Remove common prefixes
    items_text = re.sub(r'^(get\s+me|order|i\s+want|please\s+get|can\s+you\s+order)\s+', '', items_text, flags=re.IGNORECASE)
    
    # Split by '+', ',', 'and'
    item_parts = re.split(r'\s*[+,]\s*|\s+and\s+', items_text)
    
    for part in item_parts:
        part = part.strip()
        if not part:
            continue
        # Check for quantity prefix: "2 Butter Chicken"
        qty_match = re.match(r'^(\d+)\s+(.+)', part)
        if qty_match:
            intent["items"].append({
                "name": qty_match.group(2).strip(),
                "quantity": int(qty_match.group(1)),
            })
        elif part:
            intent["items"].append({"name": part, "quantity": 1})
    
    # Detect pincode in address
    if intent["delivery_address"]:
        pincode_match = re.search(r'\b\d{6}\b', intent["delivery_address"])
        if pincode_match:
            # It's a pincode, try to detect city
            pass
    
    return intent


async def node_intent(state: AgentState) -> Dict[str, Any]:
    """Extract structured intent from natural language query using LLM or rule-based fallback."""
    query = state["query"]
    logs = [_log(f"🧠 Parsing intent for: \"{query}\"...")]
    
    llm = get_llm()
    intent = None
    
    if llm:
        try:
            logs.append(_log("🧠 Using AI to extract restaurant, items, and address..."))
            response = await llm.ainvoke([
                SystemMessage(content=INTENT_SYSTEM_PROMPT),
                HumanMessage(content=query),
            ])
            
            # Parse LLM response
            content = response.content.strip()
            # Handle markdown code blocks
            if "```" in content:
                import re
                json_match = re.search(r'```(?:json)?\s*(.*?)```', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1).strip()
            
            intent = json.loads(content)
            logs.append(_log(f"🧠 AI Intent Extraction Complete ✓"))
        except Exception as e:
            logger.error(f"LLM intent extraction failed: {e}")
            logs.append(_log(f"🧠 AI extraction failed, using rule-based parser..."))
            intent = None
    
    if intent is None:
        logs.append(_log("🧠 Using rule-based intent parser..."))
        intent = _parse_intent_rule_based(query)
    
    # Format items for logging
    items_str = ", ".join(
        f"{item.get('quantity', 1)}x {item['name']}" 
        for item in intent.get("items", [])
    )
    
    logs.append(_log(
        f"📋 Restaurant: {intent.get('restaurant', 'Not specified')} | "
        f"Items: {items_str or 'None detected'} | "
        f"Address: {intent.get('delivery_address', 'Not specified')}"
    ))
    
    return {"intent": intent, "logs": logs}


# ──────────────────────────────────────────────
# NODE 2: Parallel Scraping (Fan-Out)
# ──────────────────────────────────────────────
async def node_scrape(state: AgentState) -> Dict[str, Any]:
    """Launch parallel browser workers to scrape Zomato, Swiggy, and EatSure."""
    intent = state["intent"]
    all_logs = []
    
    # Flatten items for scraper (just names list)
    item_names = []
    for item in intent.get("items", []):
        name = item.get("name", "") if isinstance(item, dict) else str(item)
        qty = item.get("quantity", 1) if isinstance(item, dict) else 1
        item_names.extend([name] * qty)
    
    scraper_intent = {
        "restaurant": intent.get("restaurant", ""),
        "items": item_names,
        "delivery_address": intent.get("delivery_address", ""),
    }
    
    all_logs.append(_log("🚀 Launching parallel browser workers for Zomato, Swiggy, and EatSure..."))
    
    # Create log collectors for each platform
    zomato_logs = []
    swiggy_logs = []
    eatsure_logs = []
    
    async def zomato_log(msg):
        zomato_logs.append(_log(msg))
    
    async def swiggy_log(msg):
        swiggy_logs.append(_log(msg))
    
    async def eatsure_log(msg):
        eatsure_logs.append(_log(msg))
    
    bm = BrowserManager()
    
    # Run all three scrapers in parallel
    z_task = asyncio.create_task(bm.scrape_zomato(scraper_intent, log=zomato_log))
    s_task = asyncio.create_task(bm.scrape_swiggy(scraper_intent, log=swiggy_log))
    e_task = asyncio.create_task(bm.scrape_eatsure(scraper_intent, log=eatsure_log))
    
    z_result, s_result, e_result = await asyncio.gather(z_task, s_task, e_task, return_exceptions=True)
    
    # Handle exceptions
    if isinstance(z_result, Exception):
        logger.error(f"Zomato scraper exception: {z_result}")
        z_result = {
            "platform": "Zomato", "base_price": 0, "taxes": 0,
            "discount": 0, "final_total": 0, "delivery_time": "N/A",
            "error": str(z_result), "membership": None, "coupon_applied": None,
        }
    
    if isinstance(s_result, Exception):
        logger.error(f"Swiggy scraper exception: {s_result}")
        s_result = {
            "platform": "Swiggy", "base_price": 0, "taxes": 0,
            "discount": 0, "final_total": 0, "delivery_time": "N/A",
            "error": str(s_result), "membership": None, "coupon_applied": None,
        }
    
    if isinstance(e_result, Exception):
        logger.error(f"EatSure scraper exception: {e_result}")
        e_result = {
            "platform": "EatSure", "base_price": 0, "taxes": 0,
            "discount": 0, "final_total": 0, "delivery_time": "N/A",
            "error": str(e_result), "membership": None, "coupon_applied": None,
        }
    
    # Merge logs in interleaved order for better UX
    max_len = max(len(zomato_logs), len(swiggy_logs), len(eatsure_logs))
    for i in range(max_len):
        if i < len(zomato_logs):
            all_logs.append(zomato_logs[i])
        if i < len(swiggy_logs):
            all_logs.append(swiggy_logs[i])
        if i < len(eatsure_logs):
            all_logs.append(eatsure_logs[i])
    
    all_logs.append(_log(
        f"✅ Scraping complete — "
        f"Zomato: ₹{z_result.get('final_total', 0)} | "
        f"Swiggy: ₹{s_result.get('final_total', 0)} | "
        f"EatSure: ₹{e_result.get('final_total', 0)}"
    ))
    
    return {
        "zomato_result": z_result,
        "swiggy_result": s_result,
        "eatsure_result": e_result,
        "logs": all_logs,
    }


# ──────────────────────────────────────────────
# NODE 3: Price Optimizer
# ──────────────────────────────────────────────
async def node_optimizer(state: AgentState) -> Dict[str, Any]:
    """
    Compare totals across all platforms and optimize.
    Key feature: if a cart is ₹460 and a ₹100 discount starts at ₹500,
    suggest a cheap filler item.
    """
    z_res = state.get("zomato_result", {})
    s_res = state.get("swiggy_result", {})
    e_res = state.get("eatsure_result", {})
    logs = [_log("🧠 Optimizer: Analyzing price data across platforms...")]
    
    platforms = []
    
    # Build platform comparison list (skip errored ones)
    if z_res.get("final_total", 0) > 0:
        platforms.append(z_res)
    else:
        logs.append(_log("⚠️  Zomato: No valid price data (scraping may have failed)"))
    
    if s_res.get("final_total", 0) > 0:
        platforms.append(s_res)
    else:
        logs.append(_log("⚠️  Swiggy: No valid price data (scraping may have failed)"))
    
    if e_res.get("final_total", 0) > 0:
        platforms.append(e_res)
    else:
        logs.append(_log("⚠️  EatSure: No valid price data (scraping may have failed)"))
    
    optimization = {"filler_suggestion": None}
    
    if len(platforms) == 0:
        logs.append(_log("❌ No valid price data from any platform. Please try again."))
        return {
            "final_decision": {
                "winner": "None",
                "savings": 0,
                "rationale": "Could not fetch prices from any platform. Please ensure you are logged in and try again.",
            },
            "optimization": optimization,
            "logs": logs,
        }
    
    # ── Filler item optimization ──
    # Common discount thresholds on Zomato/Swiggy/EatSure
    discount_thresholds = [200, 300, 500, 750, 1000]
    
    for platform in platforms:
        base = platform.get("base_price", 0)
        for threshold in discount_thresholds:
            gap = threshold - base
            if 0 < gap <= 100:
                # Within ₹100 of a discount threshold — suggest filler
                logs.append(
                    _log(
                        f"🧠 Optimizer: {platform['platform']} cart is ₹{base}, "
                        f"only ₹{gap} away from ₹{threshold} discount tier! "
                        f"Consider adding a cheap item like Gulab Jamun (≈₹{gap}) "
                        f"to unlock a bigger discount."
                    )
                )
                optimization["filler_suggestion"] = {
                    "platform": platform["platform"],
                    "current_total": base,
                    "threshold": threshold,
                    "gap": gap,
                    "suggestion": f"Add a ≈₹{gap} item (e.g., Gulab Jamun, Raita, Papad) to reach ₹{threshold} and unlock more savings",
                }
                break
    
    # ── Find the winner ──
    sorted_platforms = sorted(platforms, key=lambda x: x.get("final_total", 9999))
    winner = sorted_platforms[0]
    
    savings = 0
    if len(sorted_platforms) > 1:
        runner_up = sorted_platforms[1]
        savings = runner_up.get("final_total", 0) - winner.get("final_total", 0)
    
    # Build rationale
    rationale_parts = [f"{winner['platform']} offers the best deal at ₹{winner['final_total']}."]
    
    if savings > 0:
        rationale_parts.append(f"You save ₹{savings} compared to the next option.")
    
    if winner.get("membership"):
        rationale_parts.append(f"Your {winner['membership']} membership contributed to this price.")
    
    if winner.get("coupon_applied"):
        rationale_parts.append(f"Coupon '{winner['coupon_applied']}' was applied.")
    
    if winner.get("delivery_time") and winner["delivery_time"] != "N/A":
        rationale_parts.append(f"Estimated delivery: {winner['delivery_time']}.")
    
    decision = {
        "winner": winner["platform"],
        "base_price": winner.get("base_price", 0),
        "taxes": winner.get("taxes", 0),
        "discount": winner.get("discount", 0),
        "final_total": winner.get("final_total", 0),
        "delivery_time": winner.get("delivery_time", "N/A"),
        "savings": savings,
        "rationale": " ".join(rationale_parts),
    }
    
    logs.append(_log(
        f"🏆 Winner: {decision['winner']} at ₹{decision['final_total']} "
        f"(saving ₹{savings})"
    ))
    logs.append(_log(f"✅ Decision Ready — {decision['rationale']}"))
    
    return {
        "final_decision": decision,
        "optimization": optimization,
        "logs": logs,
    }


# ──────────────────────────────────────────────
# Build the LangGraph State Machine
# ──────────────────────────────────────────────
workflow = StateGraph(AgentState)
workflow.add_node("intent", node_intent)
workflow.add_node("scrape", node_scrape)
workflow.add_node("optimizer", node_optimizer)

workflow.set_entry_point("intent")
workflow.add_edge("intent", "scrape")
workflow.add_edge("scrape", "optimizer")
workflow.add_edge("optimizer", END)

agent_graph = workflow.compile()


# ──────────────────────────────────────────────
# Public Runner (Async Generator for WebSocket streaming)
# ──────────────────────────────────────────────
async def run_omnifood_agent(query: str) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Run the OmniFood agent and yield log messages + final result
    as they become available. Designed for WebSocket streaming.
    """
    inputs = {"query": query, "logs": []}
    accumulated_state = {}
    
    try:
        async for output in agent_graph.astream(inputs):
            for node_name, state_update in output.items():
                accumulated_state.update(state_update)
                # Stream each log message individually
                if "logs" in state_update:
                    for log_entry in state_update["logs"]:
                        yield log_entry
                        await asyncio.sleep(0.15)  # Small delay for streaming UX
                
                # Emit the final result
                if "final_decision" in state_update:
                    yield {
                        "type": "result",
                        "data": {
                            "zomato": accumulated_state.get("zomato_result", {}),
                            "swiggy": accumulated_state.get("swiggy_result", {}),
                            "eatsure": accumulated_state.get("eatsure_result", {}),
                            "decision": accumulated_state.get("final_decision", {}),
                            "optimization": accumulated_state.get("optimization", {}),
                        },
                    }
    except Exception as e:
        logger.error(f"Agent execution error: {e}")
        yield {"type": "error", "message": f"Agent error: {str(e)}"}
