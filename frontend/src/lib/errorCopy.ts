// P4.3: friendly error-copy mapper. Backend/Supabase/network failures used to
// surface raw err.message verbatim (leaking internals, reading like stack
// traces). Map the common failure shapes to honest, actionable copy and fall
// back to a generic line — never dump an unreadable payload to the user.

const PATTERNS: Array<{ re: RegExp; copy: string }> = [
  { re: /failed to fetch|networkerror|load failed|ERR_NETWORK/i, copy: "Couldn't reach the server. Check your connection and try again." },
  { re: /\b401\b|invalid login credentials|unauthorized/i, copy: 'That email or password is incorrect.' },
  { re: /\b403\b|forbidden/i, copy: "You don't have access to this." },
  { re: /\b404\b|not found/i, copy: "This item no longer exists — it may have been deleted." },
  { re: /\b409\b/i, copy: 'That action conflicts with the current state. Refresh and try again.' },
  { re: /\b429\b|rate limit|too many requests/i, copy: 'Too many requests — take a short break and try again.' },
  { re: /\b500\b|\b502\b|\b503\b|internal server error/i, copy: 'The server hit an unexpected error. Please try again in a moment.' },
  { re: /user already registered|already exists|duplicate/i, copy: 'An account with these details already exists.' },
  { re: /password/i, copy: 'Password requirement not met — use at least 6 characters.' },
  { re: /quota|limit reached|usage limit/i, copy: "You've reached your plan's limit for this action. Upgrade or try again later." },
]

export function friendlyError(err: unknown): string {
  if (typeof err === 'string') {
    const hit = PATTERNS.find((p) => p.re.test(err))
    return hit ? hit.copy : sanitize(err)
  }
  if (err instanceof Error) {
    const msg = err.message || ''
    if (err.name === 'AbortError') return ''
    const hit = PATTERNS.find((p) => p.re.test(msg))
    return hit ? hit.copy : sanitize(msg)
  }
  return 'Something went wrong. Please try again.'
}

/** Raw messages that are short, human, and leak nothing can pass through
 *  as-is; everything else (objects, [object Object], HTML, huge dumps) is
 *  replaced with the generic line. */
function sanitize(msg: string): string {
  const trimmed = msg.trim()
  if (!trimmed || trimmed.includes('[object Object]') || trimmed.startsWith('<')) {
    return 'Something went wrong. Please try again.'
  }
  // Strip backend prefixes like "HTTP 500: ..." detail chains.
  const cleaned = trimmed.split('\n')[0].slice(0, 160)
  return /[a-z] [a-z]/i.test(cleaned) ? cleaned : 'Something went wrong. Please try again.'
}
