import { Badge } from "@chakra-ui/react";
import { statusColors, statusIcons } from "../constants/UserSettings";
import type { UserStatus } from "../types/User";

const STATUS_LABEL: Record<UserStatus, string> = {
  active: "Active",
  limited: "Limited",
  expired: "Expired",
  disabled: "Disabled",
};

export default function StatusBadge({ status }: { status: string }) {
  const s = status as UserStatus;
  const Icon = statusIcons[s] ?? statusIcons.disabled;
  const label = STATUS_LABEL[s] ?? "Disabled";
  return (
    <Badge
      colorPalette={statusColors[s] ?? "gray"}
      borderRadius="full"
      px={3}
      py={1}
      fontSize="sm"
      fontWeight="medium"
      lineHeight="1.25rem"
      letterSpacing="tighter"
      title={label}
    >
      <Icon style={{ display: "inline-block", marginRight: 6 }} />
      {label}
    </Badge>
  );
}
