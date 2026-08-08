import {
  Flex,
  Text,
  Button,
  Icon,
  Menu,
  Portal,
} from "@chakra-ui/react";
import { FiSun, FiMoon, FiLogOut } from "react-icons/fi";
import { useColorMode } from "./ui/color-mode";
import { useAuth } from "../context/AuthContext";

export default function Topbar() {
  const { colorMode, toggleColorMode } = useColorMode();
  const { admin, logout } = useAuth();

  return (
    <Flex
      h="56px"
      minH="56px"
      px={6}
      align="center"
      justify="flex-end"
      gap={3}
      borderBottom="1px solid"
      borderColor="border"
      bg="bg"
    >
      <Button
        onClick={toggleColorMode}
        variant="ghost"
        size="sm"
        aria-label="Toggle color mode"
      >
        <Icon as={colorMode === "light" ? FiMoon : FiSun} />
      </Button>

      <Menu.Root>
        <Menu.Trigger asChild>
          <Button variant="ghost" size="sm">
            <Text fontSize="sm" fontWeight="medium">
              {admin?.username}
            </Text>
          </Button>
        </Menu.Trigger>
        <Portal>
          <Menu.Positioner>
            <Menu.Content>
              <Menu.Item value="logout" onClick={logout}>
                <Icon as={FiLogOut} mr={2} />
                Logout
              </Menu.Item>
            </Menu.Content>
          </Menu.Positioner>
        </Portal>
      </Menu.Root>
    </Flex>
  );
}
