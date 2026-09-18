/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        paper: '#F6F3EC',
        sheet: '#FFFDF8',
        ink: '#16150F',
        smoke: '#5C574A',
        line: '#16150F',
        signal: '#FF4D00',
        moss: '#0C3B2E',
        sun: '#FFC91A',
      },
      fontFamily: {
        display: ['"Archivo Black"', 'Archivo', 'sans-serif'],
        head: ['"Schibsted Grotesk"', 'Inter', 'sans-serif'],
        body: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      boxShadow: {
        lift: '0 16px 40px -16px rgba(22,21,15,0.35)',
        card: '0 10px 28px -14px rgba(22,21,15,0.30)',
      },
      keyframes: {
        marquee: { from: { transform: 'translateX(0)' }, to: { transform: 'translateX(-50%)' } },
        blink: { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.15 } },
      },
      animation: {
        marquee: 'marquee 28s linear infinite',
        blink: 'blink 1.6s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
