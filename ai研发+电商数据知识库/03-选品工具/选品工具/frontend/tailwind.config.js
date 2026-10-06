/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        teal: {
          DEFAULT: '#0891b2',
          light: '#06b6d4',
          sky: '#22d3ee',
        },
      },
      backdropBlur: { glass: '20px' },
      boxShadow: {
        glass: '0 8px 32px rgba(8,145,178,0.10), 0 1px 0 rgba(255,255,255,0.9) inset',
      },
      borderRadius: { card: '20px' },
    },
  },
  plugins: [],
}
