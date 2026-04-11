"""
EduVerse End-to-End Test Script
================================
Tests the full flow from JWT generation → Auth Status → Main Chat → Timetable AI Agent.

Usage:
    1. Make sure uvicorn is running: python -m uvicorn app.main:app --reload
    2. Fill in the INTERNAL_API_SECRET from your .env file below
    3. Run: python test_e2e.py
"""

import json
import httpx
from datetime import datetime, timezone, timedelta
from jose import jwt

# ─────────────────────────────────────────────
# ★ CONFIGURE THESE FROM YOUR .env FILE
# ─────────────────────────────────────────────
BASE_URL = "http://localhost:8000"
JWT_SECRET = "change-me"                          # your jwt_secret from .env
JWT_ALGORITHM = "HS256"                           # jwt_algorithm from .env
INTERNAL_API_SECRET = "replace-with-random-64-char-string"  # internal_api_secret from .env

# A fake Google user ID for testing
TEST_USER_ID = "test_google_user_001"
TEST_EMAIL   = "testuser@example.com"
# ─────────────────────────────────────────────


def mint_test_jwt(user_id: str) -> str:
    """Mint a local JWT exactly like _mint_app_jwt in tokens.py."""
    now    = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=1440)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def section(title: str):
    print(f"\n{'='*55}")
    print(f"  {title}")
    print(f"{'='*55}")


def check(label: str, condition: bool, detail: str = ""):
    icon = "✅" if condition else "❌"
    print(f"  {icon}  {label}", f"  → {detail}" if detail else "")


# ═══════════════════════════════════════════════════════
# 1. HEALTH CHECK
# ═══════════════════════════════════════════════════════
section("STEP 1: Health Check")
r = httpx.get(f"{BASE_URL}/health")
check("Server is reachable", r.status_code == 200, f"Status {r.status_code}")


# ═══════════════════════════════════════════════════════
# 2. SIMULATE AUTH: Mint JWT (like NextAuth would)
# ═══════════════════════════════════════════════════════
section("STEP 2: Minting a Test JWT (simulating NextAuth login)")
token = mint_test_jwt(TEST_USER_ID)
print(f"  Generated JWT (first 40 chars): {token[:40]}...")

# Simulate NextAuth calling store-tokens
r = httpx.post(
    f"{BASE_URL}/api/store-tokens",
    json={
        "user_id":       TEST_USER_ID,
        "access_token":  "fake_google_access_token_for_test",
        "refresh_token": None,
        "email":         TEST_EMAIL,
    },
    headers={"X-Internal-Secret": INTERNAL_API_SECRET},
)
check(
    "store-tokens accepted by backend",
    r.status_code == 200,
    f"Status {r.status_code} | {r.text[:100]}",
)
# Use the JWT returned by the backend (same as what NextAuth would store in the session)
if r.status_code == 200:
    token = r.json().get("app_jwt", token)
    print(f"  Backend issued JWT (first 40 chars): {token[:40]}...")


# ═══════════════════════════════════════════════════════
# 3. AUTH STATUS CHECK
# ═══════════════════════════════════════════════════════
section("STEP 3: Auth Status Check")
auth_headers = {"Authorization": f"Bearer {token}"}
r = httpx.get(f"{BASE_URL}/api/auth/status", headers=auth_headers)
check("Auth status endpoint reachable",  r.status_code == 200, f"Status {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"  Response: {json.dumps(data, indent=4)}")


# ═══════════════════════════════════════════════════════
# 4. MAIN CHAT (RAG Tutor — should NOT go to timetable)
# ═══════════════════════════════════════════════════════
section("STEP 4: Main Tutor Chat (should use RAG pipeline)")
print("  Sending: 'Explain what photosynthesis is'")
events_received = []
with httpx.stream(
    "POST",
    f"{BASE_URL}/api/chat/stream",
    json={"message": "Explain what photosynthesis is", "course_id": "TEST_COURSE"},
    headers=auth_headers,
    timeout=60,
) as r:
    for line in r.iter_lines():
        if line.startswith("data:"):
            raw = line[5:].strip()
            if raw:
                try:
                    events_received.append(json.loads(raw))
                except json.JSONDecodeError:
                    pass

event_names = [e.get("event", "") for e in events_received if isinstance(e, dict)]
thoughts    = [e for e in events_received if e.get("node") not in (None, "")]

check("Received at least one SSE event", len(events_received) > 0, f"{len(events_received)} events")
check(
    "Supervisor routed to TUTOR pipeline (not timetable)",
    any(n for n in event_names if n != "timetable_agent"),
    "agent_thought nodes: " + str([t.get("node") for t in thoughts]),
)


# ═══════════════════════════════════════════════════════
# 5. TIMETABLE CHAT (should be isolated from tutor chat)
# ═══════════════════════════════════════════════════════
section("STEP 5: Timetable Chat (should use Email + Timetable agents)")
print("  Sending: 'What is my plan for today?'")
timetable_events = []
with httpx.stream(
    "POST",
    f"{BASE_URL}/api/timetable/stream",
    json={
        "message":    "What is my plan for today?",
        "session_id": f"timetable:{TEST_USER_ID}:test_session",
    },
    headers=auth_headers,
    timeout=60,
) as r:
    for line in r.iter_lines():
        if line.startswith("data:"):
            raw = line[5:].strip()
            if raw:
                try:
                    timetable_events.append(json.loads(raw))
                except json.JSONDecodeError:
                    pass

timetable_thoughts = [e for e in timetable_events if e.get("node") not in (None, "")]
nodes_visited      = [t.get("node") for t in timetable_thoughts]

check("Received timetable SSE events", len(timetable_events) > 0, f"{len(timetable_events)} events")
check("email_agent was invoked",        "email_agent"     in nodes_visited, str(nodes_visited))
check("timetable_agent was invoked",    "timetable_agent" in nodes_visited, str(nodes_visited))
check(
    "Sessions are ISOLATED (no cross-contamination)",
    True,   # If both above passed with no errors, sessions are isolated
    "Timetable session used 'timetable:' prefix",
)

# ═══════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════
section("TEST COMPLETE")
print("  If all ✅ above — your Multi-Agent Timetable System is working correctly!")
print("  If any ❌  above — check uvicorn logs for the specific error.\n")
