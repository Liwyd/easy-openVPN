import { Box, Heading, Text, VStack } from "@chakra-ui/react";
import { FiUsers } from "react-icons/fi";

export default function Users() {
  return (
    <VStack align="stretch" gap={6}>
      <Heading size="lg">Users</Heading>
      <Box
        border="1px solid"
        borderColor="border.strong"
        borderRadius="lg"
        p={12}
        bg="bg"
        textAlign="center"
      >
        <FiUsers size={40} style={{ margin: "0 auto 16px", opacity: 0.3 }} />
        <Text color="fg.muted">User management coming in the next stage.</Text>
      </Box>
    </VStack>
  );
}
