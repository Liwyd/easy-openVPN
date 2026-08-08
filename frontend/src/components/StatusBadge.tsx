import { Badge } from "@chakra-ui/react";

type Status = "active" | "limited" | "expired" | "disabled";

const STATUS_CONFIG: Record<Status, { label: string; colorPalette: string }> = {
  active: { label: "Active", colorPalette: "green" },
  limited: { label: "Limited", colorPalette: "orange" },
  expired: { label: "Expired", colorPalette: "red" },
  disabled: { label: "Disabled", colorPalette: "gray" },
};

export default function StatusBadge({ status }: { status: string }) {
  const config = STATUS_CONFIG[status as Status] ?? STATUS_CONFIG.disabled;
  return (
    <Badge colorPalette={config.colorPalette} borderRadius="full" px={2.5} py={0.5} fontSize="xs" fontWeight="semibold">
      {config.label}
    </Badge>
  );
}
