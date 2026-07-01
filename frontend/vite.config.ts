import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/chat': 'http://localhost:8000',
      '/chat/stream': 'http://localhost:8000',
      '/quiz': 'http://localhost:8000',
      '/flashcards': 'http://localhost:8000',
      '/summary': 'http://localhost:8000',
    },
  },
})