import { defineConfig } from 'astro/config';

export default defineConfig({
  // Minimal static site for the Strata landing page
  output: 'static',
  build: {
    // Ensure CSS is inlined for fast first paint
    inlineStylesheets: 'auto',
  },
});
