/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./static/**/*.html",
    "./static/**/*.js",
    "./*.html",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0fdf4',
          500: '#22c55e',
          600: '#16a34a',
        },
        archive: {
          card: '#1e293b',
          border: '#334155',
          dark: '#0f172a',
        }
      }
    }
  },
  plugins: [],
}
