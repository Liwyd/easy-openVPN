import { createSystem, defaultConfig, defineConfig } from "@chakra-ui/react";

const config = defineConfig({
  globalCss: {
    body: {
      fontFamily:
        "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif",
    },
    "table thead th": {
      background: "var(--chakra-colors-bg-subtle)",
      fontSize: ".85rem",
      fontWeight: "extrabold",
      textTransform: "uppercase",
      letterSpacing: "wider",
      color: "var(--chakra-colors-fg-muted)",
      borderColor: "var(--chakra-colors-border) !important",
      borderBottomColor: "var(--chakra-colors-border) !important",
    },
    "table thead th:first-of-type": {
      borderTopLeftRadius: "8px",
      borderLeft: "1px solid",
      borderColor: "var(--chakra-colors-border) !important",
    },
    "table thead th:last-of-type": {
      borderTopRightRadius: "8px",
      borderRight: "1px solid",
      borderColor: "var(--chakra-colors-border) !important",
    },
    "table td:first-of-type": {
      borderLeft: "1px solid",
      borderColor: "var(--chakra-colors-border)",
    },
    "table td:last-of-type": {
      borderRight: "1px solid",
      borderColor: "var(--chakra-colors-border)",
    },
    "table tbody tr:last-of-type td:first-of-type": {
      borderBottomLeftRadius: "8px",
      borderBottom: "1px solid",
      borderColor: "var(--chakra-colors-border)",
    },
    "table tbody tr:last-of-type td:last-of-type": {
      borderBottomRightRadius: "8px",
      borderBottom: "1px solid",
      borderColor: "var(--chakra-colors-border)",
    },
    "table tr:hover td": {
      background: "var(--chakra-colors-bg-muted)",
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
          50: { value: "#9cb7f2" },
          100: { value: "#88a9ef" },
          200: { value: "#749aec" },
          300: { value: "#618ce9" },
          400: { value: "#4d7de7" },
          500: { value: "#396fe4" },
          600: { value: "#3364cd" },
          700: { value: "#2e59b6" },
          800: { value: "#284ea0" },
          900: { value: "#224389" },
        },
        "light-border": {
          value: "#d2d2d4",
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
          DEFAULT: { value: { base: "#d2d2d4", _dark: "#718096" } },
          strong: { value: { base: "#d2d2d4", _dark: "#718096" } },
        },
        accent: {
          DEFAULT: { value: { base: "#396fe4", _dark: "#4d7de7" } },
          hover: { value: { base: "#3364cd", _dark: "#618ce9" } },
          subtle: { value: { base: "#eef2fe", _dark: "#1a2740" } },
          fg: { value: "#ffffff" },
        },
      },
    },
  },
});

export const system = createSystem(defaultConfig, config);
