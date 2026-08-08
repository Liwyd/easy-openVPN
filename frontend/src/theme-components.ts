import type { SystemStyleObject } from "@chakra-ui/react";

export const buttonSolid: SystemStyleObject = {
  bg: "accent",
  color: "accent.fg",
  _hover: { bg: "accent.hover" },
  _active: { bg: "brand.700" },
};

export const buttonOutline: SystemStyleObject = {
  borderColor: "border.strong",
  color: "accent",
  _hover: { bg: "accent.subtle", borderColor: "accent" },
};

export const card: SystemStyleObject = {
  border: "1px solid",
  borderColor: "border.strong",
  borderRadius: "lg",
  bg: "bg",
};

export const tableRoot: SystemStyleObject = {
  border: "1px solid",
  borderColor: "border.strong",
  borderRadius: "lg",
  overflow: "hidden",
};

export const badgeActive: SystemStyleObject = {
  colorPalette: "green",
  borderRadius: "full",
  px: 2.5,
  py: 0.5,
  fontSize: "xs",
  fontWeight: "semibold",
};

export const badgeLimited: SystemStyleObject = {
  colorPalette: "orange",
  borderRadius: "full",
  px: 2.5,
  py: 0.5,
  fontSize: "xs",
  fontWeight: "semibold",
};

export const badgeExpired: SystemStyleObject = {
  colorPalette: "red",
  borderRadius: "full",
  px: 2.5,
  py: 0.5,
  fontSize: "xs",
  fontWeight: "semibold",
};

export const badgeDisabled: SystemStyleObject = {
  colorPalette: "gray",
  borderRadius: "full",
  px: 2.5,
  py: 0.5,
  fontSize: "xs",
  fontWeight: "semibold",
};
