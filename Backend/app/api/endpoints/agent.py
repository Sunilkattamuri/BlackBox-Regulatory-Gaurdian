from fastapi import APIRouter, HTTPException
from typing import List
from ... import schemas
from ...services.agent_service import agent_service

router = APIRouter()


@router.post("/query", response_model=schemas.AgentResponse)
def query_agent(request: schemas.AgentRequest):
    """
    Process a query through the multi-agent system.
    Routes to the appropriate specialist agent based on query content.
    Set run_full_pipeline=True for a complete LRR cycle (Monitor → Extract → Assess → Report).
    """
    try:
        result = agent_service.process_query(
            query=request.query,
            run_full_pipeline=request.run_full_pipeline,
        )
        return schemas.AgentResponse(
            response=result.get("response", "No response generated."),
            sources=result.get("sources"),
            agent_used=result.get("agent_used"),
            guardrail_applied=result.get("guardrail_applied", False),
            processing_steps=result.get("processing_steps"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents", response_model=List[schemas.AgentInfo])
def list_agents():
    """List all available agents and their capabilities."""
    agents_info = agent_service.get_agents_info()
    return [
        schemas.AgentInfo(
            name=a["name"],
            description=a["description"],
            capabilities=a["capabilities"],
            tools=a["tools"],
        )
        for a in agents_info
    ]


@router.get("/health")
def agent_health():
    """Check agent system health and initialization status."""
    return {
        "initialized": agent_service._initialized,
        "llm_provider": agent_service.llm.__class__.__name__ if agent_service.llm else None,
        "error": agent_service._init_error,
        "agents_count": len(agent_service.get_agents_info()),
    }
