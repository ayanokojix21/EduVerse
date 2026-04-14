import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

def calculate_rl_reward(review: Dict[str, Any], response_text: str) -> float:
    """
    Calculates a balanced RL reward.
    
    Weights:
    - Grounding (40%): Pass/Fail and Severity.
    - Conciseness (30%): Efficiency.
    - Quality (30%): Helpfulness.
    """
    passed = review.get("passed", True)
    severity = review.get("severity", "none")
    issues = review.get("issues", [])
    
    # Only triggered if the Critic actively FAILED the response AND found high-severity issues.
    if not passed and severity == "high" and len(issues) > 0:
        return -1.0
    
    # 1. Grounding Score (40%)
    # none = 1.0, low (common knowledge/missing citation) = 0.8, high (but passed) = 0.4
    if severity == "none":
        g_score = 1.0
    elif severity == "low":
        g_score = 0.8
    else:
        g_score = 0.4
    
    # 2. Conciseness Score (30%)
    resp_len = len(response_text)
    c_score = max(0.0, 1.0 - (resp_len / 5000))
    
    # 3. Quality Score (30%)
    # Helpful answers that passed are rewarded.
    q_score = 1.0 if passed else 0.5
    
    reward = (0.4 * g_score) + (0.3 * c_score) + (0.3 * q_score)
    
    # Perfect grounding bonus
    if passed and severity == "none":
        reward = min(1.0, reward + 0.1)
        
    return round(reward, 3)
