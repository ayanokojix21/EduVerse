import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

def calculate_rl_reward(review: Dict[str, Any], response_text: str) -> float:
    """
    Calculates a multi-dimensional RL reward based on Critic review.
    
    Weights:
    - Grounding (40%): Pass/Fail and Severity of hallucinations.
    - Conciseness (30%): Efficiency of the response.
    - Quality (30%): General helpfulness and adherence to student query.
    """
    passed = review.get("passed", False)
    severity = review.get("severity", "high")
    
    if not passed and severity == "high":
        return -1.0 # Critical Hallucination penalty
    
    # 1. Grounding Score (40%)
    g_score = 1.0 if severity == "none" else 0.5
    
    # 2. Conciseness Score (30%)
    resp_len = len(response_text)
    c_score = max(0.0, 1.0 - (resp_len / 4000))
    
    # 3. Quality Score (30%)
    q_score = 1.0 if passed else 0.2
    
    reward = (0.4 * g_score) + (0.3 * c_score) + (0.3 * q_score)
    
    # Perfect grounding bonus
    if passed and severity == "none":
        reward = min(1.0, reward + 0.1)
        
    return reward
