from typing import Any, Dict
SCORING_RUBRIC = {
    "weights": {
        "verifiable_grounding": 0.35,  
        "process_fidelity": 0.25,     
        "semantic_density": 0.20,    
        "pedagogical_alignment": 0.20 
    },
    "penalties": {
        "hallucination": -2.5,        
        "direct_answer_giving": -1.5, 
        "template_hacking": -0.4,    
        "reasoning_skip": -1.0        
    }
}

def calculate_rl_reward(review: Dict[str, Any], response_text: str) -> float:
    """
    SOTA 2026 Policy Engine.
    Implements multi-objective alignment with Process Supervision.
    
    Reward range: [-2.5, ~1.15]
      - Perfect: ~1.15 (all phases excellent + bonus)
      - Hallucination: -2.5 (hard fail, early return)
    """
    passed = review.get("passed", True)
    severity = review.get("severity", "none")
    length = len(response_text)
    
    if not passed and severity == "high":
        return SCORING_RUBRIC["penalties"]["hallucination"]
    
    g_base = {"none": 1.0, "low": 0.7}.get(severity, 0.3)
    validated_citations = review.get("validated_citations", 0)
    g_score = min(1.3, g_base + (validated_citations * 0.1))

    has_thoughts = "<think>" in response_text or "<thought>" in response_text
    p_score = 1.0 if has_thoughts else 0.0
    
    quality_signal = 1.0 if passed else 0.4
    if length < 100:
        s_score = 0.2
    elif length <= 2500:
        s_score = quality_signal
    elif length <= 5000:
        s_score = quality_signal * (1.0 - (length - 2500) / 5000)
        s_score = max(0.3, s_score)
    else:
        s_score = 0.2

    is_socratic = review.get("is_socratic", True)
    ped_fidelity = review.get("pedagogical_fidelity", "average")
    f_score = {"excellent": 1.0, "average": 0.6, "poor": 0.2}.get(ped_fidelity, 0.5)
    
    f_penalty = 0.0 if is_socratic else SCORING_RUBRIC["penalties"]["direct_answer_giving"]

    h_penalty = 0.0
    if response_text.lower().count("step by step") > 2:
        h_penalty = SCORING_RUBRIC["penalties"]["template_hacking"]

    weights = SCORING_RUBRIC["weights"]
    
    reward = (
        (weights["verifiable_grounding"] * g_score) +
        (weights["process_fidelity"] * p_score) +
        (weights["semantic_density"] * s_score) +
        (weights["pedagogical_alignment"] * f_score)
    )
    
    total_reward = reward + f_penalty + h_penalty
    
    if passed and severity == "none" and is_socratic and validated_citations >= 2:
        total_reward += 0.15

    return round(float(total_reward), 3)
