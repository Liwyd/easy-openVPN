import {
  Box,
  Table,
  For,
  Flex,
  HStack,
  Text,
  IconButton,
  Spinner,
} from "@chakra-ui/react";
import {
  FiLink,
  FiCopy,
  FiGrid,
} from "react-icons/fi";
import { tableRoot } from "../theme-components";
import type { User } from "../types/User";
import StatusBadge from "./StatusBadge";
import UsageSlider from "./UsageSlider";
import { useUserContext } from "../contexts/UserContext";
import { useTranslation } from "react-i18next";

function OnlineDot({ user }: { user: User }) {
  if (user.is_online) {
    return (
      <Box
        w="8px"
        h="8px"
        borderRadius="full"
        flexShrink={0}
        bg="green.400"
      />
    );
  }
  if (user.last_connected_since) {
    return (
      <Box
        w="8px"
        h="8px"
        borderRadius="full"
        flexShrink={0}
        bg="gray.400"
      />
    );
  }
  return (
    <Box
      w="8px"
      h="8px"
      borderRadius="full"
      flexShrink={0}
      border="1.5px solid"
      borderColor="gray.400"
      bg="transparent"
    />
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
  const { openEdit, copyLink, openQR } =
    useUserContext();

  return (
    <Box css={tableRoot} position="relative" overflowX="auto">
      <Table.Root size="sm" variant="outline">
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeader minW="220px">
              {t("table.username")}
            </Table.ColumnHeader>
            <Table.ColumnHeader width="400px" minW="150px">
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
                <Text userSelect="none" pointerEvents="none">
                  Sort by expire
                </Text>
              </HStack>
            </Table.ColumnHeader>
            <Table.ColumnHeader width="350px" minW="230px">
              {t("table.dataUsage")}
            </Table.ColumnHeader>
            <Table.ColumnHeader width="200px" minW="180px" />
          </Table.Row>
        </Table.Header>
        <Table.Body>
          <For each={users}>
            {(user) => {
              return (
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
                      <Text fontWeight="semibold">{user.username}</Text>
                    </HStack>
                  </Table.Cell>
                  <Table.Cell width="400px" minW="150px">
                    <StatusBadge
                      status={user.status}
                      expiryDate={user.expire_at}
                    />
                  </Table.Cell>
                  <Table.Cell width="350px" minW="230px">
                    <UsageSlider user={user} />
                  </Table.Cell>
                  <Table.Cell width="200px" minW="180px">
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
                      <IconButton
                        aria-label={t("table.downloadConfig")}
                        variant="ghost"
                        size="sm"
                        title={t("table.downloadConfig")}
                        onClick={() => copyLink(user)}
                      >
                        <FiCopy />
                      </IconButton>
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
              );
            }}
          </For>
        </Table.Body>
      </Table.Root>
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
