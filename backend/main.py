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

# ── Fix for Python 3.14+ on Windows ──
# Python 3.14 changed asyncio subprocess internals; Playwright needs ProactorEventLoop
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import get_settings
from agent import run_omnifood_agent

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
    # Python 3.14 + Uvicorn on Windows sets SelectorEventLoop; Playwright needs ProactorEventLoop
    if platform.system() == "Windows":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass
            
    logger.info("OmniFood Agent API starting up...")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"Headless Mode: {settings.headless}")
    logger.info(f"CORS Origins: {settings.cors_origins}")
    
    # Check if Playwright browsers are installed
    try:
        from playwright.async_api import async_playwright
        pw = await async_playwright().start()
        try:
            browser = await pw.chromium.launch(headless=True)
            await browser.close()
            logger.info("Playwright browsers: OK ✓")
        finally:
            await pw.stop()
    except NotImplementedError:
        logger.warning("Playwright subprocess check skipped (Python 3.14 async compat)")
        logger.info("Playwright will work at runtime with ProactorEventLoop policy.")
    except Exception as e:
        logger.warning(f"Playwright browsers may not be installed: {e}")
        logger.warning("Run: python -m playwright install chromium")
    
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
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
