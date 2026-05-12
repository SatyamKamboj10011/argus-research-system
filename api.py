from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pipeline import run_research_pipeline
from agents import get_llm
from typing import Optional

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
def research(req: ResearchRequest):
    llm = get_llm(req.model, req.api_key if req.api_key else None)
    result = run_research_pipeline(req.topic, llm)
    return {
        "topic": req.topic,
        "search_results": result["search_results"],
        "scraped_content": result["scraped_content"],
        "report": result["report"],
        "feedback": result["feedback"],
    }