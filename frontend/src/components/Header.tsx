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

const iconBtnStyle = {
  width: "32px",
  height: "32px",
  minWidth: "32px",
  minHeight: "32px",
  p: 0,
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  borderRadius: "md",
};

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
        <Flex align="center" gap={1.5}>
          <Menu.Root>
            <Menu.Trigger asChild>
              <Button
                variant="outline"
                size="sm"
                aria-label={t("header.menu")}
                css={iconBtnStyle}
              >
                <Icon as={FiMenu} boxSize="4" />
              </Button>
            </Menu.Trigger>
            <Portal>
              <Menu.Positioner>
                <Menu.Content
                  minW="200px"
                  bg="#1A202C"
                  borderColor="#4A5568"
                  borderRadius="lg"
                  boxShadow="lg"
                  p={1.5}
                  color="white"
                  zIndex={9999}
                >
                  {visibleNav.map((item) => (
                    <Menu.Item
                      key={item.path}
                      value={item.path}
                      fontWeight={location.pathname === item.path ? "bold" : "normal"}
                      fontSize="sm"
                      py={2}
                      px={3}
                      borderRadius="md"
                      color="white"
                      _hover={{ bg: "whiteAlpha.100" }}
                      onClick={() => navigate(item.path)}
                    >
                      <Icon as={item.icon} mr={3} boxSize="4" />
                      {item.label}
                    </Menu.Item>
                  ))}
                  <Box mx={3} my={1} borderTopWidth="1px" borderColor="whiteAlpha.200" />
                  <Menu.Item value="nodes-settings" disabled fontSize="sm" py={2} px={3} borderRadius="md" color="whiteAlpha.400">
                    <Icon as={FiServer} mr={3} boxSize="4" />
                    {t("header.nodeSettings")}
                  </Menu.Item>
                  <Menu.Item value="nodes-usage" disabled fontSize="sm" py={2} px={3} borderRadius="md" color="whiteAlpha.400">
                    <Icon as={FiBarChart2} mr={3} boxSize="4" />
                    {t("header.nodesUsage")}
                  </Menu.Item>
                  <Box mx={3} my={1} borderTopWidth="1px" borderColor="whiteAlpha.200" />
                  <Menu.Item value="logout" onClick={logout} fontSize="sm" py={2} px={3} borderRadius="md" color="white" _hover={{ bg: "whiteAlpha.100" }}>
                    <Icon as={FiLogOut} mr={3} boxSize="4" />
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
            css={iconBtnStyle}
          >
            <Icon as={FiSettings} boxSize="4" />
          </Button>

          <Language />

          <Button
            onClick={toggleColorMode}
            variant="outline"
            size="sm"
            aria-label={t("header.switchTheme")}
            css={iconBtnStyle}
          >
            <Icon as={colorMode === "light" ? FiMoon : FiSun} boxSize="4" />
          </Button>
        </Flex>
      </Box>
    </Flex>
  );
}
