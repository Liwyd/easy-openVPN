import { Box, Flex, Text } from "@chakra-ui/react";
import { card } from "../theme-components";

interface StatCardProps {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  color?: string;
  valueColor?: string;
}

export default function StatCard({
  label,
  value,
  icon,
  color = "accent",
  valueColor,
}: StatCardProps) {
  return (
    <Box css={card} p={5}>
      <Flex align="center" gap={3}>
        <Box color={color} p={2} borderRadius="md" bg={`${color}/10`}>
          {icon}
        </Box>
        <Box>
          <Text
            fontSize="xs"
            color="fg.muted"
            textTransform="uppercase"
            fontWeight="medium"
          >
            {label}
          </Text>
          <Text fontSize="2xl" fontWeight="bold" color={valueColor}>
            {value}
          </Text>
        </Box>
      </Flex>
    </Box>
  );
}
