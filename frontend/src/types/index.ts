// ── Auth ──────────────────────────────────────────────
export interface AuthStatus {
  authenticated: boolean;
  user?: {
    name: string;
    email: string;
    picture: string;
  };
}

// ── Courses ───────────────────────────────────────────
export interface Course {
  id: string;
  name: string;
  section?: string;
  description?: string;
  teacher: string;
  enrollment_count?: number;
  assignment_count?: number;
  state: 'ACTIVE' | 'ARCHIVED' | 'PROVISIONED' | 'DECLINED';
  is_ingested?: boolean;
  alternateLink?: string;
  creationTime?: string;
}

export interface CourseworkMaterial {
  driveFile?: {
    driveFile: {
      id: string;
      title: string;
      alternateLink: string;
      thumbnailUrl?: string;
    };
    shareMode: string;
  };
  youtubeVideo?: {
    id: string;
    title: string;
    alternateLink: string;
    thumbnailUrl?: string;
  };
  link?: {
    url: string;
    title: string;
    thumbnailUrl?: string;
  };
  form?: {
    formUrl: string;
    responseUrl: string;
    title: string;
    thumbnailUrl?: string;
  };
}

export interface CourseItem {
  id: string;
  title: string;
  description: string;
  state: string;
  dueDate?: {
    year: number;
    month: number;
    day: number;
  };
  creationTime: string;
  alternateLink: string;
  materials?: CourseworkMaterial[];
  type: string;
}

export interface CourseContent {
  assignments: CourseItem[];
  materials: CourseItem[];
  announcements: CourseItem[];
}

// ── Profile ───────────────────────────────────────────
export interface WeakTopic {
  topic: string;
  confidence: number;
  course_id: string;
  course_name?: string;
}

export interface Profile {
  session_count: number;
  weak_topics: WeakTopic[];
}

// ── Chat ──────────────────────────────────────────────
export interface Message {
  id: string; // Internal frontend ID
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  citations?: Citation[];
  tutor_drafts?: TutorDraft[];
  explainability?: Explainability;
  critic?: CriticResult;
  trace_url?: string;
}

export interface ChatSession {
  session_id: string;
  user_id: string;
  course_id: string;
  title: string;
  messages: Message[];
  message_count: number;
  created_at: string;
  updated_at: string;
}


export interface Citation {
  source_index?: number; // 1-indexed reference from the backend
  title: string;
  content_type: 'document' | 'announcement' | 'assignment' | 'material';
  link?: string;           // web fallback sources
  alternate_link?: string; // Google Classroom source URL
  file_url?: string;       // Direct file link for proxy deep-linking
  snippet?: string;
  page_number?: number;
  score?: number;
}

export interface TutorDraft {
  agent_id: string;
  style: 'concise' | 'explanatory';
  response_text: string;
}

export interface Explainability {
  confidence_label: 'High' | 'Medium' | 'Low';
  top_score: number;
  retrieval_label: string;
  sources: SourceScore[];
}

export interface SourceScore {
  title: string;
  score: number;
  content_type?: string;
}

export interface CriticResult {
  score: number;
  feedback: string;
  approved: boolean;
}

// ── SSE Events ────────────────────────────────────────
export type SSEEvent =
  | { type: 'status';           data: { message: string } }
  | { type: 'agent_thought';    data: { node: string; summary: string; data?: unknown } }
  | { type: 'retrieval_label';  data: { label: string; top_score: number; confidence_label: string } }
  | { type: 'tutor_draft';      data: TutorDraft }
  | { type: 'token';            data: { text: string } }
  | { type: 'done';             data: { response: string; citations: Citation[]; tutor_drafts: TutorDraft[]; explainability: Explainability; critic: CriticResult; trace_url?: string } }
  | { type: 'error';            data: { message: string; code?: string } };

// ── Agent nodes (Thought Log) ─────────────────────────
export const AGENT_NODES = [
  'supervisor',
  'query_rewriter',
  'rag_agent',
  'tutor_a',
  'tutor_b',
  'synthesizer',
  'critic_agent',
] as const;

export type AgentNode = typeof AGENT_NODES[number];

export interface AgentThought {
  node: AgentNode;
  summary: string;
  timestamp: Date;
  data?: unknown;
  status: 'pending' | 'active' | 'done';
}

// ── Ingest ────────────────────────────────────────────
export interface IngestResponse {
  status: string;
  message: string;
  course_id: string;
}
