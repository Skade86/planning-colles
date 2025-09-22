import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],

  // Options serveur de dev
  server: {
    port: 3000,               
    open: true,               // ouvre le navigateur automatiquement
    proxy: {
      // Toutes les requêtes commençant par /api seront redirigées vers FastAPI
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
})