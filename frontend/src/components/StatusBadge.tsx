import { Badge, Flex, Text } from "@chakra-ui/react";
import { statusColors, statusIcons } from "../constants/UserSettings";
import type { UserStatus } from "../types/User";
import { useTranslation } from "react-i18next";
import { relativeTime } from "../utils/dateFormatter";

export default function StatusBadge({
  status,
  expiryDate,
  showDetail = true,
}: {
  status: string;
  expiryDate?: string | null;
  showDetail?: boolean;
}) {
  const { t } = useTranslation();
  const s = status as UserStatus;
  const Icon = statusIcons[s] ?? statusIcons.disabled;
  const label = t(`status.${s}` as const);
  return (
    <Flex align="center" wrap="nowrap" gap={2}>
      <Badge
        colorPalette={statusColors[s] ?? "gray"}
        rounded="full"
        display="inline-flex"
        px={3}
        py={1}
        columnGap={2}
        alignItems="center"
        flexShrink={0}
      >
        <Icon style={{ display: "inline-block", width: 16, height: 16 }} />
        {showDetail && (
          <Text
            textTransform="capitalize"
            fontSize=".875rem"
            lineHeight="1.25rem"
            fontWeight="medium"
            letterSpacing="tighter"
          >
            {label}
          </Text>
        )}
      </Badge>
      {showDetail && expiryDate && (
        <Text
          fontSize="xs"
          fontWeight="medium"
          color="gray.600"
          whiteSpace="nowrap"
          _dark={{ color: "gray.400" }}
        >
          {t("table.expires", { time: relativeTime(expiryDate) })}
        </Text>
      )}
    </Flex>
  );
}
