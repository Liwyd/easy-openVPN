import {
  Box,
  Container,
  Heading,
  Text,
  VStack,
  Button,
  Icon,
} from "@chakra-ui/react";
import { FiSun, FiMoon } from "react-icons/fi";
import { useColorMode } from "./components/ui/color-mode";

function ColorModeToggle() {
  const { colorMode, toggleColorMode } = useColorMode();
  return (
    <Button
      onClick={toggleColorMode}
      variant="outline"
      size="sm"
    >
      <Icon as={colorMode === "light" ? FiMoon : FiSun} />
      {" "}
      {colorMode === "light" ? "Dark" : "Light"}
    </Button>
  );
}

function App() {
  return (
    <Box minH="100vh" bg="bg">
      <Container maxW="container.md" py={10}>
        <VStack gap={8} align="center">
          <Heading size="xl" color="brand.600">
            eovpanel
          </Heading>
          <Text color="fg.muted" fontSize="lg">
            OpenVPN Management Panel
          </Text>

          <Box
            bg="bg.subtle"
            border="1px solid"
            borderColor="border"
            borderRadius="lg"
            p={8}
            w="100%"
            textAlign="center"
          >
            <Heading size="md" mb={4}>
              Welcome
            </Heading>
            <Text color="fg.muted" mb={6}>
              This is a placeholder page. The full dashboard is coming in
              future stages.
            </Text>
            <ColorModeToggle />
          </Box>
        </VStack>
      </Container>
    </Box>
  );
}

export default App;
