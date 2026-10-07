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

  const data = await res.json();
  try {
    localStorage.setItem(`vl_session_${data.session_id}`, JSON.stringify({
      session_id: data.session_id,
      startup_idea: idea,
      status: 'running',
      agent_results: {},
      validation_result: {},
    }));
  } catch (_) {}
  return data;
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

  const data = await res.json();
  try {
    localStorage.setItem(`vl_session_${data.session_id}`, JSON.stringify(data));
  } catch (_) {}
  return data;
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
  try {
    const res = await fetch(`${API_BASE}/api/session/${sessionId}`);
    if (res.ok) {
      const data = await res.json();
      try {
        localStorage.setItem(`vl_session_${sessionId}`, JSON.stringify(data));
      } catch (_) {}
      return data;
    }
    const err = await res.json().catch(() => ({ detail: 'Session not found' }));
    throw new Error(err.detail || `API error ${res.status}`);
  } catch (err) {
    // Check localStorage cache on network error or server restart
    try {
      const cached = localStorage.getItem(`vl_session_${sessionId}`);
      if (cached) {
        return JSON.parse(cached);
      }
    } catch (_) {}
    throw err;
  }
}

/**
 * Run a fast follow-up question routed to ONLY the relevant specialist research agent.
 * @param {string} sessionId - Existing validation session ID.
 * @param {string} question - The user's follow-up question.
 * @param {string} [idea] - The original startup idea as fallback.
 * @returns {Promise<Object>} Follow-up response with agent, agent_name, agent_icon, answer, sources, is_revalidation.
 */
export async function followUpQuestion(sessionId, question, idea, requestId) {
  const res = await fetch(`${API_BASE}/api/follow-up`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, question, idea, request_id: requestId }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || `API error ${res.status}`);
  }

  return res.json();
}

/**
 * Cancel a running validation pipeline.
 * @param {string} sessionId
 */
export async function cancelValidation(sessionId) {
  const res = await fetch(`${API_BASE}/api/cancel/${sessionId}`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || `API error ${res.status}`);
  }
  return res.json();
}

/**
 * Cancel a running follow-up request.
 * @param {string} requestId
 */
export async function cancelFollowUp(requestId) {
  const res = await fetch(`${API_BASE}/api/cancel-followup/${requestId}`, {
    method: 'POST',
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

// ---------------------------------------------------------------------------
// Streaming follow-up (new non-blocking flow)
// ---------------------------------------------------------------------------

/**
 * Start a follow-up question in the background (non-blocking).
 * Returns {request_id, session_id, status, agent, agent_name, agent_icon} immediately.
 * Open streamFollowUpEvents(request_id, ...) to receive real-time events.
 *
 * @param {string} sessionId
 * @param {string} question
 * @param {string} [idea]
 * @param {string} requestId - Client-generated unique ID (also used by cancelFollowUp)
 */
export async function startFollowUp(sessionId, question, idea, requestId) {
  const res = await fetch(`${API_BASE}/api/follow-up/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, question, idea, request_id: requestId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || `API error ${res.status}`);
  }
  return res.json();
}

/**
 * Open an SSE stream for a specific follow-up requestId.
 * Events: followup_started, followup_activity, search_started, source_found,
 *         followup_completed, followup_cancelled, followup_error.
 *
 * Each requestId maps to exactly one isolated queue on the server —
 * events from other sessions/requests never appear here.
 *
 * @param {string} requestId
 * @param {(event: Object) => void} onEvent
 * @param {(err: Event) => void} onError
 * @returns {EventSource}
 */
export function streamFollowUpEvents(requestId, onEvent, onError) {
  const source = new EventSource(`${API_BASE}/api/follow-up/stream/${requestId}`);
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
