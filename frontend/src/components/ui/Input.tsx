import type { InputHTMLAttributes, Ref } from 'react'

// Bare document input: transparent fill, no border/outline of its own.
// Field chrome (the bordered container with focus-within ring) lives at the
// call site; density/width/placeholder via `className` (only font-size is
// free — color is baked so it can't collide).
interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  ref?: Ref<HTMLInputElement>
}

export function Input({ className = '', ...rest }: InputProps) {
  return (
    <input
      className={`bg-transparent border-none outline-none text-nt ${className}`
        .replace(/\s+/g, ' ')
        .trim()}
      {...rest}
    />
  )
}
