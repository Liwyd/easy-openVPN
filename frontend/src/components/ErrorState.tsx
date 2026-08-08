import { Text, VStack } from "@chakra-ui/react";
import { FiAlertTriangle } from "react-icons/fi";

export default function ErrorState({ message }: { message: string }) {
  return (
    <VStack py={12} gap={3}>
      <FiAlertTriangle size={32} style={{ opacity: 0.4, color: "var(--chakra-colors-accent)" }} />
      <Text color="fg.muted" fontSize="sm">
        {message}
      </Text>
    </VStack>
  );
}
