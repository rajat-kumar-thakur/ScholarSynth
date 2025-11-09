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
        print("⚠️ Skipping publisher: error detected")
        return "end"
    
    sub_questions = state.get("sub_questions", [])
    if not sub_questions:
        print("⚠️ Skipping publisher: no sub_questions")
        return "end"
    
    # Check if at least some questions completed
    # Handle both dict and SubQuestion objects
    completed = 0
    for q in sub_questions:
        if isinstance(q, dict):
            if q.get("status") == "completed":
                completed += 1
        elif hasattr(q, 'status'):
            if q.status == "completed":
                completed += 1
    
    print(f"📊 Publisher check: {completed}/{len(sub_questions)} questions completed")
    
    if completed == 0:
        print("⚠️ Skipping publisher: no completed questions")
        return "end"
    
    print("✅ Proceeding to publisher")
    return "publisher"


def create_research_graph():
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
        
        # Run the graph with streaming to capture intermediate states
        final_state = None
        
        # Use astream to get updates after each node completes
        # astream yields updates in format: {node_name: node_output}
        async for state_update in research_graph.astream(initial_state):
            # Extract the actual state data from the node output
            # state_update format: {node_name: {...node_output...}}
            print(f"📡 Graph state update received: {list(state_update.keys())}")
            
            # Get the node output (the actual state data)
            node_output = None
            for node_name, output in state_update.items():
                node_output = output
                print(f"  └─ Processing node: {node_name}")
                break
            
            if not node_output:
                continue
                
            # Update task state with the node output
            if node_output.get("status"):
                # Map graph status to TaskStatus enum
                status_map = {
                    "planning": TaskStatus.PLANNING,
                    "executing": TaskStatus.EXECUTING,
                    "publishing": TaskStatus.PUBLISHING,
                    "done": TaskStatus.DONE
                }
                task_state.status = status_map.get(
                    node_output["status"],
                    task_state.status
                )
            
            # Update progress
            if node_output.get("current_step") or node_output.get("progress_percentage") is not None:
                task_state.update_progress(
                    node_output.get("current_step", task_state.current_step),
                    node_output.get("progress_percentage", task_state.progress_percentage)
                )
            
            # Update sub_questions if available
            if node_output.get("sub_questions"):
                task_state.sub_questions = [
                    SubQuestion(**q) if isinstance(q, dict) else q
                    for q in node_output["sub_questions"]
                ]
            
            # Update report if available
            if node_output.get("report"):
                report_data = node_output["report"]
                task_state.report = Report(**report_data) if isinstance(report_data, dict) else report_data
                task_state.status = TaskStatus.DONE
                task_state.update_progress("Research complete!", 100)
            
            # Handle errors
            if node_output.get("error"):
                task_state.status = TaskStatus.FAILED
                task_state.error = node_output["error"]
            
            # Persist to memory store after each state update
            memory_store.update(task_state.task_id, task_state)
            print(f"  └─ Memory store updated: {task_state.status.value}, {task_state.progress_percentage}%, sub_questions: {len(task_state.sub_questions)}")
            
            final_state = node_output
        
        # Final update after workflow completes
        if final_state:
            if final_state.get("error"):
                task_state.status = TaskStatus.FAILED
                task_state.error = final_state["error"]
                task_state.update_progress(f"Failed: {final_state['error']}", 0)
            elif task_state.status != TaskStatus.DONE:
                # If we completed without errors but status isn't DONE, check if we have a report
                if task_state.report:
                    task_state.status = TaskStatus.DONE
                    task_state.update_progress("Research complete!", 100)
        
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
