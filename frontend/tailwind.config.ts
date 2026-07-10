import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        bg:        '#080808',
        surface:   '#111111',
        'surface-2': '#161616',
        border:    '#1E1E1E',
        'border-2': '#2A2A2A',
        accent:    '#FF3D00',
        'accent-2': '#E8FF00',
        muted:     '#888888',
        'muted-2': '#555555',
      },
      fontFamily: {
        display: ['Bebas Neue', 'sans-serif'],
        mono:    ['DM Mono', 'monospace'],
        sans:    ['Inter', 'sans-serif'],
      },
      animation: {
        ticker:   'ticker 30s linear infinite',
        'fade-up': 'fadeUp 0.4s ease forwards',
      },
      keyframes: {
        ticker: {
          '0%':   { transform: 'translateX(0)' },
          '100%': { transform: 'translateX(-50%)' },
        },
        fadeUp: {
          from: { opacity: '0', transform: 'translateY(16px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}

export default config
