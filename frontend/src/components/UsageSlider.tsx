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
  const isUnlimited = !user.data_limit;
  const isReached = !isUnlimited && user.data_limit !== null && (used / user.data_limit) * 100 >= 100;

  return (
    <Box>
      {user.data_limit ? (
        <Slider.Root
          value={[used]}
          max={user.data_limit}
          size="sm"
          colorPalette={isReached ? "red" : "accent"}
          mb={2}
        >
          <Slider.Control>
            <Slider.Track h="6px" borderRadius="full">
              <Slider.Range borderRadius="full" />
            </Slider.Track>
          </Slider.Control>
        </Slider.Root>
      ) : (
        <Slider.Root value={[0]} max={1} size="sm" colorPalette="accent" mb={2}>
          <Slider.Control>
            <Slider.Track h="6px" borderRadius="full">
              <Slider.Range borderRadius="full" />
            </Slider.Track>
          </Slider.Control>
        </Slider.Root>
      )}
      <HStack
        justifyContent="space-between"
        fontSize="xs"
        fontWeight="medium"
        color="gray.600"
        _dark={{ color: "gray.400" }}
      >
        <Text>
          {formatBytes(user.data_used)} /{" "}
          {isUnlimited ? (
            <Text as="span" fontFamily="system-ui">
              ∞
            </Text>
          ) : (
            formatBytes(user.data_limit!) +
            (strategy ? ` ${strategy}` : "")
          )}
        </Text>
        <Text>
          {t("usage.total")}: {formatBytes(user.data_used)}
        </Text>
      </HStack>
    </Box>
  );
}
