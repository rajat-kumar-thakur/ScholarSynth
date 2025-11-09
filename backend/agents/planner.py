"""
Planner agent - generates sub-questions from user query.
"""
from typing import Dict, Any
from models import TaskState, SubQuestion
from llm.gemini_client import get_gemini_client
from llm.prompts import PLANNER_PROMPT


async def planner_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Planner node: Generate 6-10 sub-questions from the user query.
    
    Args:
        state: Current task state dictionary
        
    Returns:
        Updated state with sub_questions populated
    """
    print(f"🔍 Planner: Analyzing query: {state['query']}")
    
    try:
        # Get Gemini client
        client = get_gemini_client()
        
        # Format prompt with user query
        prompt = PLANNER_PROMPT.format(query=state["query"])
        
        # Call Gemini to generate sub-questions
        response = client.call_json(prompt=prompt, temperature=0.8)
        
        # Parse sub-questions from response
        if "sub_questions" not in response:
            raise ValueError("Response missing 'sub_questions' field")
        
        sub_questions_list = response["sub_questions"]
        
        # Convert to SubQuestion objects
        sub_questions = [
            SubQuestion(question=q, status="pending")
            for q in sub_questions_list
        ]
        
        print(f"✅ Planner: Generated {len(sub_questions)} sub-questions")
        
        return {
            "sub_questions": sub_questions,
            "status": "planning",
            "current_step": f"Planning complete - {len(sub_questions)} research questions generated",
            "progress_percentage": 20
        }
        
    except Exception as e:
        print(f"❌ Planner error: {str(e)}")
        return {
            "error": f"Planner failed: {str(e)}",
            "current_step": "Planning failed",
            "progress_percentage": 0
        }
