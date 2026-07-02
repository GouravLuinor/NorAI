import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // Chat endpoints
      '/chat': 'http://localhost:8000',

      // Thread endpoints — THIS WAS THE MISSING PIECE.
      // Without this, every /threads/* fetch returned index.html (200 HTML),
      // apiFetch saw non-JSON, returned null, and messages wiped on every
      // thread switch and page refresh.
      '/threads': 'http://localhost:8000',
      '/notes': 'http://localhost:8000',
      // Quiz, flashcards, summary
      '/screenshots': 'http://localhost:8000',
      '/static': 'http://localhost:8000',
      '/quiz':       'http://localhost:8000',
      '/flashcards': 'http://localhost:8000',
      '/summary':    'http://localhost:8000',
    },
  },
})