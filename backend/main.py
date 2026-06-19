"""
OmniFood Agent - FastAPI Entry Point
Production-grade API with WebSocket streaming, health checks, and structured logging.
"""

import asyncio
import json
import logging
import os
import platform
import sys
from contextlib import asynccontextmanager
from datetime import datetime

if platform.system() == "Windows":
    try:
        # In Python 3.14, Proactor is default, but we set it explicitly 
        # to ensure compatibility with Playwright subprocesses.
        if not isinstance(asyncio.get_event_loop_policy(), asyncio.WindowsProactorEventLoopPolicy):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import get_settings
from agent import run_omnifood_agent
from session_manager import get_session_manager

# ── Logging Setup ──
settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(name)-22s | %(levelname)-5s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("omnifood.server")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("OmniFood Agent API starting up...")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"Headless Mode: {settings.headless}")
    logger.info(f"Demo Mode: {settings.demo_mode}")
    logger.info(f"CORS Origins: {settings.cors_origins}")
    
    import asyncio
    loop = asyncio.get_running_loop()
    logger.info(f"Current Asyncio Loop: {type(loop)}")
    
    logger.info("Playwright availability is checked per-request (not at startup).")
    yield
    logger.info("OmniFood Agent API shutting down...")

# ── FastAPI App ──
app = FastAPI(
    title="OmniFood Agent API",
    description="AI-powered food price aggregator for Zomato, Swiggy & EatSure",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──
origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Models ──
class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500, description="Natural language food order query")

class PlatformRequest(BaseModel):
    platform: str = Field(..., description="Platform key: zomato, swiggy, or eatsure")

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    llm_provider: str
    headless: bool


# ── REST Endpoints ──
@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for monitoring."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0",
        llm_provider=settings.llm_provider,
        headless=settings.headless,
    )


@app.post("/api/search")
async def search_food(request: QueryRequest):
    """
    Synchronous endpoint — runs the full agent pipeline and returns the result.
    Use /ws/agent for streaming logs.
    """
    logs = []
    result = None
    
    try:
        async for message in run_omnifood_agent(request.query):
            if message.get("type") == "result":
                result = message.get("data")
            else:
                logs.append(message)
        
        return {
            "success": True,
            "query": request.query,
            "logs": logs,
            "result": result,
        }
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Session Management Endpoints ──
@app.get("/api/sessions")
async def get_sessions():
    """
    Get the connection status of all platform sessions.
    Returns which platforms the user is logged into and their details.
    """
    sm = get_session_manager()
    sessions = sm.get_all_sessions_status()
    return {"success": True, "sessions": sessions}


@app.post("/api/sessions/login")
async def start_login(request: PlatformRequest):
    """
    Start a login flow for a platform.
    Opens a visible browser window where the user can log in.
    """
    sm = get_session_manager()
    result = await sm.start_login(request.platform.lower())
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Login failed"))
    return result


@app.post("/api/sessions/confirm")
async def confirm_login(request: PlatformRequest):
    """
    Confirm that the user has logged in via the visible browser.
    Saves the session state (cookies, tokens) for future scraping.
    """
    sm = get_session_manager()
    result = await sm.confirm_login(request.platform.lower())
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Confirmation failed"))
    return result


@app.post("/api/sessions/cancel")
async def cancel_login(request: PlatformRequest):
    """
    Cancel an in-progress login and close the browser window.
    """
    sm = get_session_manager()
    result = await sm.cancel_login(request.platform.lower())
    return result


@app.post("/api/sessions/disconnect")
async def disconnect_session(request: PlatformRequest):
    """
    Disconnect a platform session. Removes saved cookies and session data.
    """
    sm = get_session_manager()
    result = await sm.disconnect(request.platform.lower())
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Disconnect failed"))
    return result


# ── WebSocket Endpoint ──
@app.websocket("/ws/agent")
async def websocket_agent(websocket: WebSocket):
    """
    WebSocket endpoint for real-time streaming of agent activity.
    
    Client sends: {"query": "2 Butter Chicken from Punjabi Tadka to 400001"}
    Server streams: {"type": "log", "message": "..."} and {"type": "result", "data": {...}}
    """
    await websocket.accept()
    client_id = id(websocket)
    logger.info(f"WebSocket client connected: {client_id}")
    
    try:
        # Send session status as first message
        sm = get_session_manager()
        sessions = sm.get_all_sessions_status()
        connected_platforms = [k for k, v in sessions.items() if v.get("connected")]
        await websocket.send_json({
            "type": "sessions",
            "data": sessions,
            "connected": connected_platforms,
        })

        # Receive the query
        data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
        request_data = json.loads(data)
        query = request_data.get("query", "").strip()
        
        if not query:
            await websocket.send_json({"type": "error", "message": "Empty query"})
            return
        
        if len(query) < 3:
            await websocket.send_json({"type": "error", "message": "Query too short"})
            return
        
        logger.info(f"Client {client_id} query: {query}")
        
        # Stream agent output
        async for message in run_omnifood_agent(query):
            try:
                await websocket.send_json(message)
            except WebSocketDisconnect:
                logger.info(f"Client {client_id} disconnected during streaming")
                return
        
        # Signal completion
        await websocket.send_json({"type": "done"})
        logger.info(f"Client {client_id} query completed successfully")
        
    except asyncio.TimeoutError:
        logger.warning(f"Client {client_id} timeout waiting for query")
        try:
            await websocket.send_json({"type": "error", "message": "Timeout waiting for query"})
        except Exception:
            pass
    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected")
    except json.JSONDecodeError:
        logger.warning(f"Client {client_id} sent invalid JSON")
        try:
            await websocket.send_json({"type": "error", "message": "Invalid JSON"})
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Client {client_id} error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


if __name__ == "__main__":
    if platform.system() == "Windows":
        # Force Proactor loop policy for Playwright compatibility
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=False,  # Reload mode forces SelectorLoop on Windows, which breaks Playwright
        log_level=settings.log_level.lower(),
        loop="asyncio"
    )
