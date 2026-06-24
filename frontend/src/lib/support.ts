const API_BASE = "http://127.0.0.1:8000/api";

export type SupportRole = "user" | "assistant" | "system";

export interface SupportMessage {
  id: number;
  role: SupportRole;
  content: string;
  created_at: string;
}

export interface SupportOperation {
  id: number;
  kind: "refund" | "modify";
  status: "awaiting_confirmation" | "executed" | "denied" | "declined" | "failed";
  reason: string;
  policy_basis: string;
  booking_reference: string | null;
  details: Record<string, unknown>;
  before_state: Record<string, unknown>;
  after_state: Record<string, unknown>;
  created_at: string;
  executed_at: string | null;
  result?: { ok: boolean; message?: string };
}

export interface SupportSession {
  id: number;
  status: "active" | "ended";
  mode: "assist" | "individual";
  summary: string;
  created_at: string;
  updated_at: string;
  ended_at: string | null;
  messages: SupportMessage[];
  operations: SupportOperation[];
  pending_operation?: SupportOperation | null;
}

function authHeaders(token: string): HeadersInit {
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
}

async function parseError(response: Response, fallback: string): Promise<never> {
  let detail = fallback;
  try {
    const body = await response.json();
    if (body && typeof body.detail === "string") detail = body.detail;
  } catch {
    // ignore non-JSON bodies
  }
  throw new Error(detail);
}

export async function startSupportSession(token: string): Promise<SupportSession> {
  const response = await fetch(`${API_BASE}/trips/support/sessions/`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!response.ok) await parseError(response, "Could not start support");
  return response.json();
}

export async function sendSupportMessage(
  token: string,
  sessionId: number,
  content: string
): Promise<SupportSession> {
  const response = await fetch(`${API_BASE}/trips/support/sessions/${sessionId}/messages/`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ content }),
  });
  if (!response.ok) await parseError(response, "The support agent could not respond");
  return response.json();
}

export async function confirmOperation(
  token: string,
  operationId: number
): Promise<SupportOperation> {
  const response = await fetch(`${API_BASE}/trips/support/operations/${operationId}/confirm/`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!response.ok) await parseError(response, "Could not complete the operation");
  return response.json();
}

export async function declineOperation(
  token: string,
  operationId: number
): Promise<SupportOperation> {
  const response = await fetch(`${API_BASE}/trips/support/operations/${operationId}/decline/`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!response.ok) await parseError(response, "Could not decline the operation");
  return response.json();
}
