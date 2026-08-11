import { useState, useEffect } from "react";
import {
  Dialog,
  Portal,
  Field,
  Input,
  Select,
  For,
  HStack,
  VStack,
  Box,
  Text,
  Textarea,
  Button,
  Badge,
} from "@chakra-ui/react";
import {
  FiPower,
  FiRotateCcw,
  FiTrash2,
  FiRefreshCw,
} from "react-icons/fi";
import { createListCollection } from "@chakra-ui/react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../lib/api";
import { toaster } from "../lib/toaster";
import { buttonSolid, buttonOutline } from "../theme-components";
import { formatBytes } from "../utils/formatByte";
import type { User } from "../types/User";
import StatusBadge from "./StatusBadge";
import { useUserContext } from "../contexts/UserContext";

const unitCollection = createListCollection({
  items: [
    { label: "GB", value: "gb" },
    { label: "MB", value: "mb" },
  ],
});

const statusCollection = createListCollection({
  items: [
    { label: "Active", value: "active" },
    { label: "Disabled", value: "disabled" },
  ],
});

interface FormState {
  username: string;
  dataLimit: string;
  dataUnit: string;
  expireAt: string;
  timeWindowStart: string;
  timeWindowEnd: string;
  note: string;
  status: string;
}

function emptyForm(): FormState {
  return {
    username: "",
    dataLimit: "",
    dataUnit: "gb",
    expireAt: "",
    timeWindowStart: "",
    timeWindowEnd: "",
    note: "",
    status: "active",
  };
}

function userToForm(user: User): FormState {
  let limitVal = "";
  let unit = "gb";
  if (user.data_limit) {
    if (user.data_limit % 1024 ** 3 === 0) {
      limitVal = String(user.data_limit / 1024 ** 3);
      unit = "gb";
    } else {
      limitVal = String(user.data_limit / 1024 ** 2);
      unit = "mb";
    }
  }
  return {
    username: user.username,
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

function parseLimitBytes(value: string, unit: string): number | null {
  if (!value) return null;
  const num = parseFloat(value);
  if (isNaN(num) || num <= 0) return null;
  return Math.round(num * (unit === "gb" ? 1024 ** 3 : 1024 ** 2));
}

export default function UserDialog() {
  const queryClient = useQueryClient();
  const {
    editUser,
    closeEdit,
    createOpen,
    closeCreate,
    openDelete,
    openReset,
    openRegenerate,
    enableMutation,
  } = useUserContext();

  const isCreate = createOpen;
  const isOpen = createOpen || !!editUser;

  const [form, setForm] = useState<FormState>(emptyForm());
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (createOpen) {
      setForm(emptyForm());
      setErrors({});
    } else if (editUser) {
      setForm(userToForm(editUser));
      setErrors({});
    }
  }, [createOpen, editUser]);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["users"] });

  const createMutation = useMutation({
    mutationFn: async (f: FormState) => {
      const body: Record<string, unknown> = { username: f.username };
      const limit = parseLimitBytes(f.dataLimit, f.dataUnit);
      if (limit !== null) body.data_limit = limit;
      if (f.expireAt) body.expire_at = new Date(f.expireAt).toISOString();
      if (f.timeWindowStart) body.time_window_start = f.timeWindowStart;
      if (f.timeWindowEnd) body.time_window_end = f.timeWindowEnd;
      if (f.note.trim()) body.note = f.note.trim();
      return api.post("/users", body);
    },
    onSuccess: () => {
      invalidate();
      closeCreate();
      toaster.create({ title: "User created", type: "success" });
    },
    onError: (err: any) => {
      toaster.create({
        title: err?.response?.data?.detail || "Failed to create user",
        type: "error",
      });
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({
      username,
      f,
    }: {
      username: string;
      f: FormState;
    }) => {
      const body: Record<string, unknown> = {};
      const limit = parseLimitBytes(f.dataLimit, f.dataUnit);
      if (limit !== null) body.data_limit = limit;
      else body.data_limit = null;
      if (f.expireAt) body.expire_at = new Date(f.expireAt).toISOString();
      else body.expire_at = null;
      if (f.timeWindowStart) body.time_window_start = f.timeWindowStart;
      else body.time_window_start = null;
      if (f.timeWindowEnd) body.time_window_end = f.timeWindowEnd;
      else body.time_window_end = null;
      body.note = f.note.trim() || null;
      body.status = f.status;
      return api.put(`/users/${username}`, body);
    },
    onSuccess: () => {
      invalidate();
      closeEdit();
      toaster.create({ title: "User updated", type: "success" });
    },
    onError: (err: any) => {
      toaster.create({
        title: err?.response?.data?.detail || "Failed to update user",
        type: "error",
      });
    },
  });

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (isCreate) {
      if (!form.username.trim()) e.username = "Username is required";
      else if (!/^[a-zA-Z0-9_-]+$/.test(form.username.trim()))
        e.username = "Only letters, numbers, hyphens and underscores allowed";
    }
    if (
      form.dataLimit &&
      (isNaN(parseFloat(form.dataLimit)) || parseFloat(form.dataLimit) <= 0)
    ) {
      e.dataLimit = "Must be a positive number";
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  function handleSubmit() {
    if (!validate()) return;
    if (isCreate) createMutation.mutate(form);
    else if (editUser) updateMutation.mutate({ username: editUser.username, f: form });
  }

  function closeDialog() {
    if (isCreate) closeCreate();
    else closeEdit();
  }

  const set = (patch: Partial<FormState>) =>
    setForm((f) => ({ ...f, ...patch }));

  return (
    <Dialog.Root
      open={isOpen}
      onOpenChange={(e) => {
        if (!e.open) closeDialog();
      }}
    >
      <Portal>
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content maxW="md">
            <Dialog.Header>
              <Dialog.Title>
                {isCreate ? "Create User" : `Edit User`}
              </Dialog.Title>
            </Dialog.Header>
            <Dialog.Body>
              {!isCreate && editUser && (
                <HStack gap={3} mb={4} justify="space-between">
                  <HStack gap={2}>
                    <Text fontWeight="semibold">{editUser.username}</Text>
                    <StatusBadge status={editUser.status} />
                  </HStack>
                  <Text fontSize="sm" color="fg.muted">
                    {formatBytes(editUser.data_used)} used of{" "}
                    {editUser.data_limit ? formatBytes(editUser.data_limit) : "unlimited"}
                  </Text>
                </HStack>
              )}
              <VStack gap={4} align="stretch">
                {isCreate && (
                  <Field.Root invalid={!!errors.username}>
                    <Field.Label>Username</Field.Label>
                    <Input
                      value={form.username}
                      onChange={(e) => set({ username: e.target.value })}
                      placeholder="e.g. john"
                    />
                    {errors.username && (
                      <Field.ErrorText>{errors.username}</Field.ErrorText>
                    )}
                  </Field.Root>
                )}

                <Field.Root invalid={!!errors.dataLimit}>
                  <Field.Label>Data Limit (optional)</Field.Label>
                  <HStack gap={2}>
                    <Input
                      type="number"
                      value={form.dataLimit}
                      onChange={(e) => set({ dataLimit: e.target.value })}
                      placeholder="Unlimited"
                      flex="1"
                      min="0"
                    />
                    <Select.Root
                      collection={unitCollection}
                      value={[form.dataUnit]}
                      onValueChange={(details) =>
                        set({ dataUnit: details.value[0] ?? "gb" })
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
                                <Select.ItemText>{item.label}</Select.ItemText>
                              </Select.Item>
                            )}
                          </For>
                        </Select.Content>
                      </Select.Positioner>
                    </Select.Root>
                  </HStack>
                  {errors.dataLimit && (
                    <Field.ErrorText>{errors.dataLimit}</Field.ErrorText>
                  )}
                </Field.Root>

                <Field.Root>
                  <Field.Label>Expiry Date (optional)</Field.Label>
                  <Input
                    type="date"
                    value={form.expireAt}
                    onChange={(e) => set({ expireAt: e.target.value })}
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
                        value={form.timeWindowStart}
                        onChange={(e) => set({ timeWindowStart: e.target.value })}
                      />
                    </Box>
                    <Box flex="1">
                      <Text fontSize="xs" color="fg.muted" mb={1}>
                        End
                      </Text>
                      <Input
                        type="time"
                        value={form.timeWindowEnd}
                        onChange={(e) => set({ timeWindowEnd: e.target.value })}
                      />
                    </Box>
                  </HStack>
                </Field.Root>

                {!isCreate && (
                  <Field.Root>
                    <Field.Label>Status</Field.Label>
                    <Select.Root
                      collection={statusCollection}
                      value={[form.status]}
                      onValueChange={(details) =>
                        set({ status: details.value[0] ?? "active" })
                      }
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
                  </Field.Root>
                )}

                <Field.Root>
                  <Field.Label>Note (optional)</Field.Label>
                  <Textarea
                    value={form.note}
                    onChange={(e) => set({ note: e.target.value })}
                    placeholder="Internal note..."
                    rows={2}
                  />
                </Field.Root>
              </VStack>
            </Dialog.Body>
            <Dialog.Footer>
              <HStack gap={2} justify="space-between" w="100%">
                <HStack gap={1}>
                  {!isCreate && editUser && (
                    <>
                      <Button
                        size="sm"
                        variant="ghost"
                        colorPalette={
                          editUser.status === "disabled" ? "green" : "orange"
                        }
                        onClick={() => {
                          const u = editUser.username;
                          if (editUser.status === "disabled") {
                            enableMutation.mutate(u);
                            closeEdit();
                          } else {
                            openDelete(editUser);
                          }
                        }}
                        title={
                          editUser.status === "disabled"
                            ? "Enable user"
                            : "Disable user"
                        }
                      >
                        <FiPower />
                        {editUser.status === "disabled" ? "Enable" : "Disable"}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => openReset(editUser)}
                        title="Reset usage"
                      >
                        <FiRotateCcw />
                        Reset
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        colorPalette="orange"
                        onClick={() => openRegenerate(editUser)}
                        title="Regenerate subscription link"
                      >
                        <FiRefreshCw />
                      </Button>
                      {editUser.status === "disabled" && (
                        <Button
                          size="sm"
                          variant="ghost"
                          colorPalette="red"
                          onClick={() => openDelete(editUser)}
                          title="Delete user"
                        >
                          <FiTrash2 />
                        </Button>
                      )}
                    </>
                  )}
                </HStack>
                <HStack gap={2}>
                  <Button variant="outline" css={buttonOutline} onClick={closeDialog}>
                    Cancel
                  </Button>
                  <Button
                    css={buttonSolid}
                    onClick={handleSubmit}
                    loading={createMutation.isPending || updateMutation.isPending}
                  >
                    {isCreate ? "Create" : "Save"}
                  </Button>
                </HStack>
              </HStack>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  );
}
