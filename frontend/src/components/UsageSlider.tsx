import { Box, Text, HStack, Slider } from "@chakra-ui/react";
import { formatBytes } from "../utils/formatByte";
import type { User } from "../types/User";

export function getResetStrategyText(strategy: string): string {
  switch (strategy) {
    case "day":
      return "Daily";
    case "week":
      return "Weekly";
    case "month":
      return "Monthly";
    case "year":
      return "Yearly";
    default:
      return strategy.charAt(0).toUpperCase() + strategy.slice(1);
  }
}

interface UsageSliderProps {
  user: User;
}

export default function UsageSlider({ user }: UsageSliderProps) {
  const used = Math.min(
    user.data_used,
    user.data_limit ?? Number.MAX_SAFE_INTEGER,
  );

  const strategy = getResetStrategyText(user.data_limit_reset_strategy);

  return (
    <Box>
      <HStack justify="space-between" mb={1}>
        <Text fontSize="xs" color="fg.muted">
          {formatBytes(user.data_used)} used
        </Text>
        <Text fontSize="xs" color="fg.muted">
          {user.data_limit ? formatBytes(user.data_limit) : "Unlimited"} {strategy}
        </Text>
      </HStack>
      {user.data_limit ? (
        <Slider.Root
          value={[used]}
          max={user.data_limit}
          size="sm"
          colorPalette={used / user.data_limit > 0.8 ? "orange" : "green"}
        >
          <Slider.Control>
            <Slider.Track>
              <Slider.Range />
            </Slider.Track>
          </Slider.Control>
        </Slider.Root>
      ) : (
        <Slider.Root value={[0]} max={1} size="sm" colorPalette="green">
          <Slider.Control>
            <Slider.Track>
              <Slider.Range />
            </Slider.Track>
          </Slider.Control>
        </Slider.Root>
      )}
    </Box>
  );
}
