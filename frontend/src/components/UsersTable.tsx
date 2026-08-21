import {
  Box,
  Table,
  For,
  Flex,
  HStack,
  Text,
  IconButton,
  Spinner,
  VStack,
  Menu,
  Portal,
} from "@chakra-ui/react";
import {
  FiLink,
  FiCopy,
  FiGrid,
  FiChevronDown,
  FiChevronUp,
  FiEdit2,
} from "react-icons/fi";
import { tableRoot } from "../theme-components";
import type { User } from "../types/User";
import StatusBadge from "./StatusBadge";
import UsageSlider from "./UsageSlider";
import { OnlineStatus } from "./OnlineStatus";
import { formatBytes } from "../utils/formatByte";
import { useUserContext } from "../contexts/UserContext";
import { useTranslation } from "react-i18next";
import { useState } from "react";

function OnlineDot({ user }: { user: User }) {
  if (user.is_online) {
    return (
      <Box
        className="circle pulse green"
        flexShrink={0}
      />
    );
  }
  if (user.last_connected_since) {
    return (
      <Box
        className="circle"
        flexShrink={0}
        bg="gray.400"
        _dark={{ bg: "gray.600" }}
      />
    );
  }
  return (
    <Box
      className="circle"
      flexShrink={0}
      border="1px solid"
      borderColor="gray.400"
      _dark={{ borderColor: "gray.600" }}
      bg="transparent"
    />
  );
}

function MobileRow({ user }: { user: User }) {
  const [expanded, setExpanded] = useState(false);
  const { openEdit, copyLink, openQR, downloadConfig } = useUserContext();
  const { t } = useTranslation();

  const used = Math.min(
    user.data_used,
    user.data_limit ?? Number.MAX_SAFE_INTEGER,
  );
  const isUnlimited = !user.data_limit;

  return (
    <Box
      borderBottomWidth="1px"
      borderColor="border"
      _last={{ borderBottomWidth: "0" }}
      className={expanded ? "user-row-expanded" : ""}
    >
      {/* Collapsed row — always visible */}
      <Flex
        align="center"
        justify="space-between"
        py={3}
        px={4}
        cursor="pointer"
        onClick={() => setExpanded(!expanded)}
        _hover={{ bg: "bg.muted" }}
        transition="background 0.1s ease"
        gap={2}
      >
        <HStack align="center" gap={2.5} flex="1" minW={0}>
          <OnlineDot user={user} />
          <Text fontWeight="semibold" truncate fontSize="sm">
            {user.username}
          </Text>
        </HStack>

        <HStack align="center" gap={2} flexShrink={0}>
          <StatusBadge
            status={user.status}
            expiryDate={user.expire_at}
            showDetail={false}
          />
          <Text
            fontSize="xs"
            fontWeight="medium"
            color="fg.muted"
            whiteSpace="nowrap"
          >
            {isUnlimited ? "∞" : `${formatBytes(used)} / ${formatBytes(user.data_limit!)}`}
          </Text>
          <Box color="fg.muted">
            {expanded ? <FiChevronUp size={16} /> : <FiChevronDown size={16} />}
          </Box>
        </HStack>
      </Flex>

      {/* Expanded detail — conditionally visible */}
      {expanded && (
        <Box px={4} pb={4}>
          <VStack align="stretch" gap={4}>
            {/* Full data usage */}
            <Box>
              <Text
                textTransform="capitalize"
                fontSize="xs"
                fontWeight="bold"
                color="fg.muted"
                mb={2}
              >
                {t("table.dataUsage")}
              </Text>
              <UsageSlider user={user} />
            </Box>

            {/* Status + Online */}
            <HStack justify="space-between">
              <StatusBadge
                status={user.status}
                expiryDate={user.expire_at}
              />
              <OnlineStatus lastConnectedSince={user.last_connected_since} />
            </HStack>

            {/* Action icons */}
            <HStack
              justify="flex-end"
              gap={1}
              onClick={(e) => e.stopPropagation()}
            >
              <IconButton
                aria-label={t("table.downloadConfig")}
                variant="ghost"
                size="sm"
                title={t("table.downloadConfig")}
                onClick={() => copyLink(user)}
              >
                <FiLink />
              </IconButton>
              <Menu.Root>
                <Menu.Trigger asChild>
                  <IconButton
                    aria-label={t("table.downloadConfig")}
                    variant="ghost"
                    size="sm"
                    title={t("table.downloadConfig")}
                  >
                    <FiCopy />
                  </IconButton>
                </Menu.Trigger>
                <Portal>
                  <Menu.Content>
                    <Menu.Item value="default" onClick={() => downloadConfig(user)}>
                      {t("table.downloadDefault", "Default Config")}
                    </Menu.Item>
                    <Menu.Item value="udp" onClick={() => downloadConfig(user, "udp")}>
                      {t("table.downloadUdp", "Download UDP")}
                    </Menu.Item>
                    <Menu.Item value="tcp" onClick={() => downloadConfig(user, "tcp")}>
                      {t("table.downloadTcp", "Download TCP")}
                    </Menu.Item>
                  </Menu.Content>
                </Portal>
              </Menu.Root>
              <IconButton
                aria-label={t("table.showQR")}
                variant="ghost"
                size="sm"
                title={t("table.showQR")}
                onClick={() => openQR(user)}
              >
                <FiGrid />
              </IconButton>
              <IconButton
                aria-label={t("userDialog.editUser")}
                variant="ghost"
                size="sm"
                title={t("userDialog.editUser")}
                onClick={() => openEdit(user)}
              >
                <FiEdit2 />
              </IconButton>
            </HStack>
          </VStack>
        </Box>
      )}
    </Box>
  );
}

export default function UsersTable({
  users,
  isFetching,
}: {
  users: User[];
  isFetching?: boolean;
}) {
  const { t } = useTranslation();
  const { openEdit, copyLink, openQR, downloadConfig } = useUserContext();

  return (
    <Box css={tableRoot} position="relative" overflowX="auto">
      {/* Desktop table — hidden on mobile */}
      <Box display={{ base: "none", md: "block" }}>
        <Table.Root size="sm" variant="outline">
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeader minW="140px">
                {t("table.username")}
              </Table.ColumnHeader>
              <Table.ColumnHeader width="350px" minW="140px">
                <HStack position="relative" gap="5px">
                  <Text
                    userSelect="none"
                    pointerEvents="none"
                    zIndex={1}
                    textTransform="uppercase"
                  >
                    {t("table.status")}
                  </Text>
                  <Text>/</Text>
                  <Text
                    userSelect="none"
                    pointerEvents="none"
                    display={{ base: "none", lg: "block" }}
                  >
                    Sort by expire
                  </Text>
                </HStack>
              </Table.ColumnHeader>
              <Table.ColumnHeader width="300px" minW="200px">
                {t("table.dataUsage")}
              </Table.ColumnHeader>
              <Table.ColumnHeader width="160px" minW="140px" />
            </Table.Row>
          </Table.Header>
          <Table.Body>
            <For each={users}>
              {(user) => (
                <Table.Row
                  key={user.id}
                  data-testid={`user-row-${user.username}`}
                  onClick={() => openEdit(user)}
                  cursor="pointer"
                  _hover={{ bg: "bg.muted" }}
                  transition="background 0.1s ease"
                >
                  <Table.Cell minW="140px">
                    <HStack align="center" gap={2.5}>
                      <OnlineDot user={user} />
                      <Text fontWeight="semibold" truncate>{user.username}</Text>
                    </HStack>
                  </Table.Cell>
                  <Table.Cell width="350px" minW="140px">
                    <StatusBadge
                      status={user.status}
                      expiryDate={user.expire_at}
                    />
                  </Table.Cell>
                  <Table.Cell width="300px" minW="200px">
                    <UsageSlider user={user} />
                  </Table.Cell>
                  <Table.Cell width="160px" minW="140px">
                    <HStack
                      justifyContent="flex-end"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <IconButton
                        aria-label={t("table.copyLink")}
                        variant="ghost"
                        size="sm"
                        title={t("table.copyLink")}
                        onClick={() => copyLink(user)}
                      >
                        <FiLink />
                      </IconButton>
                      <Menu.Root>
                        <Menu.Trigger asChild>
                          <IconButton
                            aria-label={t("table.downloadConfig")}
                            variant="ghost"
                            size="sm"
                            title={t("table.downloadConfig")}
                          >
                            <FiCopy />
                          </IconButton>
                        </Menu.Trigger>
                        <Portal>
                          <Menu.Content>
                            <Menu.Item value="default" onClick={() => downloadConfig(user)}>
                              {t("table.downloadDefault", "Default Config")}
                            </Menu.Item>
                            <Menu.Item value="udp" onClick={() => downloadConfig(user, "udp")}>
                              {t("table.downloadUdp", "Download UDP")}
                            </Menu.Item>
                            <Menu.Item value="tcp" onClick={() => downloadConfig(user, "tcp")}>
                              {t("table.downloadTcp", "Download TCP")}
                            </Menu.Item>
                          </Menu.Content>
                        </Portal>
                      </Menu.Root>
                      <IconButton
                        aria-label={t("table.showQR")}
                        variant="ghost"
                        size="sm"
                        title={t("table.showQR")}
                        onClick={() => openQR(user)}
                      >
                        <FiGrid />
                      </IconButton>
                    </HStack>
                  </Table.Cell>
                </Table.Row>
              )}
            </For>
          </Table.Body>
        </Table.Root>
      </Box>

      {/* Mobile rows — visible only on small screens */}
      <Box display={{ base: "block", md: "none" }}>
        <For each={users}>
          {(user) => (
            <MobileRow key={user.id} user={user} />
          )}
        </For>
      </Box>

      {isFetching && (
        <Flex
          position="absolute"
          inset={0}
          bg="bg/60"
          align="center"
          justify="center"
        >
          <Spinner color="accent" />
        </Flex>
      )}
    </Box>
  );
}
