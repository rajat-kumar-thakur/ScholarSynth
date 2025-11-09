"""
LangGraph StateGraph setup - wires planner → executor → publisher workflow.
"""
from typing import TypedDict, Dict, Any, List, Optional
from langgraph.graph import StateGraph, END
from models import TaskState, TaskStatus, SubQuestion, Report
from agents.planner import planner_node
from agents.executor import executor_node
from agents.publisher import publisher_node
import asyncio


class GraphState(TypedDict):
    """State definition for the research graph"""
    task_id: str
    query: str
    status: str
    sub_questions: List[Dict[str, Any]]
    report: Optional[Dict[str, Any]]
    error: Optional[str]
    current_step: str
    progress_percentage: int


def should_continue_to_executor(state: GraphState) -> str:
    """Conditional edge: check if planner succeeded"""
    if state.get("error"):
        return "end"
    if not state.get("sub_questions"):
        return "end"
    return "executor"


def should_continue_to_publisher(state: GraphState) -> str:
    """Conditional edge: check if executor succeeded"""
    if state.get("error"):
        return "end"
    
    sub_questions = state.get("sub_questions", [])
    if not sub_questions:
        return "end"
    
    # Check if at least some questions completed
    completed = sum(1 for q in sub_questions if isinstance(q, dict) and q.get("status") == "completed")
    if completed == 0:
        return "end"
    
    return "publisher"


def create_research_graph() -> StateGraph:
    """
    Create and compile the LangGraph workflow.
    
    Graph structure:
        START → planner → executor → publisher → END
    """
    # Initialize graph
    workflow = StateGraph(GraphState)
    
    # Add nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("publisher", publisher_node)
    
    # Add edges
    workflow.set_entry_point("planner")
    
    # Planner → Executor (with conditional check)
    workflow.add_conditional_edges(
        "planner",
        should_continue_to_executor,
        {
            "executor": "executor",
            "end": END
        }
    )
    
    # Executor → Publisher (with conditional check)
    workflow.add_conditional_edges(
        "executor",
        should_continue_to_publisher,
        {
            "publisher": "publisher",
            "end": END
        }
    )
    
    # Publisher → END
    workflow.add_edge("publisher", END)
    
    # Compile graph
    return workflow.compile()


# Global compiled graph instance
research_graph = create_research_graph()


async def run_research_workflow(task_state: TaskState, memory_store) -> TaskState:
    """
    Execute the complete research workflow for a task.
    
    Args:
        task_state: Initial task state
        memory_store: Memory store to update during execution
        
    Returns:
        Updated task state after workflow completion
    """
    print(f"\n{'='*60}")
    print(f"🚀 Starting research workflow for task: {task_state.task_id}")
    print(f"📋 Query: {task_state.query}")
    print(f"{'='*60}\n")
    
    # Convert TaskState to GraphState dict
    initial_state: GraphState = {
        "task_id": task_state.task_id,
        "query": task_state.query,
        "status": TaskStatus.PLANNING.value,
        "sub_questions": [],
        "report": None,
        "error": None,
        "current_step": "Starting research...",
        "progress_percentage": 0
    }
    
    try:
        # Update status to planning
        task_state.status = TaskStatus.PLANNING
        task_state.update_progress("Planning research questions...", 5)
        memory_store.update(task_state.task_id, task_state)
        
        # Run the graph
        final_state = await research_graph.ainvoke(initial_state)
        
        # Update task state from final graph state
        if final_state.get("error"):
            task_state.status = TaskStatus.FAILED
            task_state.error = final_state["error"]
            task_state.update_progress(f"Failed: {final_state['error']}", 0)
        else:
            # Update sub_questions
            if final_state.get("sub_questions"):
                task_state.sub_questions = [
                    SubQuestion(**q) if isinstance(q, dict) else q
                    for q in final_state["sub_questions"]
                ]
            
            # Update report
            if final_state.get("report"):
                report_data = final_state["report"]
                task_state.report = Report(**report_data) if isinstance(report_data, dict) else report_data
                task_state.status = TaskStatus.DONE
            
            # Update progress
            task_state.update_progress(
                final_state.get("current_step", "Complete"),
                final_state.get("progress_percentage", 100)
            )
        
        # Save final state
        memory_store.update(task_state.task_id, task_state)
        
        print(f"\n{'='*60}")
        print(f"✅ Workflow complete for task: {task_state.task_id}")
        print(f"📊 Status: {task_state.status}")
        print(f"{'='*60}\n")
        
        return task_state
        
    except Exception as e:
        print(f"\n❌ Workflow error for task {task_state.task_id}: {str(e)}\n")
        task_state.status = TaskStatus.FAILED
        task_state.error = str(e)
        task_state.update_progress(f"Workflow failed: {str(e)}", 0)
        memory_store.update(task_state.task_id, task_state)
        return task_state
