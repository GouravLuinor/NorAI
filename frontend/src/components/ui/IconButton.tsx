import type { ButtonHTMLAttributes } from 'react'
import { FOCUS_RING } from './shared'

// Icon-only button. `label` is required for the aria-label (a11y floor).
export type IconButtonVariant = 'ghost' | 'primary' | 'bare'

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string
  variant?: IconButtonVariant
}

const base = 'inline-flex items-center justify-center transition shrink-0'

const variants: Record<IconButtonVariant, string> = {
  ghost: 'text-nt3 hover:bg-ns2 hover:text-nt2',
  primary:
    'bg-npf text-npfg hover:bg-npfh active:translate-y-[1px] active:shadow-none',
  bare: 'text-nt3 hover:text-nt',
}

export function IconButton({
  label,
  variant = 'ghost',
  className = '',
  type = 'button',
  ...rest
}: IconButtonProps) {
  return (
    <button
      type={type}
      aria-label={label}
      className={`${base} ${variants[variant]} ${FOCUS_RING} ${className}`
        .replace(/\s+/g, ' ')
        .trim()}
      {...rest}
    />
  )
}
