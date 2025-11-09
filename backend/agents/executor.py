"""
Executor agent - parallel retrieval + summary + citations for each sub-question.
"""
from typing import Dict, Any, List
from models import SubQuestion, Citation
from llm.gemini_client import get_gemini_client
from llm.prompts import EXECUTOR_PROMPT
import asyncio


async def execute_single_question(question: SubQuestion, index: int) -> SubQuestion:
    """
    Execute research for a single sub-question.
    
    Args:
        question: SubQuestion to research
        index: Index for citation numbering
        
    Returns:
        Updated SubQuestion with summary and sources
    """
    print(f"  🔎 Executor [{index}]: Researching: {question.question[:60]}...")
    
    try:
        question.status = "processing"
        
        # Get Gemini client
        client = get_gemini_client()
        
        # Format prompt with question
        prompt = EXECUTOR_PROMPT.format(question=question.question)
        
        # Call Gemini to get research summary and sources
        response = client.call_json(prompt=prompt, temperature=0.7, max_tokens=2000)
        
        # Parse response
        summary = response.get("summary", "")
        facts = response.get("facts", [])
        sources_data = response.get("sources", [])
        
        # Create Citation objects
        citations = []
        for i, source in enumerate(sources_data):
            citation = Citation(
                id=f"S{index * 3 + i + 1}",  # Unique citation ID
                title=source.get("title", "Unknown Title"),
                url=source.get("url", ""),
                authors=source.get("authors"),
                date=source.get("date"),
                snippet=source.get("snippet", "")
            )
            citations.append(citation)
        
        # Update question with results
        question.summary = summary
        question.sources = citations
        question.status = "completed"
        
        print(f"  ✅ Executor [{index}]: Completed with {len(citations)} sources")
        
        return question
        
    except Exception as e:
        print(f"  ❌ Executor [{index}] error: {str(e)}")
        question.status = "failed"
        question.summary = f"Failed to research: {str(e)}"
        return question


async def executor_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executor node: Process all sub-questions in parallel.
    
    Args:
        state: Current task state dictionary
        
    Returns:
        Updated state with completed sub_questions
    """
    sub_questions: List[SubQuestion] = state.get("sub_questions", [])
    
    if not sub_questions:
        return {
            "error": "No sub-questions to execute",
            "current_step": "Execution failed - no questions",
            "progress_percentage": 20
        }
    
    print(f"🔬 Executor: Processing {len(sub_questions)} questions in parallel...")
    
    try:
        # Execute all questions in parallel
        tasks = [
            execute_single_question(q, i) 
            for i, q in enumerate(sub_questions)
        ]
        
        # Wait for all to complete
        completed_questions = await asyncio.gather(*tasks, return_exceptions=False)
        
        # Count successful completions
        successful = sum(1 for q in completed_questions if q.status == "completed")
        
        print(f"✅ Executor: Completed {successful}/{len(sub_questions)} questions successfully")
        
        return {
            "sub_questions": completed_questions,
            "status": "executing",
            "current_step": f"Research complete - {successful}/{len(sub_questions)} questions answered",
            "progress_percentage": 70  # Increased from 60 to show progress
        }
        
    except Exception as e:
        print(f"❌ Executor error: {str(e)}")
        return {
            "error": f"Executor failed: {str(e)}",
            "current_step": "Research execution failed",
            "progress_percentage": 40
        }
