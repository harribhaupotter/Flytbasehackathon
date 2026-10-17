/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        dark: {
          bg: '#0A0A0E',
          surface: '#111216',
          elevated: '#17181F',
          muted: '#20222B',
          border: 'rgba(255, 255, 255, 0.08)',
          'border-subtle': 'rgba(255, 255, 255, 0.04)',
          text: '#EDEDEF',
          'text-muted': '#8E909B',
        },
        light: {
          bg: '#F8F9FA',
          surface: '#FFFFFF',
          elevated: '#F1F3F5',
          muted: '#E9ECEF',
          border: 'rgba(0, 0, 0, 0.08)',
          'border-subtle': 'rgba(0, 0, 0, 0.04)',
          text: '#1A1A1E',
          'text-muted': '#6C727F',
        },
        accent: {
          DEFAULT: 'var(--accent-color)',
          hover: 'var(--accent-hover)',
          muted: 'var(--accent-muted)',
          glow: 'var(--accent-glow)',
          fg: 'var(--accent-fg)',
        }
      },
      fontFamily: {
        sans: ['Inter', 'Geist', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Menlo', 'Monaco', 'Courier New', 'monospace'],
      },
      animation: {
        'fade-slide-up': 'fadeSlideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'fade-in': 'fadeIn 0.2s ease-out forwards',
        'ambient-pulse': 'ambientGlow 10s ease-in-out infinite alternate',
        'shimmer': 'shimmer 2s linear infinite',
      },
      keyframes: {
        fadeSlideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        ambientGlow: {
          '0%': { opacity: '0.4', transform: 'scale(0.98)' },
          '100%': { opacity: '0.8', transform: 'scale(1.05)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        }
      },
      lineHeight: {
        relaxed: '1.65',
      }
    },
  },
  plugins: [],
}
