import { Box, Heading } from "@chakra-ui/react";
import { card } from "../theme-components";

export default function SectionCard({
  title,
  children,
}: {
  title: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Box css={card} p={6}>
      <Heading size="sm" mb={4}>
        {title}
      </Heading>
      {children}
    </Box>
  );
}
