import type { ButtonHTMLAttributes, Ref } from 'react'
import { FOCUS_RING } from './shared'

// Blueprint-grammar button. Variant carries only the shared identity
// (surface, ink, press-down); geometry + density (padding, radius, text
// size, gap, width) stays at the call site via `className` so migration is
// strictly token-preserving.
export type ButtonVariant = 'primary' | 'primarySoft' | 'outline' | 'surface' | 'ghost'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  ref?: Ref<HTMLButtonElement>
}

const base =
  'inline-flex items-center justify-center transition select-none disabled:cursor-not-allowed'

const variants: Record<ButtonVariant, string> = {
  // Red-pencil fill, hard shadow, press-down. Default CTA.
  primary:
    'bg-npf text-npfg font-medium shadow-ev2 hover:bg-npfh active:translate-y-[1px] active:shadow-none',
  // Same fill, softer resting shadow that lifts on hover (assessment start).
  primarySoft:
    'bg-npf text-npfg font-medium shadow-ev1 hover:bg-npfh hover:shadow-ev2 active:translate-y-[1px] active:shadow-none',
  // Hairline ink border. Border + background color passed per-site so
  // selected states (e.g. `bg-npb border-npbr`) never collide with a baked
  // value. Press-down is opt-in via className (some outline sites lack it).
  outline: 'border text-nt3 hover:bg-ns2 hover:text-nt2',
  // Muted surface on a panel background; bg/hover come from the call site.
  surface: 'border border-bdr2 text-nt font-medium',
  // Borderless text button.
  ghost: 'text-nt3 hover:bg-ns2 hover:text-nt2',
}

export function Button({
  variant = 'primary',
  className = '',
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={`${base} ${variants[variant]} ${FOCUS_RING} ${className}`
        .replace(/\s+/g, ' ')
        .trim()}
      {...rest}
    />
  )
}
