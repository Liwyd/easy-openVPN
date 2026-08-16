import {
  createSystem,
  defaultConfig,
  defineConfig,
  defineRecipe,
  defineSlotRecipe,
} from "@chakra-ui/react";

const buttonRecipe = defineRecipe({
  base: {
    borderRadius: "md",
  },
  variants: {
    variant: {
      outline: {
        borderColor: "border.DEFAULT",
        _hover: { bg: "bg.muted", borderColor: "border.DEFAULT" },
        _expanded: { bg: "bg.muted", borderColor: "border.DEFAULT" },
      },
    },
  },
});

const toastRecipe = defineSlotRecipe({
  slots: ["root", "title", "description", "indicator", "actionTrigger", "closeTrigger"],
  className: "chakra-toast",
  base: {
    root: {
      width: "auto",
      maxWidth: "420px",
      display: "flex",
      alignItems: "flex-start",
      position: "relative",
      gap: "2.5",
      py: "3",
      ps: "3.5",
      pe: "6",
      borderRadius: "l2",
      translate: "var(--x) var(--y)",
      scale: "var(--scale)",
      zIndex: "var(--z-index)",
      height: "var(--height)",
      opacity: "var(--opacity)",
      willChange: "translate, opacity, scale",
      transition:
        "translate 400ms, scale 400ms, opacity 400ms, height 400ms, box-shadow 200ms",
      transitionTimingFunction: "cubic-bezier(0.21, 1.02, 0.73, 1)",
      _closed: {
        transition: "translate 400ms, scale 400ms, opacity 200ms",
        transitionTimingFunction: "cubic-bezier(0.06, 0.71, 0.55, 1)",
      },
      bg: "bg.panel",
      color: "fg",
      boxShadow: "xl",
      "--toast-trigger-bg": "colors.bg.muted",
      "&[data-type=warning]": {
        bg: "orange.solid",
        color: "orange.contrast",
        "--toast-trigger-bg": "{white/10}",
        "--toast-border-color": "{white/40}",
      },
      "&[data-type=success]": {
        bg: "green.solid",
        color: "green.contrast",
        "--toast-trigger-bg": "{white/10}",
        "--toast-border-color": "{white/40}",
      },
      "&[data-type=error]": {
        bg: "red.solid",
        color: "red.contrast",
        "--toast-trigger-bg": "{white/10}",
        "--toast-border-color": "{white/40}",
      },
    },
    title: {
      fontWeight: "medium",
      textStyle: "sm",
      marginEnd: "2",
    },
    description: {
      display: "inline",
      textStyle: "sm",
      opacity: "0.8",
    },
    indicator: {
      flexShrink: "0",
      boxSize: "5",
    },
    closeTrigger: {
      position: "absolute",
      top: "1",
      insetEnd: "1",
      padding: "1",
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      color: "{currentColor/60}",
      borderRadius: "l2",
      textStyle: "md",
      transition: "background 200ms",
      _icon: {
        boxSize: "1em",
      },
    },
  },
});

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
      borderBottom: "1px solid",
      borderColor: "var(--chakra-colors-border)",
    },
    "table thead th:first-of-type": {
      borderTopLeftRadius: "8px",
    },
    "table thead th:last-of-type": {
      borderTopRightRadius: "8px",
    },
    "table tbody tr": {
      borderBottom: "1px solid",
      borderColor: "var(--chakra-colors-border)",
    },
    "table tbody tr:last-of-type": {
      borderBottom: "none",
    },
    "table tbody td": {
      py: "14px",
    },
    "table tbody tr:last-of-type td:first-of-type": {
      borderBottomLeftRadius: "8px",
    },
    "table tbody tr:last-of-type td:last-of-type": {
      borderBottomRightRadius: "8px",
    },
  },
  theme: {
    slotRecipes: {
      toast: toastRecipe,
    },
    recipes: {
      button: buttonRecipe,
    },
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
          panel: { value: { base: "#ffffff", _dark: "#1A202C" } },
          emphasized: { value: { base: "#EDF2F7", _dark: "#2D3748" } },
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
