from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pipeline import run_research_pipeline
from agents import get_llm
from typing import Optional
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ARGUS Research API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ResearchRequest(BaseModel):
    topic: str
    model: str = "Groq — Llama 3.3 70B"
    api_key: Optional[str] = None

@app.get("/")
def health():
    return {"status": "online", "service": "ARGUS Research API"}

@app.post("/research")
async def research(req: ResearchRequest):
    try:
        llm = get_llm(req.model, req.api_key if req.api_key else None)
    except Exception as e:
        logger.error(f"LLM init failed: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to initialize model: {str(e)}")

    try:
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, run_research_pipeline, req.topic, llm),
            timeout=280,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Research pipeline timed out. Try a shorter topic or faster model.")
    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "topic": req.topic,
        "search_results": result.get("search_results", ""),
        "scraped_content": result.get("scraped_content", ""),
        "report": result.get("report", ""),
        "feedback": result.get("feedback", ""),
        "followup_questions": result.get("followup_questions", ""),
    }