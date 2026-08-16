import {
  Box,
  Flex,
  Text,
  Button,
  Icon,
  Menu,
  Portal,
} from "@chakra-ui/react";
import { FiSun, FiMoon, FiLogOut, FiMenu, FiGrid, FiUsers, FiShield, FiDollarSign, FiSettings, FiServer, FiBarChart2 } from "react-icons/fi";
import { useLocation, useNavigate } from "react-router-dom";
import { useColorMode } from "./ui/color-mode";
import { useAuth } from "../context/AuthContext";
import { HOME_PATH } from "../lib/base";
import { Language } from "./Language";
import { useTranslation } from "react-i18next";

export default function Header() {
  const { colorMode, toggleColorMode } = useColorMode();
  const { admin, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const { t } = useTranslation();

  const NAV_ITEMS = [
    { label: t("header.users"), icon: FiUsers, path: HOME_PATH },
    { label: t("header.dashboard"), icon: FiGrid, path: "/dashboard" },
    { label: t("header.admins"), icon: FiShield, path: "/admins", sudoOnly: true },
    { label: t("header.billing"), icon: FiDollarSign, path: "/billing", sudoOnly: true },
  ] as const;

  const MENU_ITEMS = [
    ...NAV_ITEMS,
    { label: t("header.settings"), icon: FiSettings, path: "/settings" },
  ];

  const isSudo = admin?.is_sudo;
  const visibleNav = NAV_ITEMS.filter(
    (item) => !("sudoOnly" in item && item.sudoOnly) || isSudo,
  );
  const visibleMenu = MENU_ITEMS.filter(
    (item) => !("sudoOnly" in item && item.sudoOnly) || isSudo,
  );

  const title =
    visibleMenu.find((i) => location.pathname === i.path)?.label ?? t("header.users");

  return (
    <Flex align="center" justify="space-between" gap={2} wrap="wrap" mb={4}>
      <Text as="h1" fontWeight="semibold" fontSize="2xl">
        {title}
      </Text>

      <Box dir="rtl">
        <Flex align="center" gap={2}>
        <Menu.Root>
          <Menu.Trigger asChild>
            <Button variant="outline" size="sm" aria-label={t("header.menu")}>
              <Icon as={FiMenu} boxSize="4" />
            </Button>
          </Menu.Trigger>
          <Portal>
            <Menu.Positioner>
              <Menu.Content minW="190px">
                {visibleNav.map((item) => (
                  <Menu.Item
                    key={item.path}
                    value={item.path}
                    fontWeight={location.pathname === item.path ? "bold" : "normal"}
                    onClick={() => navigate(item.path)}
                  >
                    <Icon as={item.icon} mr={2} />
                    {item.label}
                  </Menu.Item>
                ))}
                <Menu.Separator />
                <Menu.Item value="nodes-settings" disabled>
                  <Icon as={FiServer} mr={2} />
                  {t("header.nodeSettings")}
                </Menu.Item>
                <Menu.Item value="nodes-usage" disabled>
                  <Icon as={FiBarChart2} mr={2} />
                  {t("header.nodesUsage")}
                </Menu.Item>
                <Menu.Separator />
                <Menu.Item value="logout" onClick={logout}>
                  <Icon as={FiLogOut} mr={2} />
                  {t("header.logout")}
                </Menu.Item>
              </Menu.Content>
            </Menu.Positioner>
          </Portal>
        </Menu.Root>

        <Button
          variant="outline"
          size="sm"
          aria-label={t("header.settings")}
          title={t("header.settings")}
          onClick={() => navigate("/settings")}
        >
          <Icon as={FiSettings} boxSize="4" />
        </Button>

        <Language />

        <Button
          onClick={toggleColorMode}
          variant="outline"
          size="sm"
          aria-label={t("header.switchTheme")}
        >
          <Icon as={colorMode === "light" ? FiMoon : FiSun} boxSize="4" />
        </Button>
        </Flex>
      </Box>
    </Flex>
  );
}
