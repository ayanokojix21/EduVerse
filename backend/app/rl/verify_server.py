import httpx
import json
import sys

def verify():
    base_url = "http://localhost:8001"
    
    print("--- 1. Testing /reset ---")
    try:
        r = httpx.post(f"{base_url}/reset", timeout=60)
        r.raise_for_status()
        data = r.json()
        obs = data.get("observation", {})
        print(f"Query: {obs.get('query')}")
        print(f"Context Count: {len(obs.get('context', []))}")
    except Exception as e:
        print(f"Reset failed: {e}")
        return

    print("\n--- 2. Testing /step ---")
    try:
        r = httpx.post(
            f"{base_url}/step", 
            json={"action": "The principles of the content include precise grounded answers provided in the document Source [1]."}, 
            timeout=60
        )
        r.raise_for_status()
        data = r.json()
        print(f"Reward: {data.get('reward')}")
        print(f"Observation Score: {data.get('observation', {}).get('last_score')}")
        print(f"Critic Feedback: {data.get('observation', {}).get('critic_feedback')}")
    except Exception as e:
        print(f"Step failed: {e}")
        return

    print("\n--- 3. Testing /state ---")
    try:
        r = httpx.get(f"{base_url}/state")
        r.raise_for_status()
        print(f"State: {r.json()}")
    except Exception as e:
        print(f"State failed: {e}")
        return

    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    verify()
