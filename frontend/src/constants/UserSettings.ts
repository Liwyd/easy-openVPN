import {
  FiWifi,
  FiSlash,
  FiClock,
  FiAlertTriangle,
} from "react-icons/fi";
import type { UserStatus } from "../types/User";

export const statusIcons: Record<UserStatus, React.ComponentType<{ style?: React.CSSProperties }>> = {
  active: FiWifi,
  limited: FiAlertTriangle,
  expired: FiClock,
  disabled: FiSlash,
};

export const statusColors: Record<UserStatus, string> = {
  active: "green",
  limited: "orange",
  expired: "red",
  disabled: "gray",
};

export const statusFilterItems: Array<{ label: string; value: string }> = [
  { label: "All Statuses", value: "all" },
  { label: "Active", value: "active" },
  { label: "Limited", value: "limited" },
  { label: "Expired", value: "expired" },
  { label: "Disabled", value: "disabled" },
];
