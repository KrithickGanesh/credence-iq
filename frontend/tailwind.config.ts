import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#0f172a",
        canvas: "#f4f6f8",
        brand: {
          50: "#ecfdf8",
          100: "#d1faee",
          200: "#a7f3da",
          300: "#6ee7bf",
          400: "#34d399",
          500: "#10b981",
          600: "#0f9f7a",
          700: "#0f766e",
          800: "#115e59",
          900: "#134e4a",
        },
        navy: {
          800: "#111c30",
          900: "#0b1220",
          950: "#070d18",
        },
      },
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        serif: ["Georgia", "Cambria", "Times New Roman", "serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(15, 23, 42, 0.04), 0 8px 24px rgba(15, 23, 42, 0.04)",
        lift: "0 18px 40px rgba(15, 23, 42, 0.10)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-ring": {
          "0%": { boxShadow: "0 0 0 0 rgba(16, 185, 129, 0.5)" },
          "70%": { boxShadow: "0 0 0 6px rgba(16, 185, 129, 0)" },
          "100%": { boxShadow: "0 0 0 0 rgba(16, 185, 129, 0)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.35s ease-out both",
        "pulse-ring": "pulse-ring 2.2s infinite",
      },
    },
  },
  plugins: [],
};

export default config;
