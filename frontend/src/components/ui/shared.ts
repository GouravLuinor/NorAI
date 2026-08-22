// Shared class fragments for ui primitives. Keep zero visual delta vs the
// hand-rolled class strings they replace; these only add the keyboard
// quality floor (visible focus ring, no default outline).
export const FOCUS_RING =
  'focus-visible:outline-none focus-visible:shadow-[var(--ds-focus-ring)]'

// Same ring, tuned for inline text links / nav anchors where a box shadow on
// the text block reads cleaner than an outline.
export const LINK_RING =
  'focus-visible:outline-none focus-visible:shadow-[var(--ds-focus-ring)] rounded-sm'
