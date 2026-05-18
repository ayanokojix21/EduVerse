// ─────────────────────────────────────────────────────────────────────────────
// EduVerse — Shared TypeScript Interfaces
// Delivered by P1. Used by ALL components across P2 (Dashboard/Admin)
// and P3 (Chat/Profile). DO NOT modify field names — they map 1:1 to backend.
// ─────────────────────────────────────────────────────────────────────────────

// ─── Auth ────────────────────────────────────────────────────────────────────

export interface GuestLoginResponse {
  user_id: string;
  app_jwt: string;
  is_guest: boolean;
}

export interface OAuthResult {
  status: string;
  user_id: string;
  app_jwt: string;
}

export interface AuthStatus {
  authenticated: boolean;
  user_id: string;
  email?: string;
  google_connected: boolean;
  is_guest: boolean;
  role: "student" | "admin";
}

export interface DecodedJWT {
  sub: string;          // user_id
  email?: string;
  name?: string;
  role: "student" | "admin";
  is_guest: boolean;
  exp: number;
}

// ─── Courses (P2) ────────────────────────────────────────────────────────────

export interface UnifiedCourse {
  id: string;
  name: string;
  source: "classroom" | "local";
  description?: string;
  is_ingested: boolean;
  assignment_count: number;
  created_at?: string;
  updated_at?: string;
}

export interface CreateCourseRequest {
  name: string;
  description?: string;
}

export interface CourseworkMaterial {
  driveFile?: { driveFile?: { id?: string; title?: string; alternateLink?: string } };
  youtubeVideo?: { id?: string; title?: string; alternateLink?: string };
  link?: { url?: string; title?: string };
  form?: { formUrl?: string; title?: string };
}

export interface Coursework {
  id: string;
  title: string;
  description?: string;
  state?: string;
  type?: "assignment" | "material" | "announcement";
  dueDate?: { year?: number; month?: number; day?: number } | null;
  creationTime?: string;
  alternateLink?: string;
  materials?: CourseworkMaterial[];
}

// ─── Ingestion (P2) ──────────────────────────────────────────────────────────

export interface IngestedFile {
  filename: string;
  chunk_count: number;
  source: string;
}

export type IngestionStatusValue =
  | "none"
  | "pending"
  | "processing"
  | "completed"
  | "failed";

export interface IngestionStatus {
  status: IngestionStatusValue;
  error?: string;
  current_file_count: number;
}

export interface IngestionRequest {
  course_id: string;
}

export interface UploadFileRequest {
  course_id: string;
  file: File;
}

// ─── Chat / SSE (P3) ─────────────────────────────────────────────────────────

export interface ChatRequest {
  message: string;         // 1–4000 chars
  course_id: string;
  session_id?: string;     // Provide to continue existing conversation
  image_data?: string;     // Base64-encoded image
  image_mimetype?: string; // Default: "image/png"
}

export interface HITLResumeRequest {
  session_id: string;
  decision: "search_web" | "socratic_only";
}

export interface Citation {
  source_index: number;       // [Doc 1], [Doc 2], etc.
  title: string;
  alternate_link: string;     // Link to Google Classroom material
  file_url?: string;          // Direct PDF link for deep-linking
  content_type: string;
  page_number?: number;       // For PDF jump-to-page
  snippet: string;
}

export interface AgentThought {
  node: string;
  summary: string;           // Bold header: "Optimizing Search Query"
  reasoning?: string;        // Italic body: model's chain-of-thought reasoning
  data?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface DonePayload {
  response: string;             // Final markdown response
  citations: Citation[];
  retrieval_label: string;      // "CLASSROOM_GROUNDED" | "CLASSROOM_LOW_CONFIDENCE" | "CLASSROOM_INSUFFICIENT"
  explainability: Record<string, unknown>;
  critic: Record<string, unknown>;
  agent_thoughts: AgentThought[];
  mermaid_graph: string;        // Mermaid diagram string
  retrieval_ms: number;
  session_id: string;
  trace_url: string;            // LangSmith trace link
}

// SSE Event types — all 10 event variants the backend can emit
export type SSEEvent =
  | { event: "status";          data: { message: string; session_id: string } }
  | { event: "node_start";      data: { node: string; message: string } }
  | { event: "node_end";        data: { node: string } }
  | { event: "tool_start";      data: { tool: string; input: unknown } }
  | { event: "tool_end";        data: { tool: string } }
  | { event: "retrieval_label"; data: { label: string; top_score: number; confidence_label: string; retrieval_ms: number } }
  | { event: "agent_thought";   data: AgentThought }
  | { event: "token";           data: { text: string } }
  | { event: "done";            data: DonePayload }
  | { event: "error";           data: { message: string; code: string } }
  | { event: "hitl";            data: { session_id: string; interrupt_data: any; trace_url: string } };

// Keyed map for discriminated union lookups
export type SSEEventMap = {
  [E in SSEEvent as E["event"]]: E["data"];
};

// Chat message (frontend state model)
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  retrieval_label?: string;
  agent_thoughts?: AgentThought[];
  active_nodes?: string[];
  mermaid_graph?: string;
  trace_url?: string;
  retrieval_ms?: number;
  image_data?: string;
  image_mimetype?: string;
  created_at?: string; // used by local state
  timestamp?: string;  // used by backend history
  is_streaming?: boolean;
  feedback?: "up" | "down" | null;
}

// ─── Sessions (P3) ───────────────────────────────────────────────────────────

export interface ChatSession {
  session_id: string;
  course_id: string;
  title: string;
  created_at: string;
  updated_at?: string;
  message_count?: number;
}

export interface SessionDetail extends ChatSession {
  messages: ChatMessage[];
}

export interface FeedbackRequest {
  rating: "up" | "down";
  comment?: string;
}

// ─── Profile (P3) ────────────────────────────────────────────────────────────

export interface TopicMastery {
  [topic: string]: number; // topic name → score 0.0–1.0
}

export interface ProfileResponse {
  user_id: string;
  email?: string;
  full_name?: string;
  total_documents: number;
  actual_session_count: number;
  topic_mastery: TopicMastery;
  created_at?: string;
}

export interface MasteryNode {
  id: string;
  name: string;
  val: number;    // Size: 10 + (score * 20)
  score: number;  // 0.0 – 1.0
  color: string;  // "#4ade80" | "#fbbf24" | "#f87171"
}

export interface MasteryLink {
  source: string;
  target: string;
}

export interface KnowledgeUniverseResponse {
  nodes: MasteryNode[];
  links: MasteryLink[];
}

// ─── RLAIF Admin (P2) ────────────────────────────────────────────────────────

export interface RLStats {
  total_episodes: number;
  average_reward: number;
  environment_version: string;
  [key: string]: unknown;
}

export interface RLModel {
  model_id: string;
  name: string;
  version: string;
  role: "tutor" | "quiz" | "feedback";
  status: "active" | "training" | "archived";
  created_at: string;
}

export interface RLEpisode {
  episode_id: string;
  query: string;
  response: string;
  reward: number;
  created_at: string;
}

export interface TrainingStatus {
  status: "idle" | "running" | "complete" | "error";
  message?: string;
  started_at?: string;
  completed_at?: string;
}

export interface RLDashboard {
  total_episodes: number;
  model_history: {
    tutor: Array<{ version: string; reward: number; date: string }>;
    quiz: Array<{ version: string; reward: number; date: string }>;
    feedback: Array<{ version: string; reward: number; date: string }>;
  };
  [key: string]: unknown;
}

// ─── Generic API Wrappers ─────────────────────────────────────────────────────

export interface APIError {
  detail: string;
  code?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
