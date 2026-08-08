import { Box, Heading, Text, VStack } from "@chakra-ui/react";
import { FiSettings } from "react-icons/fi";

export default function Settings() {
  return (
    <VStack align="stretch" gap={6}>
      <Heading size="lg">Settings</Heading>
      <Box
        border="1px solid"
        borderColor="border.strong"
        borderRadius="lg"
        p={12}
        bg="bg"
        textAlign="center"
      >
        <FiSettings size={40} style={{ margin: "0 auto 16px", opacity: 0.3 }} />
        <Text color="fg.muted">Server settings coming in the next stage.</Text>
      </Box>
    </VStack>
  );
}
