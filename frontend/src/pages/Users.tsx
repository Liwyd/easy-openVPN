import { useState, useMemo } from "react";
import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import {
  Box,
  Heading,
  Text,
  VStack,
  HStack,
  Flex,
  Button,
  IconButton,
  Badge,
  Input,
  Progress,
  Spinner,
  Alert,
  Dialog,
  Portal,
  Field,
  Table,
  Select,
  Textarea,
  For,
} from "@chakra-ui/react";
import {
  FiPlus,
  FiEdit2,
  FiTrash2,
  FiDownload,
  FiCopy,
  FiRefreshCw,
  FiSearch,
  FiPower,
  FiUsers,
} from "react-icons/fi";
import api from "../lib/api";
import { toaster } from "../lib/toaster";
import {
  card,
  tableRoot,
  badgeActive,
  badgeLimited,
  badgeExpired,
  badgeDisabled,
  buttonSolid,
  buttonOutline,
} from "../theme-components";
import { createListCollection } from "@chakra-ui/react";

interface User {
  id: number;
  username: string;
  admin_id: number;
  status: string;
  created_at: string;
  data_limit: number | null;
  data_used: number;
  data_limit_reset_strategy: string;
  expire_at: string | null;
  time_window_start: string | null;
  time_window_end: string | null;
  note: string | null;
  revoked: boolean;
  common_name: string | null;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / 1024 ** i).toFixed(1)} ${units[i]}`;
}

function formatDate(iso: string | null): string {
  if (!iso) return "\u2014";
  return new Date(iso).toLocaleDateString();
}

function formatTime(time: string | null): string {
  if (!time) return "\u2014";
  return time.length >= 5 ? time.slice(0, 5) : time;
}

function statusBadgeCss(status: string) {
  switch (status) {
    case "active":
      return badgeActive;
    case "disabled":
      return badgeDisabled;
    case "expired":
      return badgeExpired;
    case "limited":
      return badgeLimited;
    default:
      return {};
  }
}

const statusCollection = createListCollection({
  items: [
    { label: "All Statuses", value: "all" },
    { label: "Active", value: "active" },
    { label: "Disabled", value: "disabled" },
    { label: "Expired", value: "expired" },
    { label: "Limited", value: "limited" },
  ],
});

const editStatusCollection = createListCollection({
  items: [
    { label: "Active", value: "active" },
    { label: "Disabled", value: "disabled" },
  ],
});

const unitCollection = createListCollection({
  items: [
    { label: "GB", value: "gb" },
    { label: "MB", value: "mb" },
  ],
});

function DataUsageBar({
  used,
  limit,
}: {
  used: number;
  limit: number | null;
}) {
  if (!limit) {
    return (
      <Text fontSize="sm" color="fg.muted">
        {formatBytes(used)} used
      </Text>
    );
  }
  const pct = Math.min((used / limit) * 100, 100);
  const color = pct > 90 ? "red" : pct > 70 ? "orange" : "green";
  return (
    <VStack align="stretch" gap={1}>
      <Progress.Root value={pct} size="xs" colorPalette={color}>
        <Progress.Track>
          <Progress.Range />
        </Progress.Track>
      </Progress.Root>
      <Text fontSize="xs" color="fg.muted">
        {formatBytes(used)} / {formatBytes(limit)}
      </Text>
    </VStack>
  );
}

interface CreateUserForm {
  username: string;
  dataLimit: string;
  dataUnit: string;
  expireAt: string;
  timeWindowStart: string;
  timeWindowEnd: string;
  note: string;
}

const emptyCreateForm: CreateUserForm = {
  username: "",
  dataLimit: "",
  dataUnit: "gb",
  expireAt: "",
  timeWindowStart: "",
  timeWindowEnd: "",
  note: "",
};

interface EditUserForm {
  dataLimit: string;
  dataUnit: string;
  expireAt: string;
  timeWindowStart: string;
  timeWindowEnd: string;
  note: string;
  status: string;
}

function userToEditForm(user: User): EditUserForm {
  let limitVal = "";
  let unit = "gb";
  if (user.data_limit) {
    if (user.data_limit % (1024 ** 3) === 0) {
      limitVal = String(user.data_limit / 1024 ** 3);
      unit = "gb";
    } else {
      limitVal = String(user.data_limit / 1024 ** 2);
      unit = "mb";
    }
  }
  return {
    dataLimit: limitVal,
    dataUnit: unit,
    expireAt: user.expire_at
      ? new Date(user.expire_at).toISOString().slice(0, 10)
      : "",
    timeWindowStart: user.time_window_start
      ? user.time_window_start.slice(0, 5)
      : "",
    timeWindowEnd: user.time_window_end
      ? user.time_window_end.slice(0, 5)
      : "",
    note: user.note ?? "",
    status: user.status,
  };
}

export default function Users() {
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const perPage = 20;

  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateUserForm>(emptyCreateForm);
  const [createErrors, setCreateErrors] = useState<Record<string, string>>({});

  const [editUser, setEditUser] = useState<User | null>(null);
  const [editForm, setEditForm] = useState<EditUserForm | null>(null);

  const [deleteUser, setDeleteUser] = useState<User | null>(null);
  const [resetUsageUser, setResetUsageUser] = useState<User | null>(null);
  const [regenerateUser, setRegenerateUser] = useState<User | null>(null);

  const offset = (page - 1) * perPage;

  const {
    data: users,
    isLoading,
    error,
    isFetching,
  } = useQuery<User[]>({
    queryKey: ["users", search, offset, perPage],
    queryFn: async () => {
      const params: Record<string, string | number> = {
        limit: perPage,
        offset,
      };
      if (search.trim()) params.username = search.trim();
      const { data } = await api.get("/users", { params });
      return data;
    },
  });

  const filteredUsers = useMemo(() => {
    if (!users) return [];
    if (statusFilter === "all") return users;
    return users.filter((u) => u.status === statusFilter);
  }, [users, statusFilter]);

  const hasMore = users?.length === perPage;

  const createMutation = useMutation({
    mutationFn: async (form: CreateUserForm) => {
      const body: Record<string, unknown> = { username: form.username };
      if (form.dataLimit) {
        const num = parseFloat(form.dataLimit);
        if (!isNaN(num) && num > 0) {
          body.data_limit = Math.round(
            num * (form.dataUnit === "gb" ? 1024 ** 3 : 1024 ** 2),
          );
        }
      }
      if (form.expireAt) body.expire_at = new Date(form.expireAt).toISOString();
      if (form.timeWindowStart) body.time_window_start = form.timeWindowStart;
      if (form.timeWindowEnd) body.time_window_end = form.timeWindowEnd;
      if (form.note.trim()) body.note = form.note.trim();
      return api.post("/users", body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setCreateOpen(false);
      setCreateForm(emptyCreateForm);
      toaster.create({ title: "User created", type: "success" });
    },
    onError: (err: any) => {
      const msg =
        err?.response?.data?.detail || "Failed to create user";
      toaster.create({ title: msg, type: "error" });
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({
      username,
      form,
    }: {
      username: string;
      form: EditUserForm;
    }) => {
      const body: Record<string, unknown> = {};
      if (form.dataLimit) {
        const num = parseFloat(form.dataLimit);
        if (!isNaN(num) && num > 0) {
          body.data_limit = Math.round(
            num * (form.dataUnit === "gb" ? 1024 ** 3 : 1024 ** 2),
          );
        }
      }
      if (form.expireAt) body.expire_at = new Date(form.expireAt).toISOString();
      else body.expire_at = null;
      if (form.timeWindowStart) body.time_window_start = form.timeWindowStart;
      else body.time_window_start = null;
      if (form.timeWindowEnd) body.time_window_end = form.timeWindowEnd;
      else body.time_window_end = null;
      body.note = form.note.trim() || null;
      body.status = form.status;
      return api.put(`/users/${username}`, body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setEditUser(null);
      setEditForm(null);
      toaster.create({ title: "User updated", type: "success" });
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail || "Failed to update user";
      toaster.create({ title: msg, type: "error" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (username: string) =>
      api.delete(`/users/${username}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setDeleteUser(null);
      toaster.create({ title: "User deleted", type: "success" });
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail || "Failed to delete user";
      toaster.create({ title: msg, type: "error" });
    },
  });

  const disableMutation = useMutation({
    mutationFn: async (username: string) =>
      api.post(`/users/${username}/disable`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      toaster.create({ title: "User disabled", type: "success" });
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail || "Failed to disable user";
      toaster.create({ title: msg, type: "error" });
    },
  });

  const enableMutation = useMutation({
    mutationFn: async (username: string) =>
      api.post(`/users/${username}/enable`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      toaster.create({ title: "User enabled", type: "success" });
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail || "Failed to enable user";
      toaster.create({ title: msg, type: "error" });
    },
  });

  const resetUsageMutation = useMutation({
    mutationFn: async (username: string) =>
      api.post(`/users/${username}/reset-usage`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setResetUsageUser(null);
      toaster.create({ title: "Usage reset", type: "success" });
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail || "Failed to reset usage";
      toaster.create({ title: msg, type: "error" });
    },
  });

  const revokeMutation = useMutation({
    mutationFn: async (username: string) =>
      api.post(`/users/${username}/subscription/revoke`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setRegenerateUser(null);
      toaster.create({
        title: "Link regenerated",
        description: "The old subscription link is now invalid.",
        type: "success",
      });
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail || "Failed to regenerate link";
      toaster.create({ title: msg, type: "error" });
    },
  });

  async function handleCopyLink(username: string) {
    try {
      const { data } = await api.get(`/users/${username}/subscription-url`);
      const text = data.subscription_url;

      // navigator.clipboard requires HTTPS or localhost — fall back to
      // the older execCommand approach for plain-HTTP environments.
      if (window.isSecureContext && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }

      toaster.create({ title: "Subscription link copied", type: "success" });
    } catch {
      toaster.create({ title: "Failed to copy link", type: "error" });
    }
  }

  async function handleDownloadConfig(username: string) {
    try {
      const { data } = await api.get(`/users/${username}/config`, {
        responseType: "blob",
      });
      const blob = new Blob([data], { type: "application/x-openvpn-profile" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${username}.ovpn`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail || "Failed to download config";
      toaster.create({ title: msg, type: "error" });
    }
  }

  function validateCreateForm(): boolean {
    const errors: Record<string, string> = {};
    if (!createForm.username.trim()) {
      errors.username = "Username is required";
    } else if (!/^[a-zA-Z0-9_-]+$/.test(createForm.username.trim())) {
      errors.username =
        "Only letters, numbers, hyphens and underscores allowed";
    }
    if (
      createForm.dataLimit &&
      (isNaN(parseFloat(createForm.dataLimit)) ||
        parseFloat(createForm.dataLimit) <= 0)
    ) {
      errors.dataLimit = "Must be a positive number";
    }
    setCreateErrors(errors);
    return Object.keys(errors).length === 0;
  }

  function handleCreateSubmit() {
    if (!validateCreateForm()) return;
    createMutation.mutate(createForm);
  }

  function openEditDialog(user: User) {
    setEditUser(user);
    setEditForm(userToEditForm(user));
  }

  function handleDisableClick(user: User) {
    setDeleteUser(user);
  }

  return (
    <VStack align="stretch" gap={6}>
      <Heading size="lg">Users</Heading>

      <Flex gap={3} wrap="wrap" align="center">
        <Box position="relative" flex="1" maxW="300px" minW="180px">
          <Input
            placeholder="Search by username..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            pe="40px"
          />
          <Box position="absolute" right="12px" top="50%" transform="translateY(-50%)" pointerEvents="none">
            <FiSearch />
          </Box>
        </Box>

        <Select.Root
          collection={statusCollection}
          value={[statusFilter]}
          onValueChange={(details) => {
            setStatusFilter(details.value[0]);
            setPage(1);
          }}
          width="180px"
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

        <Box flex="1" />

        <IconButton
          aria-label="Refresh users list"
          variant="outline"
          css={buttonOutline}
          onClick={() => queryClient.refetchQueries({ queryKey: ["users"] })}
          disabled={isFetching}
          title="Refresh users list"
        >
          <FiRefreshCw />
        </IconButton>

        <Button css={buttonSolid} onClick={() => setCreateOpen(true)}>
          <FiPlus />
          Create User
        </Button>
      </Flex>

      {isLoading && (
        <Flex py={20} justify="center">
          <Spinner size="lg" color="accent" />
        </Flex>
      )}

      {error && (
        <Alert.Root status="error" borderRadius="lg">
          <Alert.Title>Failed to load users</Alert.Title>
          <Alert.Description>
            {(error as Error).message || "An unexpected error occurred."}
          </Alert.Description>
        </Alert.Root>
      )}

      {!isLoading && !error && filteredUsers.length === 0 && (
        <Box css={card} p={12} textAlign="center">
          <FiUsers
            size={40}
            style={{ margin: "0 auto 16px", opacity: 0.3 }}
          />
          <Text color="fg.muted">
            {search || statusFilter !== "all"
              ? "No users match your filters."
              : "No users yet. Create your first user to get started."}
          </Text>
        </Box>
      )}

      {!isLoading && !error && filteredUsers.length > 0 && (
        <Box css={tableRoot}>
          <Table.Root size="sm" variant="outline">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Username</Table.ColumnHeader>
                <Table.ColumnHeader>Status</Table.ColumnHeader>
                <Table.ColumnHeader minW="160px">
                  Data Usage
                </Table.ColumnHeader>
                <Table.ColumnHeader hideBelow="md">
                  Expiry
                </Table.ColumnHeader>
                <Table.ColumnHeader hideBelow="lg">
                  Time Window
                </Table.ColumnHeader>
                <Table.ColumnHeader textAlign="right">
                  Actions
                </Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              <For each={filteredUsers}>
                {(user) => (
                  <Table.Row key={user.id}>
                    <Table.Cell fontWeight="medium">
                      {user.username}
                    </Table.Cell>
                    <Table.Cell>
                      <Badge css={statusBadgeCss(user.status)}>
                        {user.status}
                      </Badge>
                    </Table.Cell>
                    <Table.Cell>
                      <DataUsageBar
                        used={user.data_used}
                        limit={user.data_limit}
                      />
                    </Table.Cell>
                    <Table.Cell hideBelow="md" fontSize="sm">
                      {formatDate(user.expire_at)}
                    </Table.Cell>
                    <Table.Cell hideBelow="lg" fontSize="sm">
                      {user.time_window_start && user.time_window_end
                        ? `${formatTime(user.time_window_start)}\u2009\u2013\u2009${formatTime(user.time_window_end)}`
                        : "\u2014"}
                    </Table.Cell>
                    <Table.Cell>
                      <HStack justify="flex-end" gap={1}>
                        <IconButton
                          aria-label="Edit user"
                          variant="ghost"
                          size="sm"
                          onClick={() => openEditDialog(user)}
                        >
                          <FiEdit2 />
                        </IconButton>
                        <IconButton
                          aria-label={
                            user.status === "disabled"
                              ? "Enable user"
                              : "Disable user"
                          }
                          variant="ghost"
                          size="sm"
                          colorPalette={
                            user.status === "disabled" ? "green" : "gray"
                          }
                          onClick={() => {
                            if (user.status === "disabled") {
                              enableMutation.mutate(user.username);
                            } else {
                              handleDisableClick(user);
                            }
                          }}
                        >
                          {user.status === "disabled" ? (
                            <FiPower />
                          ) : (
                            <FiPower />
                          )}
                        </IconButton>
                        <IconButton
                          aria-label="Download config"
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDownloadConfig(user.username)}
                        >
                          <FiDownload />
                        </IconButton>
                        <IconButton
                          aria-label="Copy subscription link"
                          variant="ghost"
                          size="sm"
                          onClick={() => handleCopyLink(user.username)}
                        >
                          <FiCopy />
                        </IconButton>
                        <IconButton
                          aria-label="Regenerate link"
                          variant="ghost"
                          size="sm"
                          onClick={() => setRegenerateUser(user)}
                        >
                          <FiRefreshCw />
                        </IconButton>
                        <IconButton
                          aria-label="Reset usage"
                          variant="ghost"
                          size="sm"
                          onClick={() => setResetUsageUser(user)}
                          title="Reset usage"
                        >
                          ↺
                        </IconButton>
                        <IconButton
                          aria-label="Delete user"
                          variant="ghost"
                          size="sm"
                          colorPalette="red"
                          onClick={() => setDeleteUser(user)}
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
        </Box>
      )}

      {!isLoading && !error && (users?.length ?? 0) > 0 && (
        <Flex justify="space-between" align="center">
          <Text fontSize="sm" color="fg.muted">
            Page {page}
            {hasMore ? " (more available)" : ""}
          </Text>
          <HStack gap={2}>
            <Button
              size="sm"
              variant="outline"
              css={buttonOutline}
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Previous
            </Button>
            <Button
              size="sm"
              variant="outline"
              css={buttonOutline}
              disabled={!hasMore}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </HStack>
        </Flex>
      )}

      {/* Create User Dialog */}
      <Dialog.Root open={createOpen} onOpenChange={(e) => setCreateOpen(e.open)}>
        <Portal>
          <Dialog.Backdrop />
          <Dialog.Positioner>
            <Dialog.Content maxW="md">
              <Dialog.Header>
                <Dialog.Title>Create User</Dialog.Title>
              </Dialog.Header>
              <Dialog.Body>
                <VStack gap={4} align="stretch">
                  <Field.Root invalid={!!createErrors.username}>
                    <Field.Label>Username</Field.Label>
                    <Input
                      value={createForm.username}
                      onChange={(e) =>
                        setCreateForm((f) => ({
                          ...f,
                          username: e.target.value,
                        }))
                      }
                      placeholder="e.g. john"
                    />
                    {createErrors.username && (
                      <Field.ErrorText>{createErrors.username}</Field.ErrorText>
                    )}
                  </Field.Root>

                  <Field.Root invalid={!!createErrors.dataLimit}>
                    <Field.Label>Data Limit (optional)</Field.Label>
                    <HStack gap={2}>
                      <Input
                        type="number"
                        value={createForm.dataLimit}
                        onChange={(e) =>
                          setCreateForm((f) => ({
                            ...f,
                            dataLimit: e.target.value,
                          }))
                        }
                        placeholder="Unlimited"
                        flex="1"
                        min="0"
                      />
                      <Select.Root
                        collection={unitCollection}
                        value={[createForm.dataUnit]}
                        onValueChange={(details) =>
                          setCreateForm((f) => ({
                            ...f,
                            dataUnit: details.value[0],
                          }))
                        }
                        width="90px"
                      >
                        <Select.Control>
                          <Select.Trigger>
                            <Select.ValueText />
                          </Select.Trigger>
                        </Select.Control>
                        <Select.Positioner>
                          <Select.Content>
                            <For each={unitCollection.items}>
                              {(item) => (
                                <Select.Item key={item.value} item={item}>
                                  <Select.ItemText>
                                    {item.label}
                                  </Select.ItemText>
                                </Select.Item>
                              )}
                            </For>
                          </Select.Content>
                        </Select.Positioner>
                      </Select.Root>
                    </HStack>
                    {createErrors.dataLimit && (
                      <Field.ErrorText>
                        {createErrors.dataLimit}
                      </Field.ErrorText>
                    )}
                  </Field.Root>

                  <Field.Root>
                    <Field.Label>Expiry Date (optional)</Field.Label>
                    <Input
                      type="date"
                      value={createForm.expireAt}
                      onChange={(e) =>
                        setCreateForm((f) => ({
                          ...f,
                          expireAt: e.target.value,
                        }))
                      }
                    />
                  </Field.Root>

                  <Field.Root>
                    <Field.Label>
                      Time Window{" "}
                      <Badge size="sm" colorPalette="gray">
                        Optional
                      </Badge>
                    </Field.Label>
                    <HStack gap={2}>
                      <Box flex="1">
                        <Text fontSize="xs" color="fg.muted" mb={1}>
                          Start
                        </Text>
                        <Input
                          type="time"
                          value={createForm.timeWindowStart}
                          onChange={(e) =>
                            setCreateForm((f) => ({
                              ...f,
                              timeWindowStart: e.target.value,
                            }))
                          }
                        />
                      </Box>
                      <Box flex="1">
                        <Text fontSize="xs" color="fg.muted" mb={1}>
                          End
                        </Text>
                        <Input
                          type="time"
                          value={createForm.timeWindowEnd}
                          onChange={(e) =>
                            setCreateForm((f) => ({
                              ...f,
                              timeWindowEnd: e.target.value,
                            }))
                          }
                        />
                      </Box>
                    </HStack>
                  </Field.Root>

                  <Field.Root>
                    <Field.Label>Note (optional)</Field.Label>
                    <Textarea
                      value={createForm.note}
                      onChange={(e) =>
                        setCreateForm((f) => ({
                          ...f,
                          note: e.target.value,
                        }))
                      }
                      placeholder="Internal note..."
                      rows={2}
                    />
                  </Field.Root>
                </VStack>
              </Dialog.Body>
              <Dialog.Footer>
                <Dialog.CloseTrigger asChild>
                  <Button variant="outline" css={buttonOutline}>
                    Cancel
                  </Button>
                </Dialog.CloseTrigger>
                <Button
                  css={buttonSolid}
                  onClick={handleCreateSubmit}
                  loading={createMutation.isPending}
                >
                  Create
                </Button>
              </Dialog.Footer>
            </Dialog.Content>
          </Dialog.Positioner>
        </Portal>
      </Dialog.Root>

      {/* Edit User Dialog */}
      <Dialog.Root
        open={!!editUser}
        onOpenChange={(e) => {
          if (!e.open) {
            setEditUser(null);
            setEditForm(null);
          }
        }}
      >
        <Portal>
          <Dialog.Backdrop />
          <Dialog.Positioner>
            <Dialog.Content maxW="md">
              <Dialog.Header>
                <Dialog.Title>Edit User: {editUser?.username}</Dialog.Title>
              </Dialog.Header>
              <Dialog.Body>
                {editForm && (
                  <VStack gap={4} align="stretch">
                    <Field.Root>
                      <Field.Label>Data Limit</Field.Label>
                      <HStack gap={2}>
                        <Input
                          type="number"
                          value={editForm.dataLimit}
                          onChange={(e) =>
                            setEditForm((f) =>
                              f ? { ...f, dataLimit: e.target.value } : f,
                            )
                          }
                          placeholder="Unlimited"
                          flex="1"
                          min="0"
                        />
                        <Select.Root
                          collection={unitCollection}
                          value={[editForm.dataUnit]}
                          onValueChange={(details) =>
                            setEditForm((f) =>
                              f
                                ? { ...f, dataUnit: details.value[0] }
                                : f,
                            )
                          }
                          width="90px"
                        >
                          <Select.Control>
                            <Select.Trigger>
                              <Select.ValueText />
                            </Select.Trigger>
                          </Select.Control>
                          <Select.Positioner>
                            <Select.Content>
                              <For each={unitCollection.items}>
                                {(item) => (
                                  <Select.Item
                                    key={item.value}
                                    item={item}
                                  >
                                    <Select.ItemText>
                                      {item.label}
                                    </Select.ItemText>
                                  </Select.Item>
                                )}
                              </For>
                            </Select.Content>
                          </Select.Positioner>
                        </Select.Root>
                      </HStack>
                    </Field.Root>

                    <Field.Root>
                      <Field.Label>Status</Field.Label>
                      <Select.Root
                        collection={editStatusCollection}
                        value={[editForm.status]}
                        onValueChange={(details) =>
                          setEditForm((f) =>
                            f ? { ...f, status: details.value[0] } : f,
                          )
                        }
                      >
                        <Select.Control>
                          <Select.Trigger>
                            <Select.ValueText />
                          </Select.Trigger>
                        </Select.Control>
                        <Select.Positioner>
                          <Select.Content>
                            <For each={editStatusCollection.items}>
                              {(item) => (
                                <Select.Item key={item.value} item={item}>
                                  <Select.ItemText>
                                    {item.label}
                                  </Select.ItemText>
                                </Select.Item>
                              )}
                            </For>
                          </Select.Content>
                        </Select.Positioner>
                      </Select.Root>
                    </Field.Root>

                    <Field.Root>
                      <Field.Label>Expiry Date</Field.Label>
                      <Input
                        type="date"
                        value={editForm.expireAt}
                        onChange={(e) =>
                          setEditForm((f) =>
                            f ? { ...f, expireAt: e.target.value } : f,
                          )
                        }
                      />
                    </Field.Root>

                    <Field.Root>
                      <Field.Label>Time Window</Field.Label>
                      <HStack gap={2}>
                        <Box flex="1">
                          <Text fontSize="xs" color="fg.muted" mb={1}>
                            Start
                          </Text>
                          <Input
                            type="time"
                            value={editForm.timeWindowStart}
                            onChange={(e) =>
                              setEditForm((f) =>
                                f
                                  ? {
                                      ...f,
                                      timeWindowStart: e.target.value,
                                    }
                                  : f,
                              )
                            }
                          />
                        </Box>
                        <Box flex="1">
                          <Text fontSize="xs" color="fg.muted" mb={1}>
                            End
                          </Text>
                          <Input
                            type="time"
                            value={editForm.timeWindowEnd}
                            onChange={(e) =>
                              setEditForm((f) =>
                                f
                                  ? {
                                      ...f,
                                      timeWindowEnd: e.target.value,
                                    }
                                  : f,
                              )
                            }
                          />
                        </Box>
                      </HStack>
                    </Field.Root>

                    <Field.Root>
                      <Field.Label>Note</Field.Label>
                      <Textarea
                        value={editForm.note}
                        onChange={(e) =>
                          setEditForm((f) =>
                            f ? { ...f, note: e.target.value } : f,
                          )
                        }
                        rows={2}
                      />
                    </Field.Root>
                  </VStack>
                )}
              </Dialog.Body>
              <Dialog.Footer>
                <Dialog.CloseTrigger asChild>
                  <Button variant="outline" css={buttonOutline}>
                    Cancel
                  </Button>
                </Dialog.CloseTrigger>
                <Button
                  css={buttonSolid}
                  onClick={() => {
                    if (editUser && editForm) {
                      updateMutation.mutate({
                        username: editUser.username,
                        form: editForm,
                      });
                    }
                  }}
                  loading={updateMutation.isPending}
                >
                  Save Changes
                </Button>
              </Dialog.Footer>
            </Dialog.Content>
          </Dialog.Positioner>
        </Portal>
      </Dialog.Root>

      {/* Delete / Disable Confirmation Dialog */}
      <Dialog.Root
        open={!!deleteUser}
        onOpenChange={(e) => {
          if (!e.open) setDeleteUser(null);
        }}
      >
        <Portal>
          <Dialog.Backdrop />
          <Dialog.Positioner>
            <Dialog.Content maxW="sm">
              <Dialog.Header>
                <Dialog.Title>
                  {deleteUser?.status === "disabled"
                    ? "Delete User"
                    : "Disable User"}
                </Dialog.Title>
              </Dialog.Header>
              <Dialog.Body>
                {deleteUser?.status === "disabled" ? (
                  <Text>
                    Are you sure you want to delete{" "}
                    <strong>{deleteUser?.username}</strong>? This will revoke
                    their certificate permanently.
                  </Text>
                ) : (
                  <Text>
                    Disable <strong>{deleteUser?.username}</strong>? They will
                    lose access immediately.
                  </Text>
                )}
              </Dialog.Body>
              <Dialog.Footer>
                <Dialog.CloseTrigger asChild>
                  <Button variant="outline" css={buttonOutline}>
                    Cancel
                  </Button>
                </Dialog.CloseTrigger>
                <Button
                  colorPalette={
                    deleteUser?.status === "disabled" ? "red" : "orange"
                  }
                  onClick={() => {
                    if (!deleteUser) return;
                    if (deleteUser.status === "disabled") {
                      deleteMutation.mutate(deleteUser.username);
                    } else {
                      disableMutation.mutate(deleteUser.username);
                      setDeleteUser(null);
                    }
                  }}
                  loading={deleteMutation.isPending || disableMutation.isPending}
                >
                  {deleteUser?.status === "disabled" ? "Delete" : "Disable"}
                </Button>
              </Dialog.Footer>
            </Dialog.Content>
          </Dialog.Positioner>
        </Portal>
      </Dialog.Root>

      {/* Reset Usage Confirmation Dialog */}
      <Dialog.Root
        open={!!resetUsageUser}
        onOpenChange={(e) => {
          if (!e.open) setResetUsageUser(null);
        }}
      >
        <Portal>
          <Dialog.Backdrop />
          <Dialog.Positioner>
            <Dialog.Content maxW="sm">
              <Dialog.Header>
                <Dialog.Title>Reset Usage</Dialog.Title>
              </Dialog.Header>
              <Dialog.Body>
                <Text>
                  Reset data usage for{" "}
                  <strong>{resetUsageUser?.username}</strong> to zero?
                </Text>
              </Dialog.Body>
              <Dialog.Footer>
                <Dialog.CloseTrigger asChild>
                  <Button variant="outline" css={buttonOutline}>
                    Cancel
                  </Button>
                </Dialog.CloseTrigger>
                <Button
                  css={buttonSolid}
                  onClick={() =>
                    resetUsageUser &&
                    resetUsageMutation.mutate(resetUsageUser.username)
                  }
                  loading={resetUsageMutation.isPending}
                >
                  Reset
                </Button>
              </Dialog.Footer>
            </Dialog.Content>
          </Dialog.Positioner>
        </Portal>
      </Dialog.Root>

      {/* Regenerate Link Confirmation Dialog */}
      <Dialog.Root
        open={!!regenerateUser}
        onOpenChange={(e) => {
          if (!e.open) setRegenerateUser(null);
        }}
      >
        <Portal>
          <Dialog.Backdrop />
          <Dialog.Positioner>
            <Dialog.Content maxW="sm">
              <Dialog.Header>
                <Dialog.Title>Regenerate Subscription Link</Dialog.Title>
              </Dialog.Header>
              <Dialog.Body>
                <Text>
                  This will invalidate the current subscription link for{" "}
                  <strong>{regenerateUser?.username}</strong>. A new link
                  will be generated.
                </Text>
              </Dialog.Body>
              <Dialog.Footer>
                <Dialog.CloseTrigger asChild>
                  <Button variant="outline" css={buttonOutline}>
                    Cancel
                  </Button>
                </Dialog.CloseTrigger>
                <Button
                  colorPalette="orange"
                  onClick={() =>
                    regenerateUser &&
                    revokeMutation.mutate(regenerateUser.username)
                  }
                  loading={revokeMutation.isPending}
                >
                  Regenerate
                </Button>
              </Dialog.Footer>
            </Dialog.Content>
          </Dialog.Positioner>
        </Portal>
      </Dialog.Root>
    </VStack>
  );
}
