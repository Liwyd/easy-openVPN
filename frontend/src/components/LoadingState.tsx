import { Flex, Spinner } from "@chakra-ui/react";

export default function LoadingState() {
  return (
    <Flex align="center" justify="center" py={20}>
      <Spinner size="lg" color="accent" />
    </Flex>
  );
}
