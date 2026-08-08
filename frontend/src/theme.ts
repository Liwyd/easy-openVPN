import { createSystem, defaultConfig, defineConfig } from "@chakra-ui/react";

const config = defineConfig({
  theme: {
    tokens: {
      colors: {
        brand: {
          50: { value: "#fff5f5" },
          100: { value: "#ffe3e3" },
          200: { value: "#ffc9c9" },
          300: { value: "#ffa8a8" },
          400: { value: "#ff6b6b" },
          500: { value: "#fa5252" },
          600: { value: "#f03e3e" },
          700: { value: "#e03131" },
          800: { value: "#c92a2a" },
          900: { value: "#a52222" },
          950: { value: "#8b1a1a" },
        },
      },
    },
    semanticTokens: {
      colors: {
        bg: {
          DEFAULT: { value: { base: "white", _dark: "#0a0a0a" } },
          subtle: { value: { base: "#fafafa", _dark: "#141414" } },
          muted: { value: { base: "#f5f5f5", _dark: "#1a1a1a" } },
        },
        fg: {
          DEFAULT: { value: { base: "#171717", _dark: "#ededed" } },
          muted: { value: { base: "#737373", _dark: "#a3a3a3" } },
          subtle: { value: { base: "#a3a3a3", _dark: "#525252" } },
        },
        border: {
          DEFAULT: { value: { base: "#e5e5e5", _dark: "#262626" } },
          strong: { value: { base: "#fa5252", _dark: "#7f1d1d" } },
        },
        accent: {
          DEFAULT: { value: { base: "#fa5252", _dark: "#dc2626" } },
          hover: { value: { base: "#f03e3e", _dark: "#ef4444" } },
          subtle: { value: { base: "#fff5f5", _dark: "#450a0a" } },
          fg: { value: { base: "#ffffff", _dark: "#ffffff" } },
        },
      },
    },
  },
});

export const system = createSystem(defaultConfig, config);
