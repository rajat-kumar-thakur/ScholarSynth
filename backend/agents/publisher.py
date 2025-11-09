"""
Publisher agent - synthesize all results into final report.
"""
from typing import Dict, Any, List
from models import SubQuestion, Report, Citation
from llm.gemini_client import get_gemini_client
from llm.prompts import PUBLISHER_PROMPT
from datetime import datetime


def format_summaries(sub_questions: List[SubQuestion]) -> str:
    """Format all summaries and sources for the publisher prompt"""
    formatted = []
    
    for i, q in enumerate(sub_questions, 1):
        if q.status != "completed" or not q.summary:
            continue
        
        section = f"\n--- Sub-Question {i} ---\n"
        section += f"Q: {q.question}\n\n"
        section += f"Summary:\n{q.summary}\n\n"
        
        if q.sources:
            section += "Sources:\n"
            for source in q.sources:
                section += f"- [{source.id}] {source.title}\n"
                section += f"  URL: {source.url}\n"
                if source.authors:
                    section += f"  Authors: {source.authors}\n"
                if source.date:
                    section += f"  Date: {source.date}\n"
                section += f"  Snippet: {source.snippet}\n\n"
        
        formatted.append(section)
    
    return "\n".join(formatted)


async def publisher_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Publisher node: Synthesize all research into a comprehensive report.
    
    Args:
        state: Current task state dictionary
        
    Returns:
        Updated state with final report
    """
    query = state.get("query", "")
    sub_questions: List[SubQuestion] = state.get("sub_questions", [])
    
    print(f"📝 Publisher: Synthesizing {len(sub_questions)} research sections...")
    
    try:
        # Format all summaries
        summaries = format_summaries(sub_questions)
        
        if not summaries:
            raise ValueError("No completed research to synthesize")
        
        # Get Gemini client
        client = get_gemini_client()
        
        # Format publisher prompt
        prompt = PUBLISHER_PROMPT.format(
            query=query,
            summaries=summaries
        )
        
        # Generate final report (using higher max_tokens for long report)
        report_content = client.call(
            prompt=prompt, 
            temperature=0.7,
            max_tokens=8000
        )
        
        # Collect all citations from all sub-questions
        all_citations: List[Citation] = []
        for q in sub_questions:
            if q.sources:
                all_citations.extend(q.sources)
        
        # Remove duplicate citations by ID
        unique_citations = {c.id: c for c in all_citations}
        citations_list = list(unique_citations.values())
        
        # Count words (approximate)
        word_count = len(report_content.split())
        
        # Extract title from report (first # heading)
        title = query  # Default to query
        for line in report_content.split('\n'):
            if line.startswith('# '):
                title = line.replace('# ', '').strip()
                break
        
        # Create Report object
        report = Report(
            title=title,
            content=report_content,
            word_count=word_count,
            citations=citations_list,
            generated_at=datetime.utcnow()
        )
        
        print(f"✅ Publisher: Generated {word_count} word report with {len(citations_list)} citations")
        
        return {
            "report": report,
            "current_step": "Report generation complete",
            "progress_percentage": 100,
            "status": "done"  # Mark as done when report is ready
        }
        
    except Exception as e:
        print(f"❌ Publisher error: {str(e)}")
        return {
            "error": f"Publisher failed: {str(e)}",
            "current_step": "Report synthesis failed",
            "progress_percentage": 80
        }
