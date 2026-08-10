import {
  HStack,
  VStack,
  Text,
  IconButton,
  Drawer,
  Portal,
  useBreakpointValue,
  Icon,
} from "@chakra-ui/react";
import { FiMenu, FiX, FiGrid, FiUsers, FiShield, FiSettings, FiDollarSign } from "react-icons/fi";
import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useState } from "react";

const NAV_ITEMS = [
  { label: "Dashboard", icon: FiGrid, path: "/dashboard" },
  { label: "Users", icon: FiUsers, path: "/users" },
  { label: "Admins", icon: FiShield, path: "/admins", sudoOnly: true },
  { label: "Billing", icon: FiDollarSign, path: "/billing", sudoOnly: true },
  { label: "Settings", icon: FiSettings, path: "/settings" },
] as const;

function NavItem({
  label,
  icon,
  path,
  onClick,
}: {
  label: string;
  icon: React.ComponentType;
  path: string;
  onClick?: () => void;
}) {
  const location = useLocation();
  const active = location.pathname === path;

  return (
    <NavLink to={path} onClick={onClick} style={{ textDecoration: "none" }}>
      <HStack
        gap={3}
        px={3}
        py={2.5}
        borderRadius="md"
        fontWeight={active ? "semibold" : "normal"}
        color={active ? "accent" : "fg.muted"}
        bg={active ? "accent.subtle" : "transparent"}
        _hover={{ bg: "bg.muted", color: "fg" }}
        transition="all 0.15s"
      >
        <Icon as={icon} boxSize={4} />
        <Text fontSize="sm">{label}</Text>
      </HStack>
    </NavLink>
  );
}

function SidebarContent({ onNavClick }: { onNavClick?: () => void }) {
  const { admin } = useAuth();
  const filtered = NAV_ITEMS.filter(
    (item) => !("sudoOnly" in item && item.sudoOnly) || admin?.is_sudo,
  );

  return (
    <VStack align="stretch" gap={1} p={4} h="full">
      <HStack gap={2.5} px={3} mb={4}>
        <img src="/favicon.svg" alt="" width={24} height={24} />
        <Text fontSize="lg" fontWeight="bold" color="accent" letterSpacing="tight">
          eovpanel
        </Text>
      </HStack>
      {filtered.map((item) => (
        <NavItem key={item.path} {...item} onClick={onNavClick} />
      ))}
    </VStack>
  );
}

export default function Sidebar() {
  const [open, setOpen] = useState(false);
  const isMobile = useBreakpointValue({ base: true, md: false });

  if (isMobile) {
    return (
      <>
        <IconButton
          aria-label="Open menu"
          variant="ghost"
          size="sm"
          position="fixed"
          top={3}
          left={3}
          zIndex="overlay"
          onClick={() => setOpen(true)}
        >
          <Icon as={FiMenu} />
        </IconButton>
        <Drawer.Root open={open} onOpenChange={(e) => setOpen(e.open)}>
          <Portal>
            <Drawer.Backdrop />
            <Drawer.Positioner>
              <Drawer.Content>
                <Drawer.CloseTrigger asChild>
                  <IconButton
                    aria-label="Close menu"
                    variant="ghost"
                    size="sm"
                    position="absolute"
                    top={3}
                    right={3}
                  >
                    <Icon as={FiX} />
                  </IconButton>
                </Drawer.CloseTrigger>
                <SidebarContent onNavClick={() => setOpen(false)} />
              </Drawer.Content>
            </Drawer.Positioner>
          </Portal>
        </Drawer.Root>
      </>
    );
  }

  return (
    <VStack
      w="240px"
      minW="240px"
      h="100vh"
      borderRight="1px solid"
      borderColor="border"
      bg="bg"
      display={{ base: "none", md: "flex" }}
      align="stretch"
      gap={0}
    >
      <SidebarContent />
    </VStack>
  );
}
