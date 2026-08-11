import { useMemo, useState } from "react";
import {
  Box,
  Table,
  For,
  Flex,
  Text,
  IconButton,
  Spinner,
  Select,
} from "@chakra-ui/react";
import {
  FiLink,
  FiDownload,
  FiGrid,
  FiArrowUp,
  FiArrowDown,
} from "react-icons/fi";
import { createListCollection } from "@chakra-ui/react";
import { tableRoot } from "../theme-components";
import { statusFilterItems } from "../constants/UserSettings";
import { relativeTime } from "../utils/dateFormatter";
import { getResetStrategyText } from "./UsageSlider";
import type { User } from "../types/User";
import StatusBadge from "./StatusBadge";
import UsageSlider from "./UsageSlider";
import { useUserContext } from "../contexts/UserContext";

type SortKey = "username" | "status" | "data_usage";
type SortDir = "asc" | "desc";

const statusCollection = createListCollection({
  items: statusFilterItems,
});

export default function UsersTable({
  users,
  isFetching,
}: {
  users: User[];
  isFetching?: boolean;
}) {
  const { openEdit, copyLink, downloadConfig, openQR } = useUserContext();
  const [statusFilter, setStatusFilter] = useState("all");
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

  const sortedUsers = useMemo(() => {
    const filtered =
      statusFilter === "all"
        ? users
        : users.filter((u) => u.status === statusFilter);
    const arr = [...filtered];
    arr.sort((a, b) => {
      let cmp = 0;
      if (sortKey === "username") {
        cmp = a.username.localeCompare(b.username);
      } else if (sortKey === "status") {
        cmp = a.status.localeCompare(b.status);
      } else {
        cmp = (a.data_used ?? 0) - (b.data_used ?? 0);
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return arr;
  }, [users, statusFilter, sortKey, sortDir]);

  const SortIndicator = ({ active }: { active: boolean }) =>
    active ? (
      sortDir === "asc" ? <FiArrowUp /> : <FiArrowDown />
    ) : null;

  const renderSortable = (key: SortKey, label: string, extra?: React.ReactNode) => (
    <Flex
      align="center"
      gap={2}
      cursor="pointer"
      onClick={() => toggleSort(key)}
      userSelect="none"
      title={`Sort by ${label.toLowerCase()}`}
    >
      <span>{label}</span>
      <SortIndicator active={sortKey === key} />
      {extra}
    </Flex>
  );

  return (
    <Box css={tableRoot} position="relative" overflowX="auto">
      <Table.Root size="sm" variant="outline">
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeader minW="220px">
              {renderSortable("username", "Username")}
            </Table.ColumnHeader>
            <Table.ColumnHeader minW="180px">
              {renderSortable("status", "Status", (
                <Select.Root
                  collection={statusCollection}
                  value={[statusFilter]}
                  onValueChange={(details) =>
                    setStatusFilter(details.value[0] ?? "all")
                  }
                  size="sm"
                  width="150px"
                  position="absolute"
                  right={2}
                  top="50%"
                  translateY="-50%"
                  onClick={(e: any) => e.stopPropagation()}
                >
                  <Select.Control>
                    <Select.Trigger>
                      <Select.ValueText />
                    </Select.Trigger>
                  </Select.Control>
                  <Select.Positioner>
                    <Select.Content>
                      <For each={statusCollection.items}>
                        {(item) => (
                          <Select.Item key={item.value} item={item}>
                            <Select.ItemText>{item.label}</Select.ItemText>
                          </Select.Item>
                        )}
                      </For>
                    </Select.Content>
                  </Select.Positioner>
                </Select.Root>
              ))}
            </Table.ColumnHeader>
            <Table.ColumnHeader minW="220px">
              {renderSortable("data_usage", "Data Usage")}
            </Table.ColumnHeader>
            <Table.ColumnHeader minW="180px">
              Data Reset
            </Table.ColumnHeader>
            <Table.ColumnHeader minW="140px">Actions</Table.ColumnHeader>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          <For each={sortedUsers}>
            {(user) => {
              const resetStrategy = getResetStrategyText(
                user.data_limit_reset_strategy,
              );
              return (
                <Table.Row
                  key={user.id}
                  data-testid={`user-row-${user.username}`}
                  onClick={() => openEdit(user)}
                  cursor="pointer"
                  _hover={{ bg: "bg.muted" }}
                  transition="background 0.1s ease"
                >
                  <Table.Cell>
                    <Flex direction="column" gap={0.5}>
                      <Text fontWeight="semibold">{user.username}</Text>
                      <Text fontSize="xs" color="fg.muted">
                        {user.expire_at
                          ? `expires ${relativeTime(user.expire_at)}`
                          : "No expiration"}
                        {user.time_window_start && user.time_window_end
                          ? `\u00b7 ${user.time_window_start.slice(0, 5)}\u2013${user.time_window_end.slice(0, 5)}`
                          : ""}
                      </Text>
                    </Flex>
                  </Table.Cell>
                  <Table.Cell>
                    <StatusBadge status={user.status} />
                  </Table.Cell>
                  <Table.Cell>
                    <UsageSlider user={user} />
                  </Table.Cell>
                  <Table.Cell>
                    <Text fontSize="xs" color="fg.muted">
                      {resetStrategy}
                    </Text>
                  </Table.Cell>
                  <Table.Cell>
                    <Flex gap={1} onClick={(e) => e.stopPropagation()}>
                      <IconButton
                        aria-label="Copy subscription link"
                        variant="ghost"
                        size="sm"
                        title="Copy subscription link"
                        onClick={() => copyLink(user)}
                      >
                        <FiLink />
                      </IconButton>
                      <IconButton
                        aria-label="Download config"
                        variant="ghost"
                        size="sm"
                        title="Download .ovpn config"
                        onClick={() => downloadConfig(user)}
                      >
                        <FiDownload />
                      </IconButton>
                      <IconButton
                        aria-label="Show QR code"
                        variant="ghost"
                        size="sm"
                        title="Show QR code"
                        onClick={() => openQR(user, "link")}
                      >
                        <FiGrid />
                      </IconButton>
                    </Flex>
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
