import { useState } from "react";
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
  For,
  Switch,
} from "@chakra-ui/react";
import {
  FiPlus,
  FiEdit2,
  FiTrash2,
  FiShield,
  FiKey,
} from "react-icons/fi";
import api from "../lib/api";
import { toaster } from "../lib/toaster";
import {
  card,
  tableRoot,
  badgeActive,
  buttonSolid,
  buttonOutline,
} from "../theme-components";
import { createListCollection } from "@chakra-ui/react";

interface Admin {
  id: number;
  username: string;
  is_sudo: boolean;
  disabled: boolean;
  created_at: string;
  data_limit: number | null;
  data_used: number;
  parent_admin_id: number | null;
  user_count: number;
  limitless_user_count: number;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / 1024 ** i).toFixed(1)} ${units[i]}`;
}

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

interface CreateAdminForm {
  username: string;
  password: string;
  isSudo: boolean;
  dataLimit: string;
  dataUnit: string;
}

const emptyCreateForm: CreateAdminForm = {
  username: "",
  password: "",
  isSudo: false,
  dataLimit: "",
  dataUnit: "gb",
};

interface EditAdminForm {
  dataLimit: string;
  dataUnit: string;
  password: string;
}

function adminToEditForm(admin: Admin): EditAdminForm {
  let limitVal = "";
  let unit = "gb";
  if (admin.data_limit) {
    if (admin.data_limit % (1024 ** 3) === 0) {
      limitVal = String(admin.data_limit / 1024 ** 3);
      unit = "gb";
    } else {
      limitVal = String(admin.data_limit / 1024 ** 2);
      unit = "mb";
    }
  }
  return { dataLimit: limitVal, dataUnit: unit, password: "" };
}

export default function Admins() {
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const perPage = 20;

  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] =
    useState<CreateAdminForm>(emptyCreateForm);
  const [createErrors, setCreateErrors] = useState<Record<string, string>>({});

  const [editAdmin, setEditAdmin] = useState<Admin | null>(null);
  const [editForm, setEditForm] = useState<EditAdminForm | null>(null);

  const [deleteAdmin, setDeleteAdmin] = useState<Admin | null>(null);
  const [resetPassAdmin, setResetPassAdmin] = useState<Admin | null>(null);
  const [resetPassValue, setResetPassValue] = useState("");

  const offset = (page - 1) * perPage;

  const {
    data: admins,
    isLoading,
    error,
  } = useQuery<Admin[]>({
    queryKey: ["admins", search, offset, perPage],
    queryFn: async () => {
      const params: Record<string, string | number> = {
        limit: perPage,
        offset,
      };
      if (search.trim()) params.username = search.trim();
      const { data } = await api.get("/admins", { params });
      return data;
    },
  });

  const hasMore = admins?.length === perPage;

  const createMutation = useMutation({
    mutationFn: async (form: CreateAdminForm) => {
      const body: Record<string, unknown> = {
        username: form.username,
        password: form.password,
        is_sudo: form.isSudo,
      };
      if (!form.isSudo) {
        const num = parseFloat(form.dataLimit);
        if (!isNaN(num) && num > 0) {
          body.data_limit = Math.round(
            num * (form.dataUnit === "gb" ? 1024 ** 3 : 1024 ** 2),
          );
        }
      } else {
        body.data_limit = 0;
      }
      return api.post("/admins", body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admins"] });
      setCreateOpen(false);
      setCreateForm(emptyCreateForm);
      toaster.create({ title: "Admin created", type: "success" });
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail || "Failed to create admin";
      toaster.create({ title: msg, type: "error" });
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({
      adminId,
      form,
    }: {
      adminId: number;
      form: EditAdminForm;
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
      if (form.password.trim()) body.password = form.password.trim();
      return api.put(`/admins/${adminId}`, body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admins"] });
      setEditAdmin(null);
      setEditForm(null);
      toaster.create({ title: "Admin updated", type: "success" });
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail || "Failed to update admin";
      toaster.create({ title: msg, type: "error" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (adminId: number) =>
      api.delete(`/admins/${adminId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admins"] });
      setDeleteAdmin(null);
      toaster.create({ title: "Admin deleted", type: "success" });
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail || "Failed to delete admin";
      toaster.create({ title: msg, type: "error" });
    },
  });

  const toggleDisabledMutation = useMutation({
    mutationFn: async ({ adminId, disabled }: { adminId: number; disabled: boolean }) =>
      api.put(`/admins/${adminId}`, { disabled }),
    onMutate: async ({ adminId, disabled }) => {
      await queryClient.cancelQueries({ queryKey: ["admins"] });
      const previous = queryClient.getQueryData<Admin[]>(["admins", search, offset, perPage]);
      queryClient.setQueryData<Admin[]>(["admins", search, offset, perPage], (old) =>
        old?.map((a) => (a.id === adminId ? { ...a, disabled } : a)) ?? old,
      );
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["admins", search, offset, perPage], context.previous);
      }
      toaster.create({ title: "Failed to toggle admin", type: "error" });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["admins"] });
    },
  });

  const resetPassMutation = useMutation({
    mutationFn: async ({
      adminId,
      password,
    }: {
      adminId: number;
      password: string;
    }) => api.put(`/admins/${adminId}`, { password }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admins"] });
      setResetPassAdmin(null);
      setResetPassValue("");
      toaster.create({ title: "Password reset", type: "success" });
    },
    onError: (err: any) => {
      const msg =
        err?.response?.data?.detail || "Failed to reset password";
      toaster.create({ title: msg, type: "error" });
    },
  });

  function validateCreateForm(): boolean {
    const errors: Record<string, string> = {};
    if (!createForm.username.trim()) {
      errors.username = "Username is required";
    } else if (!/^[a-zA-Z0-9_-]+$/.test(createForm.username.trim())) {
      errors.username =
        "Only letters, numbers, hyphens and underscores allowed";
    }
    if (!createForm.password) {
      errors.password = "Password is required";
    } else if (createForm.password.length < 6) {
      errors.password = "Password must be at least 6 characters";
    }
    if (!createForm.isSudo) {
      if (
        !createForm.dataLimit ||
        isNaN(parseFloat(createForm.dataLimit)) ||
        parseFloat(createForm.dataLimit) <= 0
      ) {
        errors.dataLimit =
          "Data limit is required for non-sudo admins";
      }
    }
    setCreateErrors(errors);
    return Object.keys(errors).length === 0;
  }

  function handleCreateSubmit() {
    if (!validateCreateForm()) return;
    createMutation.mutate(createForm);
  }

  function openEditDialog(admin: Admin) {
    setEditAdmin(admin);
    setEditForm(adminToEditForm(admin));
  }

  return (
    <VStack align="stretch" gap={6}>
      <Heading size="lg">Admins</Heading>

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
            🔍
          </Box>
        </Box>

        <Box flex="1" />

        <Button css={buttonSolid} onClick={() => setCreateOpen(true)}>
          <FiPlus />
          Create Admin
        </Button>
      </Flex>

      {isLoading && (
        <Flex py={20} justify="center">
          <Spinner size="lg" color="accent" />
        </Flex>
      )}

      {error && (
        <Alert.Root status="error" borderRadius="lg">
          <Alert.Title>Failed to load admins</Alert.Title>
          <Alert.Description>
            {(error as Error).message || "An unexpected error occurred."}
          </Alert.Description>
        </Alert.Root>
      )}

      {!isLoading && !error && (admins?.length ?? 0) === 0 && (
        <Box css={card} p={12} textAlign="center">
          <FiShield
            size={40}
            style={{ margin: "0 auto 16px", opacity: 0.3 }}
          />
          <Text color="fg.muted">
            {search
              ? "No admins match your search."
              : "No sub-admins yet. Create your first admin to get started."}
          </Text>
        </Box>
      )}

      {!isLoading && !error && (admins?.length ?? 0) > 0 && (
        <Box css={tableRoot} overflowX="auto">
          <Table.Root size="sm" variant="outline">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Username</Table.ColumnHeader>
                <Table.ColumnHeader>Role</Table.ColumnHeader>
                <Table.ColumnHeader minW="160px">
                  Data Quota
                </Table.ColumnHeader>
                <Table.ColumnHeader textAlign="center">
                  Users
                </Table.ColumnHeader>
                <Table.ColumnHeader textAlign="center">
                  Limitless
                </Table.ColumnHeader>
                <Table.ColumnHeader hideBelow="lg">
                  Disabled
                </Table.ColumnHeader>
                <Table.ColumnHeader textAlign="right">
                  Actions
                </Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              <For each={admins!}>
                {(adm) => (
                  <Table.Row key={adm.id}>
                    <Table.Cell fontWeight="medium">
                      {adm.username}
                    </Table.Cell>
                    <Table.Cell>
                      <Badge css={adm.is_sudo ? badgeActive : {}}>
                        {adm.is_sudo ? "sudo" : "sub-admin"}
                      </Badge>
                    </Table.Cell>
                    <Table.Cell>
                      <DataUsageBar
                        used={adm.data_used}
                        limit={adm.data_limit}
                      />
                    </Table.Cell>
                    <Table.Cell textAlign="center">
                      <Badge colorPalette="blue" variant="subtle" fontSize="xs">
                        {adm.user_count}
                      </Badge>
                    </Table.Cell>
                    <Table.Cell textAlign="center">
                      <Badge
                        colorPalette={adm.limitless_user_count > 0 ? "orange" : "gray"}
                        variant="subtle"
                        fontSize="xs"
                      >
                        {adm.limitless_user_count}
                      </Badge>
                    </Table.Cell>
                    <Table.Cell hideBelow="lg">
                      <Switch.Root
                        size="sm"
                        checked={adm.disabled}
                        onCheckedChange={(details) =>
                          toggleDisabledMutation.mutate({
                            adminId: adm.id,
                            disabled: details.checked,
                          })
                        }
                      >
                        <Switch.Control>
                          <Switch.Thumb />
                        </Switch.Control>
                      </Switch.Root>
                    </Table.Cell>
                    <Table.Cell>
                      <HStack justify="flex-end" gap={1}>
                        <IconButton
                          aria-label="Edit quota / password"
                          variant="ghost"
                          size="sm"
                          onClick={() => openEditDialog(adm)}
                        >
                          <FiEdit2 />
                        </IconButton>
                        <IconButton
                          aria-label="Reset password"
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setResetPassAdmin(adm);
                            setResetPassValue("");
                          }}
                        >
                          <FiKey />
                        </IconButton>
                        <IconButton
                          aria-label="Delete admin"
                          variant="ghost"
                          size="sm"
                          colorPalette="red"
                          onClick={() => setDeleteAdmin(adm)}
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

      {!isLoading && !error && (admins?.length ?? 0) > 0 && (
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

      {/* Create Admin Dialog */}
      <Dialog.Root
        open={createOpen}
        onOpenChange={(e) => setCreateOpen(e.open)}
      >
        <Portal>
          <Dialog.Backdrop />
          <Dialog.Positioner>
            <Dialog.Content maxW="md">
              <Dialog.Header>
                <Dialog.Title>Create Admin</Dialog.Title>
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
                      placeholder="e.g. alice"
                    />
                    {createErrors.username && (
                      <Field.ErrorText>
                        {createErrors.username}
                      </Field.ErrorText>
                    )}
                  </Field.Root>

                  <Field.Root invalid={!!createErrors.password}>
                    <Field.Label>Password</Field.Label>
                    <Input
                      type="password"
                      value={createForm.password}
                      onChange={(e) =>
                        setCreateForm((f) => ({
                          ...f,
                          password: e.target.value,
                        }))
                      }
                      placeholder="At least 6 characters"
                    />
                    {createErrors.password && (
                      <Field.ErrorText>
                        {createErrors.password}
                      </Field.ErrorText>
                    )}
                  </Field.Root>

                  <Field.Root>
                    <Field.Label>Sudo Admin</Field.Label>
                    <Switch.Root
                      checked={createForm.isSudo}
                      onCheckedChange={(details) =>
                        setCreateForm((f) => ({
                          ...f,
                          isSudo: details.checked,
                        }))
                      }
                    >
                      <Switch.Control>
                        <Switch.Thumb />
                      </Switch.Control>
                    </Switch.Root>
                    <Text fontSize="xs" color="fg.muted">
                      Sudo admins can manage other admins and have no quota
                      limit.
                    </Text>
                  </Field.Root>

                  {!createForm.isSudo && (
                    <Field.Root invalid={!!createErrors.dataLimit}>
                      <Field.Label>Data Limit</Field.Label>
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
                          placeholder="e.g. 10"
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
                      {createErrors.dataLimit && (
                        <Field.ErrorText>
                          {createErrors.dataLimit}
                        </Field.ErrorText>
                      )}
                    </Field.Root>
                  )}
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

      {/* Edit Admin Dialog */}
      <Dialog.Root
        open={!!editAdmin}
        onOpenChange={(e) => {
          if (!e.open) {
            setEditAdmin(null);
            setEditForm(null);
          }
        }}
      >
        <Portal>
          <Dialog.Backdrop />
          <Dialog.Positioner>
            <Dialog.Content maxW="md">
              <Dialog.Header>
                <Dialog.Title>
                  Edit Admin: {editAdmin?.username}
                </Dialog.Title>
              </Dialog.Header>
              <Dialog.Body>
                {editForm && (
                  <VStack gap={4} align="stretch">
                    {!editAdmin?.is_sudo && (
                      <Field.Root>
                        <Field.Label>Data Limit</Field.Label>
                        <HStack gap={2}>
                          <Input
                            type="number"
                            value={editForm.dataLimit}
                            onChange={(e) =>
                              setEditForm((f) =>
                                f
                                  ? {
                                      ...f,
                                      dataLimit: e.target.value,
                                    }
                                  : f,
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
                                  ? {
                                      ...f,
                                      dataUnit: details.value[0],
                                    }
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
                    )}

                    <Field.Root>
                      <Field.Label>New Password (leave blank to keep)</Field.Label>
                      <Input
                        type="password"
                        value={editForm.password}
                        onChange={(e) =>
                          setEditForm((f) =>
                            f
                              ? { ...f, password: e.target.value }
                              : f,
                          )
                        }
                        placeholder="Enter new password"
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
                    if (editAdmin && editForm) {
                      updateMutation.mutate({
                        adminId: editAdmin.id,
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

      {/* Delete Confirmation Dialog */}
      <Dialog.Root
        open={!!deleteAdmin}
        onOpenChange={(e) => {
          if (!e.open) setDeleteAdmin(null);
        }}
      >
        <Portal>
          <Dialog.Backdrop />
          <Dialog.Positioner>
            <Dialog.Content maxW="sm">
              <Dialog.Header>
                <Dialog.Title>Delete Admin</Dialog.Title>
              </Dialog.Header>
              <Dialog.Body>
                <Text>
                  Are you sure you want to delete{" "}
                  <strong>{deleteAdmin?.username}</strong>? This action
                  cannot be undone.
                </Text>
                {deleteAdmin?.is_sudo && (
                  <Alert.Root status="error" mt={3} size="sm">
                    <Alert.Description>
                      Cannot delete a sudo admin.
                    </Alert.Description>
                  </Alert.Root>
                )}
              </Dialog.Body>
              <Dialog.Footer>
                <Dialog.CloseTrigger asChild>
                  <Button variant="outline" css={buttonOutline}>
                    Cancel
                  </Button>
                </Dialog.CloseTrigger>
                <Button
                  colorPalette="red"
                  disabled={deleteAdmin?.is_sudo}
                  onClick={() =>
                    deleteAdmin &&
                    deleteMutation.mutate(deleteAdmin.id)
                  }
                  loading={deleteMutation.isPending}
                >
                  Delete
                </Button>
              </Dialog.Footer>
            </Dialog.Content>
          </Dialog.Positioner>
        </Portal>
      </Dialog.Root>

      {/* Reset Password Dialog */}
      <Dialog.Root
        open={!!resetPassAdmin}
        onOpenChange={(e) => {
          if (!e.open) {
            setResetPassAdmin(null);
            setResetPassValue("");
          }
        }}
      >
        <Portal>
          <Dialog.Backdrop />
          <Dialog.Positioner>
            <Dialog.Content maxW="sm">
              <Dialog.Header>
                <Dialog.Title>
                  Reset Password: {resetPassAdmin?.username}
                </Dialog.Title>
              </Dialog.Header>
              <Dialog.Body>
                <Field.Root>
                  <Field.Label>New Password</Field.Label>
                  <Input
                    type="password"
                    value={resetPassValue}
                    onChange={(e) => setResetPassValue(e.target.value)}
                    placeholder="At least 6 characters"
                  />
                </Field.Root>
              </Dialog.Body>
              <Dialog.Footer>
                <Dialog.CloseTrigger asChild>
                  <Button variant="outline" css={buttonOutline}>
                    Cancel
                  </Button>
                </Dialog.CloseTrigger>
                <Button
                  css={buttonSolid}
                  disabled={resetPassValue.length < 6}
                  onClick={() =>
                    resetPassAdmin &&
                    resetPassMutation.mutate({
                      adminId: resetPassAdmin.id,
                      password: resetPassValue,
                    })
                  }
                  loading={resetPassMutation.isPending}
                >
                  Reset Password
                </Button>
              </Dialog.Footer>
            </Dialog.Content>
          </Dialog.Positioner>
        </Portal>
      </Dialog.Root>
    </VStack>
  );
}
