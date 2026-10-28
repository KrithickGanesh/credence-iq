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
        canvas: "#f7f8fa",
        brand: {
          50: "#f0f9f5",
          100: "#dcf1e8",
          200: "#bfe3d4",
          300: "#93d0b9",
          400: "#5fb899",
          500: "#35a17e",
          600: "#14866a",
          700: "#0f6c58",
          800: "#0e5749",
          900: "#0d4a3e",
        },
        navy: {
          800: "#111c30",
          900: "#0b1220",
          950: "#070d18",
        },
      },
      fontFamily: {
        sans: [
          "var(--font-sans, ui-sans-serif)",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        serif: ["Georgia", "Cambria", "Times New Roman", "serif"],
        mono: ["var(--font-mono, ui-monospace)", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(15, 23, 42, 0.05), 0 1px 1px rgba(15, 23, 42, 0.03)",
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
