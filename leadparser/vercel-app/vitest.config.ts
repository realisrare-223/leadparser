import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./test-setup.ts'],
    include: ['./__tests__/**/*.{test,spec}.{ts,tsx}'],
    tsconfig: './tsconfig.test.json',
    alias: {
      '@': path.resolve(__dirname, '.'),
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
    },
  },
})
