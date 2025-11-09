"""
FastAPI application - REST API endpoints for research workflow.
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import Dict, Any
import asyncio
import json
import uuid
from datetime import datetime

from models import (
    CreateReportRequest, 
    TaskState, 
    TaskStatus,
    StatusResponse,
    Report
)
from memory import memory_store
from graph import run_research_workflow
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="ScholarSynth API",
    description="Multi-agent deep research system with LangGraph and Gemini",
    version="1.0.0"
)

# CORS middleware
# Get allowed origins from environment variable or use defaults
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_str:
    # Strip whitespace and filter empty strings
    allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]
else:
    # Default to wildcard for production if ALLOWED_ORIGINS not set
    # For security, set ALLOWED_ORIGINS env var with specific domains
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True if allowed_origins != ["*"] else False,  # Can't use credentials with wildcard
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "ScholarSynth",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/api/report", response_model=Dict[str, str])
async def create_report(
    request: CreateReportRequest,
    background_tasks: BackgroundTasks
):
    """
    Create a new research report task.
    
    Args:
        request: Research query
        
    Returns:
        task_id and status
    """
    # Generate unique task ID
    task_id = str(uuid.uuid4())
    
    # Create initial task state
    task_state = TaskState(
        task_id=task_id,
        query=request.query,
        status=TaskStatus.PLANNING,
        current_step="Initializing research workflow...",
        progress_percentage=0
    )
    
    # Store in memory
    memory_store.create(task_state)
    
    # Run workflow in background
    background_tasks.add_task(
        run_research_workflow,
        task_state,
        memory_store
    )
    
    return {
        "task_id": task_id,
        "status": "started",
        "message": "Research workflow initiated"
    }


@app.get("/api/report/{task_id}/status", response_model=StatusResponse)
async def get_report_status(task_id: str):
    """
    Get status of a research task.
    
    Args:
        task_id: Task identifier
        
    Returns:
        Current status and progress
    """
    task_state = memory_store.get(task_id)
    
    if not task_state:
        raise HTTPException(status_code=404, detail="Task not found")
    
    completed = sum(1 for q in task_state.sub_questions if q.status == "completed")
    
    return StatusResponse(
        task_id=task_id,
        status=task_state.status,
        current_step=task_state.current_step,
        progress_percentage=task_state.progress_percentage,
        sub_questions_count=len(task_state.sub_questions),
        completed_questions=completed
    )


@app.get("/api/report/{task_id}")
async def get_report(task_id: str):
    """
    Get the final research report.
    
    Args:
        task_id: Task identifier
        
    Returns:
        Complete task state with report
    """
    task_state = memory_store.get(task_id)
    
    if not task_state:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Return full state
    return task_state.model_dump()


@app.get("/api/report/{task_id}/stream")
async def stream_report_progress(task_id: str):
    """
    Server-Sent Events stream for real-time progress updates.
    
    Args:
        task_id: Task identifier
        
    Returns:
        SSE stream of status updates
    """
    task_state = memory_store.get(task_id)
    
    if not task_state:
        raise HTTPException(status_code=404, detail="Task not found")
    
    async def event_generator():
        """Generate SSE events"""
        last_progress = -1
        
        while True:
            # Get current state
            current_state = memory_store.get(task_id)
            
            if not current_state:
                yield f"data: {json.dumps({'error': 'Task not found'})}\n\n"
                break
            
            # Send update if progress changed
            if current_state.progress_percentage != last_progress:
                last_progress = current_state.progress_percentage
                
                event_data = {
                    "status": current_state.status.value,
                    "current_step": current_state.current_step,
                    "progress_percentage": current_state.progress_percentage,
                    "sub_questions_count": len(current_state.sub_questions),
                    "completed_questions": sum(1 for q in current_state.sub_questions if q.status == "completed")
                }
                
                yield f"data: {json.dumps(event_data)}\n\n"
            
            # If task is done or failed, send final event and close
            if current_state.status in [TaskStatus.DONE, TaskStatus.FAILED]:
                yield f"data: {json.dumps({'status': current_state.status.value, 'done': True})}\n\n"
                break
            
            # Wait before next check
            await asyncio.sleep(0.5)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.delete("/api/report/{task_id}")
async def delete_report(task_id: str):
    """
    Delete a research task from memory.
    
    Args:
        task_id: Task identifier
        
    Returns:
        Success message
    """
    deleted = memory_store.delete(task_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"message": "Task deleted successfully"}


@app.get("/api/reports")
async def list_reports():
    """
    List all active research tasks.
    
    Returns:
        List of all tasks in memory
    """
    all_tasks = memory_store.list_all()
    
    # Return summary of each task
    summaries = []
    for task_id, task_state in all_tasks.items():
        summaries.append({
            "task_id": task_id,
            "query": task_state.query,
            "status": task_state.status.value,
            "progress_percentage": task_state.progress_percentage,
            "created_at": task_state.created_at.isoformat(),
            "has_report": task_state.report is not None
        })
    
    return {"tasks": summaries, "count": len(summaries)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
