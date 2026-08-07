import { ThemeProvider, useTheme } from "next-themes";
import { ChakraProvider } from "@chakra-ui/react";
import { system } from "../../theme";

export interface ColorModeProviderProps {
  children: React.ReactNode;
}

export function ColorModeProvider({ children }: ColorModeProviderProps) {
  return (
    <ThemeProvider attribute="class" defaultTheme="light" enableSystem>
      <ChakraProvider value={system}>{children}</ChakraProvider>
    </ThemeProvider>
  );
}

export function useColorMode() {
  const { theme, setTheme } = useTheme();
  return {
    colorMode: (theme ?? "light") as "light" | "dark",
    toggleColorMode: () => setTheme(theme === "light" ? "dark" : "light"),
  };
}

export function useColorModeValue<T>(light: T, dark: T): T {
  const { colorMode } = useColorMode();
  return colorMode === "light" ? light : dark;
}
