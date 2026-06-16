import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:5034',
      '/static': 'http://127.0.0.1:5034',
      '/manifest.json': 'http://127.0.0.1:5034',
      '/service-worker.js': 'http://127.0.0.1:5034',
      '/chatbot': 'http://127.0.0.1:5034',
      '/journal': 'http://127.0.0.1:5034',
      '/planner': 'http://127.0.0.1:5034',
      '/activities': 'http://127.0.0.1:5034',
      '/recommend': 'http://127.0.0.1:5034',
      '/counsellor': 'http://127.0.0.1:5034',
      '/game': 'http://127.0.0.1:5034',
      '/3d-lite': 'http://127.0.0.1:5034',
      '/track': 'http://127.0.0.1:5034',
      '/analyze_home': 'http://127.0.0.1:5034',
      '/detect_emotion': 'http://127.0.0.1:5034',
      '/authorize': 'http://127.0.0.1:5034',
      '/oauth2callback': 'http://127.0.0.1:5034',
      '/sync_to_calendar': 'http://127.0.0.1:5034',
      '/speech-to-text': 'http://127.0.0.1:5034',
      '/text-to-speech': 'http://127.0.0.1:5034',
      '/oasis-watch': 'http://127.0.0.1:5034',
      '/oasis-home': 'http://127.0.0.1:5034',
    }
  }
})
