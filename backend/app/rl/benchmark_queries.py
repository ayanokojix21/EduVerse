"""
Baseline benchmark queries for the EduVerse RL Environment.
These represent typical student questions across various difficulty levels.
"""

BENCHMARK_QUERIES = [
    {
        "id": "q1",
        "query": "What are the core principles of the subject discussed in the document?",
        "topic": "General Overview",
        "difficulty": "easy"
    },
    {
        "id": "q2",
        "query": "Explain the step-by-step process of the main algorithm or method described.",
        "topic": "Process/Methodology",
        "difficulty": "medium"
    },
    {
        "id": "q3",
        "query": "Compare and contrast the two major theories mentioned in the text.",
        "topic": "Comparative Analysis",
        "difficulty": "hard"
    },
    {
        "id": "q4",
        "query": "Provide a concrete example or use case for the concept of 'X' based on the sources.",
        "topic": "Application",
        "difficulty": "medium"
    },
    {
        "id": "q5",
        "query": "Summarize the historical context that led to the development of this field.",
        "topic": "History/Context",
        "difficulty": "easy"
    },
    {
        "id": "q6",
        "query": "Identify the specific page where the author lists 'X' as a primary constraint and explain its implications.",
        "topic": "Precision Retrieval",
        "difficulty": "hard"
    }
]

async def generate_adversarial_queries(context_docs: list[dict]) -> list[dict]:
    """
    Experimental: Uses an LLM to generate 'trick' questions based on provided 
    context to test agent limits.
    """
    from app.utils.llm_pool import RoundRobinLLM
    llm = RoundRobinLLM.for_role("fast", temperature=0.7)
    
    # Simple strategy: Suggest a meta-question about the source's limitations
    return [
        {
            "query": "Explain what this source CONTRADICTS regarding the main theory, if anything.",
            "difficulty": "hard",
            "topic": "Adversarial Analysis"
        }
    ]
