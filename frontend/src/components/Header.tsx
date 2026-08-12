import {
  Flex,
  Text,
  Button,
  Icon,
  Menu,
  Portal,
} from "@chakra-ui/react";
import { FiSun, FiMoon, FiLogOut, FiMenu, FiGrid, FiUsers, FiShield, FiDollarSign, FiSettings } from "react-icons/fi";
import { useLocation, useNavigate } from "react-router-dom";
import { useColorMode } from "./ui/color-mode";
import { useAuth } from "../context/AuthContext";
import { HOME_PATH } from "../lib/base";

const NAV_ITEMS = [
  { label: "Users", icon: FiUsers, path: HOME_PATH },
  { label: "Dashboard", icon: FiGrid, path: "/dashboard" },
  { label: "Admins", icon: FiShield, path: "/admins", sudoOnly: true },
  { label: "Billing", icon: FiDollarSign, path: "/billing", sudoOnly: true },
  { label: "Settings", icon: FiSettings, path: "/settings" },
] as const;

export default function Header() {
  const { colorMode, toggleColorMode } = useColorMode();
  const { admin, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const filtered = NAV_ITEMS.filter(
    (item) => !("sudoOnly" in item && item.sudoOnly) || admin?.is_sudo,
  );

  const title =
    filtered.find((i) => location.pathname === i.path)?.label ?? "Users";

  return (
    <Flex align="center" justify="space-between" gap={3} wrap="wrap" mb={4}>
      <Text as="h1" fontWeight="semibold" fontSize="2xl">
        {title}
      </Text>

      <Flex align="center" gap={2}>
        <Button
          onClick={toggleColorMode}
          variant="outline"
          size="sm"
          aria-label="Toggle color mode"
        >
          <Icon as={colorMode === "light" ? FiMoon : FiSun} />
        </Button>

        <Menu.Root>
          <Menu.Trigger asChild>
            <Button variant="outline" size="sm" aria-label="Menu">
              <Icon as={FiMenu} />
            </Button>
          </Menu.Trigger>
          <Portal>
            <Menu.Positioner>
              <Menu.Content minW="190px">
                {filtered.map((item) => (
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
                <Menu.Item value="logout" onClick={logout}>
                  <Icon as={FiLogOut} mr={2} />
                  Logout
                </Menu.Item>
              </Menu.Content>
            </Menu.Positioner>
          </Portal>
        </Menu.Root>
      </Flex>
    </Flex>
  );
}