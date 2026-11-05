import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// base: './' makes the built site work from any sub-path,
// including https://vamsivoleti25.github.io/traveldeal_search/
export default defineConfig({
  base: './',
  plugins: [react()],
  test: {
    globals: true,
    include: ['tests/**/*.test.ts'],
  },
});
