import { defineConfig, searchForWorkspaceRoot } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  envDir: '..',
  server: {
    fs: {
      allow: [
        // Dynamically allows the root project directory and node_modules
        searchForWorkspaceRoot(process.cwd())
      ],
    },
    proxy: {
      '/process': 'http://localhost:8000',
      '/estimate': 'http://localhost:8000',
      '/chat': 'http://localhost:8000',
      '/chat/stream': 'http://localhost:8000',
      '/quiz': 'http://localhost:8000',
      '/flashcards': 'http://localhost:8000',
      '/summary': 'http://localhost:8000',
      '/notes': 'http://localhost:8000',
      '/screenshots': 'http://localhost:8000',
      '/threads': 'http://localhost:8000',
      '/download': 'http://localhost:8000',
      '/lectures': 'http://localhost:8000',
      '/static': 'http://localhost:8000',
      '/outline': 'http://localhost:8000',
      '/study-guide': 'http://localhost:8000',
      '/concept-map': 'http://localhost:8000',
      '/quota': 'http://localhost:8000',
    },
  },
})