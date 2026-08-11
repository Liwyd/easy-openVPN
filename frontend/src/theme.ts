import { createSystem, defaultConfig, defineConfig } from "@chakra-ui/react";

const config = defineConfig({
  globalCss: {
    body: {
      fontFamily:
        "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif",
    },
    "table thead th": {
      background: "var(--chakra-colors-bg-subtle)",
      fontSize: "xs",
      fontWeight: "bold",
      textTransform: "uppercase",
      letterSpacing: "wider",
      color: "var(--chakra-colors-fg-muted)",
    },
    "table thead th:first-of-type": {
      borderTopLeftRadius: "8px",
    },
    "table thead th:last-of-type": {
      borderTopRightRadius: "8px",
    },
    "table tbody tr:last-of-type td:first-of-type": {
      borderBottomLeftRadius: "8px",
    },
    "table tbody tr:last-of-type td:last-of-type": {
      borderBottomRightRadius: "8px",
    },
  },
  theme: {
    tokens: {
      fonts: {
        body: {
          value:
            "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif",
        },
        heading: {
          value:
            "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif",
        },
      },
      shadows: {
        outline: { value: "0 0 0 2px var(--chakra-colors-primary-200)" },
      },
      colors: {
        primary: {
          50: { value: "#fce9e9" },
          100: { value: "#f9d3d3" },
          200: { value: "#f3b1b1" },
          300: { value: "#ec8e8e" },
          400: { value: "#e36c6c" },
          500: { value: "#d94f4f" },
          600: { value: "#c13f3f" },
          700: { value: "#a33333" },
          800: { value: "#852828" },
          900: { value: "#691f1f" },
        },
        gray: {
          750: { value: "#222C3B" },
        },
      },
    },
    semanticTokens: {
      colors: {
        bg: {
          DEFAULT: { value: { base: "#ffffff", _dark: "#1A202C" } },
          subtle: { value: { base: "#F9FAFB", _dark: "#222C3B" } },
          muted: { value: { base: "#EDF2F7", _dark: "#2D3748" } },
        },
        fg: {
          DEFAULT: { value: { base: "#1A202C", _dark: "#F7FAFC" } },
          muted: { value: { base: "#718096", _dark: "#A0AEC0" } },
          subtle: { value: { base: "#A0AEC0", _dark: "#718096" } },
        },
        border: {
          DEFAULT: { value: { base: "#d2d2d4", _dark: "#4A5568" } },
          strong: { value: { base: "#d2d2d4", _dark: "#4A5568" } },
        },
        accent: {
          DEFAULT: { value: { base: "#d94f4f", _dark: "#e36c6c" } },
          hover: { value: { base: "#c13f3f", _dark: "#ec8e8e" } },
          subtle: { value: { base: "#fce9e9", _dark: "#382a2a" } },
          fg: { value: "#ffffff" },
        },
      },
    },
  },
});

export const system = createSystem(defaultConfig, config);
