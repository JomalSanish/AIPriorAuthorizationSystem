/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        darkBg: '#0b0d13',
        darkCard: 'rgba(30, 41, 59, 0.25)',
        accentPurple: '#c084fc',
        accentIndigo: '#818cf8',
        accentBlue: '#38bdf8',
      }
    },
  },
  plugins: [],
}
