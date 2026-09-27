/**
 * VentureLens API service.
 * Calls the Python FastAPI backend that wraps the existing CrewAI pipeline
 * and single-agent follow-up routing.
 */

export const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Start the full 7-agent validation pipeline in the background.
 * @param {string} idea - The startup/business idea to validate.
 * @returns {Promise<Object>} Initial session metadata with session_id.
 */
export async function startValidation(idea) {
  const res = await fetch(`${API_BASE}/api/validate/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ idea }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || `API error ${res.status}`);
  }

  return res.json();
}

/**
 * Run the full 7-agent validation pipeline.
 * @param {string} idea - The startup/business idea to validate.
 * @returns {Promise<Object>} Pipeline response with session_id, raw, score, recommendation, justification, agent_results.
 */
export async function validateIdea(idea) {
  const res = await fetch(`${API_BASE}/api/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ idea }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || `API error ${res.status}`);
  }

  return res.json();
}

export function streamValidationEvents(sessionId, onEvent, onError) {
  const source = new EventSource(`${API_BASE}/api/validate/events/${sessionId}`);
  source.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      onEvent?.(payload);
    } catch (err) {
      onError?.(err);
    }
  };
  source.onerror = (err) => {
    onError?.(err);
  };
  return source;
}

export async function getSession(sessionId) {
  const res = await fetch(`${API_BASE}/api/session/${sessionId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || `API error ${res.status}`);
  }
  return res.json();
}

/**
 * Run a fast follow-up question routed to ONLY the relevant specialist research agent.
 * @param {string} sessionId - Existing validation session ID.
 * @param {string} question - The user's follow-up question.
 * @param {string} [idea] - The original startup idea as fallback.
 * @returns {Promise<Object>} Follow-up response with agent, agent_name, agent_icon, answer, sources, is_revalidation.
 */
export async function followUpQuestion(sessionId, question, idea) {
  const res = await fetch(`${API_BASE}/api/follow-up`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, question, idea }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || `API error ${res.status}`);
  }

  return res.json();
}

/**
 * Health check.
 */
export async function checkHealth() {
  const res = await fetch(`${API_BASE}/api/health`);
  return res.json();
}
