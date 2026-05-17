<p align="center">
  <h1 align="center">EduVerse</h1>
  <p align="center">
    Multi-Agent System built on Gemma 4 · Socratic by design · Self-improving through DPO
  </p>
  <p align="center">
    <a href="#">🎥 Video Demo</a> · <a href="#">🌐 Live Demo</a> · <a href="./ARCHITECTURE.md">📐 Architecture</a> · <a href="https://www.kaggle.com/competitions/gemma-4-good-hackathon">🏆 Hackathon</a>
  </p>
</p>

---

## The Problem

260 million students are enrolled in higher education worldwide. Most use AI tools that do one thing: spit out answers. The student copies, submits, learns nothing. The tool enables academic dishonesty at scale.

Meanwhile, every professor uploads PDFs, lecture slides, and assignments to Google Classroom - and none of it gets connected to the AI. Students ask ChatGPT about photosynthesis and get a generic Wikipedia response when they should be getting an explanation grounded in *what their professor actually taught*.

EduVerse was built to fix both problems.

## What It Does

EduVerse syncs with a student's Google Classroom, ingests their actual course materials, and uses a **multi-agent system of 15+ specialized Gemma 4 nodes** to teach through questions, analogies, and conceptual scaffolding - never direct answers.

Three agent swarms handle distinct educational workflows:

**RAG Tutor** - Socratic explanations grounded in course materials. The system retrieves relevant docs, builds a chain-of-thought reasoning trace, then drafts an explanation that guides the student to the answer through questions and analogies. An adversarial validator fact-checks every claim against the source documents. If it finds hallucinations, it sends the draft back for revision - automatically.

**Quiz Engine** - Parallel MCQ generation mapped to Bloom's taxonomy. Three drafter workers run simultaneously via LangGraph's `Send()` API, each producing a question with intentionally designed distractors. A reviewer quality-gates the set and can reject + regenerate the entire batch.

**Feedback Analyst** - Root-cause analysis of student answers. A diagnostician agent uses code execution and web search tools to verify student work, then a mentor agent scores the feedback through a growth-mindset lens. If the feedback is too harsh, it loops back for revision.

Every swarm feeds into a **Critic Agent** that performs a final quality audit. If the critic rejects the output, the entire graph re-runs from the orchestrator - up to 2 self-correction cycles. A triple-layer guardrail system (input moderator -> integrity guard -> output shield) ensures no direct answers, no PII leaks, and no prompt injection.

The entire reasoning process is transparent. Every agent's `<think>` trace is extracted and rendered in an **X-Ray panel** in the UI, so the student can see exactly how the AI reached its response.

## Why Gemma 4

We didn't just swap in Gemma 4 as a drop-in replacement. The architecture was designed around specific Gemma 4 capabilities:

| Capability | How We Use It | Where |
|-----------|--------------|-------|
| **Native `<think>` CoT** | Every pedagogical agent triggers explicit reasoning with `<think>` tokens. We extract these traces for the X-Ray transparency panel. | Generator, Diagnostician, all Guardrails |
| **Structured Output** | Every agent uses `with_structured_output()` for typed schemas - `PlannerOutput`, `QuizQuestion`, `CriticOutput`, `SafetyOutput`, etc. No regex parsing. | All 15+ nodes |
| **Multimodal Vision** | Students can upload photos of diagrams, handwritten problems, or textbook pages. The generator processes image+text natively. | RAG Generator, Quiz Drafters, Diagnostician |
| **Function Calling** | Validator and Reviewer agents autonomously call web_search and python_repl tools to fact-check claims and verify math. | Validator, Reviewer, Diagnostician |
| **MoE Efficiency** | The 26B-A4B model activates only 4B params per token - perfect for parallel execution across 3+ concurrent drafters without blowing the latency budget. | Quiz Drafters, Critics, Guardrails |

### Model Routing

We use three Gemma 4 variants, matched to task complexity:

```
┌────────────────────────────────────────────────────────────┐
│  Gemma 4 26B-A4B-IT (MoE)     - 4B active / 26B total    │
│  Used for: Routing, guardrails, validators, quiz drafters │
│  Why: Fast. 4B active params = near-edge latency.         │
├────────────────────────────────────────────────────────────┤
│  Gemma 4 31B-IT (Dense)       - Full 31B parameters       │
│  Used for: RAG generation, feedback root-cause analysis   │
│  Why: Maximum reasoning depth for pedagogical tasks.      │
├────────────────────────────────────────────────────────────┤
│  Gemini 2.5 Pro (Teacher)     - Background only           │
│  Used for: DPO distillation, evaluation judging           │
│  Why: Gold-standard for offline training data. Never on   │
│       the live student path.                              │
└────────────────────────────────────────────────────────────┘
```

All chains include a Gemini Flash fallback via `.with_fallbacks()` - if the Gemma 4 endpoint returns a 500, the system degrades gracefully rather than crashing.

## The DPO Self-Improvement Pipeline

This is the part that makes EduVerse more than a demo.

Every time a validator rejects a draft and the generator revises it, the system captures a DPO (Direct Preference Optimization) pair: the rejected version becomes the "losing" response, the revised version becomes the "winning" response. This happens automatically, across all three swarms, on every student interaction.

```
Student asks a question
  -> Agent drafts response
  -> Validator finds a grounding issue
  -> Rejected draft saved as "rejected" ←──── DPO pair
  -> Agent revises
  -> Validator approves
  -> Approved draft saved as "chosen"  ←──── DPO pair
                    ↓
        MongoDB (dpo_pairs collection)
                    ↓
     Shadow Auditor adds teacher gold-standard
     responses via Gemini 2.5 Pro (background)
                    ↓
     Training Orchestrator exports to Kaggle
     -> DPO fine-tuning on T4 GPU
     -> Pairwise Teacher-as-Judge evaluation
     -> Auto-promote to HuggingFace if improved 15%+
```

The end goal: once enough DPO pairs accumulate per agent role, the system fine-tunes **Gemma 4 E4B** (a model small enough for consumer hardware) using distilled knowledge from the larger cloud models. Every student interaction makes the future local model better.

**Current state:** We're in the data collection phase. The pipeline is live and logging. Training triggers when any agent accumulates 150+ DPO pairs.

## Tech Stack

| Layer | What We Use |
|-------|------------|
| LLM Inference | Gemma 4 26B-A4B-IT, Gemma 4 31B-IT (Google AI Studio) |
| Agent Orchestration | LangGraph with MongoDB checkpointing |
| Embeddings | Nomic Embed Text v1.5 (768d, cloud) |
| Reranking | Cohere Rerank v3.5 |
| Vector + BM25 Search | MongoDB Atlas (hybrid retrieval with RRF) |
| Backend | FastAPI, async SSE streaming |
| Frontend | Next.js 16, React 19, Tailwind CSS 4, Three.js |
| Document Storage | Cloudinary |
| Code Sandbox | E2B (cloud Python execution) |
| DPO Training | Kaggle Kernels (T4 GPU) |
| Model Hosting | HuggingFace Hub (GGUF) |
| Observability | LangSmith tracing |

## Running It

### Backend

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # fill in your API keys
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install && npm run dev   # → http://localhost:3000
```

### Docker

```bash
docker-compose up --build
# API: localhost:8000 | RL Server: localhost:8001
```

### What You Need

- Python 3.11+, Node.js 20+
- [Google AI Studio API key](https://aistudio.google.com/apikey) (free)
- MongoDB Atlas cluster (free M0 tier works)
- Google Cloud OAuth credentials (for Classroom sync)
- See `backend/.env.example` for the full list

## Project Structure

```
EduVerse/
├── backend/app/
│   ├── agents/           # LangGraph nodes & subgraphs
│   │   ├── graph.py          # Main state graph compilation
│   │   ├── orchestrator.py   # Intent classification & routing
│   │   ├── guardrails.py     # Triple-layer safety (input → integrity → output)
│   │   ├── rag_subgraph.py   # 6-node RAG pipeline with HITL
│   │   ├── quiz_subgraph.py  # Map-Reduce parallel MCQ generation
│   │   ├── feedback_subgraph.py  # RCA + growth-mindset scoring
│   │   ├── critic.py         # Global quality gate
│   │   └── swarm_engine.py   # Standardized revision loop + DPO extraction
│   ├── retrieval/        # Hybrid search: vector + BM25 + reranking
│   ├── ingestion/        # PDF parsing, chunking, embedding pipeline
│   ├── services/training/ # DPO orchestrator, shadow auditor, eval engine
│   ├── db/               # MongoDB repositories (9 collections)
│   └── utils/            # LLM factory, thinking extraction, token mgmt
├── frontend/src/
│   ├── app/              # Next.js pages (dashboard, chat, course, admin)
│   └── components/       # Chat UI, X-Ray panel, 3D visualizations
├── ARCHITECTURE.md       # Deep technical walkthrough
└── docker-compose.yml    # One-command dev environment
```

## Challenges We Hit

**Gemma 4 structured output inconsistency.** The 26B MoE model sometimes returns raw text instead of structured tool calls. We built a fallback parser that regex-extracts JSON from the raw response content when `with_structured_output()` fails to parse. See `rag_subgraph.py:61-74`.

**HITL checkpoint serialization.** LangGraph's `interrupt()` requires all state to be serializable to MongoDB. We had to flatten complex objects (LangChain `Document`s, Pydantic models) into plain dicts before checkpointing and reconstruct them after resume.

**DPO pair quality.** Early revision cycles produced noisy pairs where both "chosen" and "rejected" were bad. The Shadow Auditor (Gemini 2.5 Pro teacher distillation) was added specifically to inject higher-quality "chosen" examples into the training set.

**Retrieval grounding.** A naive RAG setup produced confident-sounding hallucinations. Adding the 3-tier confidence labeling (`GROUNDED` / `LOW_CONFIDENCE` / `INSUFFICIENT`) with the HITL gate gives the student control over when the system reaches outside course materials.

## Acknowledgments

- **Google** — Gemma 4 models and Google AI Studio
- **Kaggle** — Hosting the competition and providing GPU compute for training
- **LangGraph** — Multi-agent orchestration framework
- **MongoDB** — Atlas Vector Search and hybrid retrieval infrastructure
- **Cohere** — Rerank v3.5 for retrieval quality
- **Nomic** — Embedding model

## License

CC-BY 4.0. See [LICENSE](./LICENSE).

Built for the [Gemma 4 Good Hackathon](https://www.kaggle.com/competitions/gemma-4-good-hackathon) - Future of Education Track.
