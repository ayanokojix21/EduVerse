# EduVerse Frontend — Implementation Plan

Build a hyper-minimalist, Twitter-inspired dark-mode frontend for EduVerse using **Next.js 15 (App Router)** + **TailwindCSS v4** + **GSAP** + **D3.js**.

## User Review Required

> [!IMPORTANT]
> **Phased Delivery**: This is a large project (~25+ files). I'll build it in **4 phases**, committing after each so you can review incrementally:
> 1. **Foundation** — Next.js scaffold, design system, layout shell, landing page
> 2. **Core Pages** — Course Dashboard, Auth flow, Settings
> 3. **Chat Engine** — SSE streaming, HITL, citations, observability drawer
> 4. **Data Pages** — Student Profile + D3 Knowledge Universe, RLAIF Admin Dashboard

> [!WARNING]
> **TailwindCSS Version**: Your blueprint references TailwindCSS. Next.js 15 ships with Tailwind v4 by default. I'll use **Tailwind v4** unless you want v3. Tailwind v4 uses CSS-based config (`@theme` in CSS) instead of `tailwind.config.js`.

> [!IMPORTANT]
> **3D Elements**: Your blueprint mentions Spline 3D / Three.js for the landing page. I'll use **CSS-only** cinematic animations (gradient orbs, glow effects, parallax) for now since Spline requires a separately-hosted 3D scene URL. This keeps the landing page visually stunning without external dependencies. Let me know if you want me to integrate Spline instead (you'd need to provide a scene URL).

## Open Questions

> [!IMPORTANT]
> 1. **Backend URL**: Is the backend at `http://localhost:8000` during development? I'll default to this.
> 2. **Deployment target**: Vercel? Docker? This affects the Next.js output config.
> 3. **Should I add the frontend service to `docker-compose.yml`?**

---

## Proposed Changes

### Phase 1: Foundation (This Session)

#### Next.js Project Scaffold

##### [NEW] `frontend/` directory
- Initialize with `npx create-next-app@latest` (App Router, TypeScript, TailwindCSS, ESLint)
- Install additional deps: `gsap`, `@microsoft/fetch-event-source`, `d3`, `react-markdown`, `rehype-raw`, `remark-gfm`, `lucide-react`

---

#### Design System

##### [NEW] [app/globals.css](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/app/globals.css)
Tailwind v4 theme with your exact design tokens:
- Colors: `bg: #000`, `panel: #16181C`, `border: #2F3336`, `textMain: #E7E9EA`, `textMuted: #71767B`
- Semantic: `danger: #F4212E`, `warning: #FFD400`, `success: #00BA7C`
- Primary: `#EFF3F4` with hover/dim variants
- Font: Inter from Google Fonts
- Custom animations: `pulse-fast`, `fade-up`, `slide-in-right`

---

#### Layout Shell

##### [NEW] [app/layout.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/app/layout.tsx)
Root layout with:
- Google Fonts (Inter) loading
- Dark mode body (`bg-black text-textMain`)
- Auth context provider wrapper
- Metadata (title, description, viewport)

##### [NEW] [components/layout/Sidebar.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/components/layout/Sidebar.tsx)
Twitter-style left navigation:
- Logo/brand at top
- Nav links: Home (Dashboard), Chat, Profile
- Admin section (conditionally rendered)
- Razor-thin `border-r border-border` divider

##### [NEW] [components/layout/AppShell.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/components/layout/AppShell.tsx)
Three-column layout wrapper (sidebar | main content | optional right panel)

---

#### Auth Infrastructure

##### [NEW] [lib/auth-context.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/lib/auth-context.tsx)
React context providing:
- `user` state (user_id, role, is_guest)
- `token` (JWT string)
- `login()`, `loginAsGuest()`, `logout()`
- Persists JWT in localStorage

##### [NEW] [lib/api.ts](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/lib/api.ts)
Centralized API client:
- Base URL config (`NEXT_PUBLIC_API_URL`)
- Auto-attaches Bearer token from auth context
- Typed fetch wrappers for GET/POST/DELETE/PATCH
- SSE stream helper using `@microsoft/fetch-event-source`

---

#### Landing Page

##### [NEW] [app/page.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/app/page.tsx)
Cinematic landing page:
- Full-viewport black background
- Animated gradient orb (CSS radial-gradient with GSAP motion)
- Bold hero headline + subtitle in `#E7E9EA`
- Two CTA buttons: "Sign in with Google" (ghost) + "Continue as Guest" (solid)
- GSAP staggered fade-up reveal on load
- Feature highlights section below fold

##### [NEW] [app/auth/callback/page.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/app/auth/callback/page.tsx)
OAuth callback handler — extracts JWT, stores, redirects to `/dashboard`

---

### Phase 2: Core Pages

#### Course Dashboard

##### [NEW] [app/(app)/dashboard/page.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/app/(app)/dashboard/page.tsx)
Twitter-feed style course grid:
- Fetches courses from `GET /api/v1/courses/`
- Bento-box card grid with flat borders
- Source badges (Classroom / Local)
- Ingestion status dots (green/yellow/red)
- "New Workspace" button → creation modal

##### [NEW] [components/courses/CourseCard.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/components/courses/CourseCard.tsx)
Individual course card with hover effect, badges, action menu

##### [NEW] [components/courses/CourseDrawer.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/components/courses/CourseDrawer.tsx)
Right-side slide-in drawer with Files tab + Assignments tab:
- File list from `GET /ingestion/{course_id}/files`
- Upload button (multipart form)
- Sync/Ingest button with progress bar polling
- Delete file actions

##### [NEW] [components/courses/CreateCourseModal.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/components/courses/CreateCourseModal.tsx)
Modal for creating local workspaces

##### [NEW] [app/(app)/settings/page.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/app/(app)/settings/page.tsx)
Settings page: Google connection status, disconnect, data wipe (danger zone)

---

### Phase 3: Chat Engine

##### [NEW] [app/(app)/chat/[courseId]/page.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/app/(app)/chat/[courseId]/page.tsx)
Main chat page with three-panel layout:
- Left: Session sidebar
- Center: Chat stream (max-width 65ch)
- Right: Observability drawer (toggleable)

##### [NEW] [components/chat/SessionSidebar.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/components/chat/SessionSidebar.tsx)
Session list with rename/delete context menu

##### [NEW] [components/chat/ChatStream.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/components/chat/ChatStream.tsx)
Message rendering with markdown, streaming cursor, citation pills

##### [NEW] [components/chat/ChatInput.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/components/chat/ChatInput.tsx)
Text input + image upload (multimodal)

##### [NEW] [components/chat/HITLInterrupt.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/components/chat/HITLInterrupt.tsx)
Decision block with "Search Web" / "Socratic Only" buttons

##### [NEW] [components/chat/CitationPill.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/components/chat/CitationPill.tsx)
Inline citation references with hover tooltips

##### [NEW] [components/chat/ObservabilityDrawer.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/components/chat/ObservabilityDrawer.tsx)
Agent thoughts timeline, retrieval badge, Mermaid graph, LangSmith link

##### [NEW] [lib/sse.ts](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/lib/sse.ts)
SSE stream parser handling all 10 event types with typed callbacks

---

### Phase 4: Data Pages

##### [NEW] [app/(app)/profile/page.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/app/(app)/profile/page.tsx)
Profile stats + D3 Knowledge Universe

##### [NEW] [components/profile/KnowledgeUniverse.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/components/profile/KnowledgeUniverse.tsx)
D3 force-directed graph with glowing nodes, dark canvas

##### [NEW] [app/(app)/admin/rl/page.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/app/(app)/admin/rl/page.tsx)
RLAIF dashboard: stats cards, model registry table, episode list, training controls

---

### Shared Components

##### [NEW] [components/ui/Button.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/components/ui/Button.tsx)
Reusable button variants: primary, ghost, danger, icon

##### [NEW] [components/ui/Modal.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/components/ui/Modal.tsx)
Animated modal with backdrop blur

##### [NEW] [components/ui/Badge.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/components/ui/Badge.tsx)
Pill-shaped status badges

##### [NEW] [components/ui/Loader.tsx](file:///home/vingw009/codefiles/proj/EduVerse/frontend/src/components/ui/Loader.tsx)
Custom loaders: skeleton pulser, typing indicator, thin progress bar

---

## Verification Plan

### Automated Tests
- `npm run build` — must compile with zero errors after each phase
- Visual check via `npm run dev` on `http://localhost:3000`
- Browser subagent to screenshot each page

### Manual Verification
- Verify CORS works between `localhost:3000` ↔ `localhost:8000`
- Test SSE streaming connection to the backend chat endpoint
- Confirm responsive layout at mobile/tablet/desktop breakpoints
