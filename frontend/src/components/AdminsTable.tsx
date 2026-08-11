import { useMemo, useState } from "react";
import {
  Box,
  Table,
  For,
  Flex,
  Text,
  IconButton,
  Spinner,
  Badge,
  HStack,
} from "@chakra-ui/react";
import {
  FiEdit2,
  FiTrash2,
  FiPower,
  FiArrowUp,
  FiArrowDown,
  FiShield,
  FiUser,
} from "react-icons/fi";
import { tableRoot } from "../theme-components";
import { formatBytes } from "../utils/formatByte";
import { formatDate } from "../utils/dateFormatter";
import type { Admin } from "../types/Admin";
import { useAdminContext } from "../contexts/AdminContext";

type SortKey = "username" | "data_usage" | "user_count";
type SortDir = "asc" | "desc";

function AdminUsageBar({ admin }: { admin: Admin }) {
  if (!admin.data_limit) {
    return (
      <Text fontSize="sm" color="fg.muted">
        {formatBytes(admin.data_used)} used
      </Text>
    );
  }
  const pct = Math.min((admin.data_used / admin.data_limit) * 100, 100);
  const color = pct > 90 ? "red" : pct > 70 ? "orange" : "green";
  return (
    <Box w="100%" maxW="220px">
      <Flex justify="space-between" mb={1}>
        <Text fontSize="xs" color="fg.muted">
          {formatBytes(admin.data_used)} used
        </Text>
        <Text fontSize="xs" color="fg.muted">
          {formatBytes(admin.data_limit)}
        </Text>
      </Flex>
      <Box h={1.5} bg="bg.muted" borderRadius="full" overflow="hidden">
        <Box
          h="full"
          bg={`${color}.500`}
          borderRadius="full"
          w={`${pct}%`}
          transition="width 0.3s"
        />
      </Box>
    </Box>
  );
}

export default function AdminsTable({
  admins,
  isFetching,
}: {
  admins: Admin[];
  isFetching?: boolean;
}) {
  const { openEdit, openDelete, toggleMutation } = useAdminContext();
  const [sortKey, setSortKey] = useState<SortKey>("username");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const sorted = useMemo(() => {
    const arr = [...admins];
    arr.sort((a, b) => {
      let cmp = 0;
      if (sortKey === "username") {
        cmp = a.username.localeCompare(b.username);
      } else if (sortKey === "user_count") {
        cmp = a.user_count - b.user_count;
      } else {
        cmp = (a.data_used ?? 0) - (b.data_used ?? 0);
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return arr;
  }, [admins, sortKey, sortDir]);

  const SortHeader = ({
    label,
    sortable,
    onClick,
  }: {
    label: React.ReactNode;
    sortable?: SortKey;
    onClick?: () => void;
  }) => (
    <Flex
      align="center"
      gap={2}
      cursor={onClick ? "pointer" : undefined}
      onClick={onClick}
      userSelect="none"
    >
      {label}
      {sortable && sortKey === sortable
        ? sortDir === "asc"
          ? <FiArrowUp />
          : <FiArrowDown />
        : null}
    </Flex>
  );

  return (
    <Box css={tableRoot} position="relative" overflowX="auto">
      <Table.Root size="sm" variant="outline">
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeader minW="200px">
              <SortHeader
                label="Username"
                sortable="username"
                onClick={() => toggleSort("username")}
              />
            </Table.ColumnHeader>
            <Table.ColumnHeader minW="220px">
              <SortHeader
                label="Data Usage"
                sortable="data_usage"
                onClick={() => toggleSort("data_usage")}
              />
            </Table.ColumnHeader>
            <Table.ColumnHeader minW="100px">
              <SortHeader
                label="Users"
                sortable="user_count"
                onClick={() => toggleSort("user_count")}
              />
            </Table.ColumnHeader>
            <Table.ColumnHeader minW="140px">Created</Table.ColumnHeader>
            <Table.ColumnHeader textAlign="right">Actions</Table.ColumnHeader>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          <For each={sorted}>
            {(admin) => (
              <Table.Row key={admin.id} data-testid={`admin-row-${admin.username}`}>
                <Table.Cell>
                  <HStack gap={2}>
                    <Badge
                      colorPalette={admin.is_sudo ? "purple" : "blue"}
                      borderRadius="full"
                      px={2}
                      py={0.5}
                      fontSize="xs"
                      title={admin.is_sudo ? "Sudo admin" : "Sub-admin"}
                    >
                      {admin.is_sudo ? <FiShield /> : <FiUser />}
                    </Badge>
                    <Flex direction="column" gap={0.5}>
                      <Text fontWeight="semibold">{admin.username}</Text>
                      {admin.disabled && (
                        <Badge colorPalette="gray" borderRadius="full" px={2} py={0} fontSize="xs">
                          Disabled
                        </Badge>
                      )}
                    </Flex>
                  </HStack>
                </Table.Cell>
                <Table.Cell>
                  <AdminUsageBar admin={admin} />
                </Table.Cell>
                <Table.Cell>
                  <Flex direction="column" gap={0.5}>
                    <Text fontSize="sm">
                      {admin.user_count} users
                    </Text>
                    {admin.limitless_user_count > 0 && (
                      <Text fontSize="xs" color="fg.muted">
                        {admin.limitless_user_count} unlimited
                      </Text>
                    )}
                  </Flex>
                </Table.Cell>
                <Table.Cell fontSize="sm" color="fg.muted">
                  {formatDate(admin.created_at)}
                </Table.Cell>
                <Table.Cell>
                  <HStack justify="flex-end" gap={1}>
                    <IconButton
                      aria-label={admin.disabled ? "Enable admin" : "Disable admin"}
                      variant="ghost"
                      size="sm"
                      colorPalette={admin.disabled ? "green" : "gray"}
                      title={admin.disabled ? "Enable admin" : "Disable admin"}
                      disabled={admin.is_sudo}
                      onClick={() =>
                        toggleMutation.mutate({
                          adminId: admin.id,
                          disabled: !admin.disabled,
                        })
                      }
                    >
                      <FiPower />
                    </IconButton>
                    <IconButton
                      aria-label="Edit admin"
                      variant="ghost"
                      size="sm"
                      title="Edit admin"
                      onClick={() => openEdit(admin)}
                    >
                      <FiEdit2 />
                    </IconButton>
                    <IconButton
                      aria-label="Delete admin"
                      variant="ghost"
                      size="sm"
                      colorPalette="red"
                      title="Delete admin"
                      disabled={admin.is_sudo}
                      onClick={() => openDelete(admin)}
                    >
                      <FiTrash2 />
                    </IconButton>
                  </HStack>
                </Table.Cell>
              </Table.Row>
            )}
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
