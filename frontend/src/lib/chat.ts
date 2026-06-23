const API_BASE = "http://127.0.0.1:8000/api";

export type ChatRole = "user" | "assistant";

export interface ChatActionResult {
  type: string;
  ok: boolean;
  message: string;
  data?: Record<string, unknown>;
}

export interface ChatMessage {
  id: number;
  role: ChatRole;
  content: string;
  actions: ChatActionResult[];
  created_at: string;
}

export interface ChatSession {
  id: number;
  title: string;
  status: "active" | "ended";
  summary: string;
  context_snapshot: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  ended_at: string | null;
  message_count: number;
  messages: ChatMessage[];
}

export interface ChatSessionListItem {
  id: number;
  title: string;
  status: "active" | "ended";
  summary: string;
  created_at: string;
  updated_at: string;
  ended_at: string | null;
  message_count: number;
}

/** Trip context captured at session start; the Codex agent reads this. */
export interface ChatTripContext {
  origin?: string;
  destination?: string;
  destinationCountry?: string;
  startDate?: string;
  endDate?: string;
  travelers?: number;
  budgetTier?: string;
  interests?: string[];
  selectedFlight?: Record<string, unknown> | null;
  selectedHotel?: Record<string, unknown> | null;
}

function authHeaders(token: string): HeadersInit {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

async function parseError(response: Response, fallback: string): Promise<never> {
  let detail = fallback;
  try {
    const body = await response.json();
    if (body && typeof body.detail === "string") detail = body.detail;
  } catch {
    // ignore non-JSON error bodies
  }
  throw new Error(detail);
}

export async function listChatSessions(token: string): Promise<ChatSessionListItem[]> {
  const response = await fetch(`${API_BASE}/trips/chat/sessions/`, {
    headers: authHeaders(token),
  });
  if (!response.ok) await parseError(response, "Failed to load conversations");
  return response.json();
}

export async function startChatSession(
  token: string,
  context: ChatTripContext,
  title?: string
): Promise<ChatSession> {
  const response = await fetch(`${API_BASE}/trips/chat/sessions/`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ context, title }),
  });
  if (!response.ok) await parseError(response, "Failed to start conversation");
  return response.json();
}

export async function getChatSession(token: string, sessionId: number): Promise<ChatSession> {
  const response = await fetch(`${API_BASE}/trips/chat/sessions/${sessionId}/`, {
    headers: authHeaders(token),
  });
  if (!response.ok) await parseError(response, "Failed to load conversation");
  return response.json();
}

export async function sendChatMessage(
  token: string,
  sessionId: number,
  content: string,
  context?: ChatTripContext
): Promise<ChatSession> {
  const response = await fetch(`${API_BASE}/trips/chat/sessions/${sessionId}/messages/`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ content, context }),
  });
  if (!response.ok) await parseError(response, "The assistant could not respond");
  return response.json();
}

export async function endChatSession(token: string, sessionId: number): Promise<ChatSession> {
  const response = await fetch(`${API_BASE}/trips/chat/sessions/${sessionId}/end/`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!response.ok) await parseError(response, "Failed to end conversation");
  return response.json();
}
