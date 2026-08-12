import { useMemo, useState } from "react";
import {
  Box,
  Table,
  For,
  Flex,
  HStack,
  Text,
  IconButton,
  Spinner,
  Switch,
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
import { relativeTime } from "../utils/dateFormatter";
import { getResetStrategyText } from "./UsageSlider";
import type { User, UserStatus } from "../types/User";
import StatusBadge from "./StatusBadge";
import UsageSlider from "./UsageSlider";
import { useUserContext } from "../contexts/UserContext";
import { useTranslation } from "react-i18next";

type SortKey = "username" | "status" | "data_usage";
type SortDir = "asc" | "desc";

const statusDotColor: Record<UserStatus, string> = {
  active: "green.400",
  limited: "red.400",
  expired: "orange.400",
  disabled: "gray.400",
};

export default function UsersTable({
  users,
  isFetching,
}: {
  users: User[];
  isFetching?: boolean;
}) {
  const { t } = useTranslation();
  const { openEdit, copyLink, downloadConfig, openQR, enableMutation, disableMutation } =
    useUserContext();
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("username");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const statusCollection = useMemo(
    () =>
      createListCollection({
        items: ["all", "active", "limited", "expired", "disabled"].map(
          (value) => ({ label: t(`status.${value}` as const), value }),
        ),
      }),
    [t],
  );

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
              {renderSortable("username", t("table.username"))}
            </Table.ColumnHeader>
            <Table.ColumnHeader minW="180px">
              <HStack gap={0} position="relative" align="center">
                <Text
                  position="absolute"
                  bg="bg.subtle"
                  userSelect="none"
                  pointerEvents="none"
                  zIndex={1}
                  w="100%"
                  textTransform="uppercase"
                >
                  {t("table.status")}
                  {statusFilter !== "all" ? `: ${t(`status.${statusFilter}` as const)}` : ""}
                </Text>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  aria-label={t("table.status")}
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: "100%",
                    height: "100%",
                    border: 0,
                    background: "transparent",
                    cursor: "pointer",
                    opacity: 0,
                    appearance: "none",
                    WebkitAppearance: "none",
                  }}
                >
                  {statusCollection.items.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </HStack>
            </Table.ColumnHeader>
            <Table.ColumnHeader minW="220px">
              {renderSortable("data_usage", t("table.dataUsage"))}
            </Table.ColumnHeader>
            <Table.ColumnHeader minW="180px">
              {t("table.dataReset")}
            </Table.ColumnHeader>
            <Table.ColumnHeader minW="140px">{t("table.actions")}</Table.ColumnHeader>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          <For each={sortedUsers}>
            {(user) => {
              const resetStrategy = getResetStrategyText(
                user.data_limit_reset_strategy,
                t,
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
                  <Table.Cell pl={2}>
                    <HStack align="center" gap={2.5}>
                      <Box
                        w="10px"
                        h="10px"
                        borderRadius="full"
                        flexShrink={0}
                        bg={statusDotColor[user.status]}
                        boxShadow="0 0 1px 1px rgba(0, 0, 0, 0.1)"
                      />
                      <Flex direction="column" gap={0.5} minW={0}>
                        <Text fontWeight="semibold">{user.username}</Text>
                        <Text fontSize="xs" color="fg.muted">
                          {user.expire_at
                            ? t("table.expires", {
                                time: relativeTime(user.expire_at),
                              })
                            : t("table.noExpiration")}
                          {user.time_window_start && user.time_window_end
                            ? `\u00b7 ${user.time_window_start.slice(0, 5)}\u2013${user.time_window_end.slice(0, 5)}`
                            : ""}
                        </Text>
                      </Flex>
                    </HStack>
                  </Table.Cell>
                  <Table.Cell>
                    <HStack gap={2} align="center">
                      <StatusBadge status={user.status} />
                      <Box
                        onClick={(e) => e.stopPropagation()}
                        display="inline-flex"
                        aria-label={`Toggle ${user.username} status`}
                      >
                        <Switch.Root
                          size="sm"
                          colorPalette={user.status === "active" ? "green" : "primary"}
                          checked={user.status === "active"}
                          disabled={user.status === "limited" || user.status === "expired"}
                          title={user.status === "disabled" ? t("users.enableUser") : t("users.disableUser")}
                          onCheckedChange={(e) => {
                            if (e.checked) enableMutation.mutate(user.username);
                            else disableMutation.mutate(user.username);
                          }}
                        >
                          <Switch.HiddenInput />
                          <Switch.Control />
                          <Switch.Thumb />
                        </Switch.Root>
                      </Box>
                    </HStack>
                  </Table.Cell>
                  <Table.Cell>
                    <UsageSlider user={user} />
                  </Table.Cell>
                  <Table.Cell>
                    <Text fontSize="xs" color="fg.muted">
                      {resetStrategy || "\u2014"}
                    </Text>
                  </Table.Cell>
                  <Table.Cell>
                    <Flex gap={1} onClick={(e) => e.stopPropagation()}>
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
                        onClick={() => downloadConfig(user)}
                      >
                        <FiDownload />
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
