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
          400: { value: "#ff8787" },
          500: { value: "#ff6b6b" },
          600: { value: "#fa5252" },
          700: { value: "#f03e3e" },
          800: { value: "#e03131" },
          900: { value: "#c92a2a" },
          950: { value: "#a52222" },
        },
      },
    },
    semanticTokens: {
      colors: {
        bg: {
          DEFAULT: { value: { base: "white", _dark: "gray.900" } },
          subtle: { value: { base: "gray.50", _dark: "gray.800" } },
        },
        fg: {
          DEFAULT: { value: { base: "gray.800", _dark: "white" } },
          muted: { value: { base: "gray.500", _dark: "gray.400" } },
        },
        border: {
          DEFAULT: { value: { base: "brand.200", _dark: "gray.700" } },
        },
      },
    },
  },
});

export const system = createSystem(defaultConfig, config);
