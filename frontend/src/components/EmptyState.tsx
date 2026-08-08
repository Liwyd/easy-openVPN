import { Text, VStack } from "@chakra-ui/react";
import type { ReactNode } from "react";

export default function EmptyState({ icon: Icon, message }: { icon: ReactNode; message: string }) {
  return (
    <VStack py={12} gap={3}>
      {Icon}
      <Text color="fg.muted" fontSize="sm">
        {message}
      </Text>
    </VStack>
  );
}
