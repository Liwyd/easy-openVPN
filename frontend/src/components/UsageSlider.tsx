import { Box, Text, HStack, Slider } from "@chakra-ui/react";
import { useTranslation } from "react-i18next";
import { formatBytes } from "../utils/formatByte";
import type { User } from "../types/User";

export function getResetStrategyText(
  strategy: string,
  t?: (key: string) => string,
): string {
  switch (strategy) {
    case "no_reset":
      return "";
    case "day":
      return t ? t("usage.daily") : "Daily";
    case "week":
      return t ? t("usage.weekly") : "Weekly";
    case "month":
      return t ? t("usage.monthly") : "Monthly";
    case "year":
      return t ? t("usage.yearly") : "Yearly";
    default:
      return strategy.charAt(0).toUpperCase() + strategy.slice(1);
  }
}

interface UsageSliderProps {
  user: User;
}

export default function UsageSlider({ user }: UsageSliderProps) {
  const { t } = useTranslation();
  const used = Math.min(
    user.data_used,
    user.data_limit ?? Number.MAX_SAFE_INTEGER,
  );

  const strategy = getResetStrategyText(user.data_limit_reset_strategy, t);

  return (
    <Box>
      <HStack justify="space-between" mb={1}>
        <Text fontSize="xs" color="fg.muted">
          {formatBytes(user.data_used)} {t("usage.used")}
        </Text>
        <Text fontSize="xs" color="fg.muted">
          {user.data_limit ? formatBytes(user.data_limit) : t("usage.unlimited")}
          {strategy ? ` ${strategy}` : ""}
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
