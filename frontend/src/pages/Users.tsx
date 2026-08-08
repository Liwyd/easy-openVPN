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
        <Box color="accent" opacity={0.3} display="flex" justifyContent="center" mb={4}>
          <FiUsers size={40} />
        </Box>
        <Text color="fg.muted" fontSize="sm">User management coming in the next stage.</Text>
      </Box>
    </VStack>
  );
}
