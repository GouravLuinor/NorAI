/**
 * Generate a deterministic SHA-256 hex string for a flashcard front string.
 * Used to key flashcard ratings stably across reloads.
 */
export async function getCardKey(text: string): Promise<string> {
  const normalized = text.trim().toLowerCase();
  const encoder = new TextEncoder();
  const data = encoder.encode(normalized);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hexString = hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
  return hexString.slice(0, 16);
}
