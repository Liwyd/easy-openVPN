import type { SystemStyleObject } from "@chakra-ui/react";

export const buttonSolid: SystemStyleObject = {
  bg: "accent",
  color: "accent.fg",
  _hover: { bg: "accent.hover" },
  _active: { bg: "primary.700" },
};

export const buttonOutline: SystemStyleObject = {
  borderColor: "border.strong",
  color: "fg",
  _hover: { bg: "bg.muted", borderColor: "border.strong" },
};

export const card: SystemStyleObject = {
  border: "1px solid",
  borderColor: "border.strong",
  borderRadius: "12px",
  bg: "bg.subtle",
};

export const tableRoot: SystemStyleObject = {
  border: "1px solid",
  borderColor: "border.strong",
  borderRadius: "8px",
  overflow: "hidden",
  bg: "bg",
};

export const badgeActive: SystemStyleObject = {
  colorPalette: "green",
  borderRadius: "full",
  px: 3,
  py: 1,
  fontSize: "xs",
  fontWeight: "medium",
};

export const badgeLimited: SystemStyleObject = {
  colorPalette: "red",
  borderRadius: "full",
  px: 3,
  py: 1,
  fontSize: "xs",
  fontWeight: "medium",
};

export const badgeExpired: SystemStyleObject = {
  colorPalette: "orange",
  borderRadius: "full",
  px: 3,
  py: 1,
  fontSize: "xs",
  fontWeight: "medium",
};

export const badgeDisabled: SystemStyleObject = {
  colorPalette: "gray",
  borderRadius: "full",
  px: 3,
  py: 1,
  fontSize: "xs",
  fontWeight: "medium",
};
