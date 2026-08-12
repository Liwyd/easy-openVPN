import { useState, useEffect, useMemo } from "react";
import {
  Dialog,
  Portal,
  Field,
  Input,
  Textarea,
  Button,
  HStack,
  VStack,
  Box,
  Text,
  Grid,
  GridItem,
  IconButton,
  Badge,
  Switch,
} from "@chakra-ui/react";
import {
  FiUserPlus,
  FiEdit3,
  FiRefreshCw,
  FiPower,
  FiRotateCcw,
  FiTrash2,
  FiServer,
} from "react-icons/fi";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../lib/api";
import { toaster } from "../lib/toaster";
import { buttonSolid, buttonOutline } from "../theme-components";
import { formatBytes } from "../utils/formatByte";
import { relativeTime } from "../utils/dateFormatter";
import type { User } from "../types/User";
import StatusBadge from "./StatusBadge";
import { useUserContext } from "../contexts/UserContext";
import { useTranslation } from "react-i18next";
import ReactDatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import "./datepicker.css";

const RANDOM_CHARS =
  "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";

interface FormState {
  username: string;
  dataLimit: string;
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
    expireAt: "",
    timeWindowStart: "",
    timeWindowEnd: "",
    note: "",
    status: "active",
  };
}

function userToForm(user: User): FormState {
  let limitVal = "";
  if (user.data_limit) {
    limitVal = String((user.data_limit / 1024 ** 3).toFixed(2));
  }
  return {
    username: user.username,
    dataLimit: limitVal,
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

function parseLimitBytes(value: string): number | null {
  if (!value) return null;
  const num = parseFloat(value);
  if (isNaN(num) || num <= 0) return null;
  return Math.round(num * 1024 ** 3);
}

function createRandomUsername(): string {
  let result = "";
  for (let i = 0; i < 6; i += 1) {
    result += RANDOM_CHARS.charAt(
      Math.floor(Math.random() * RANDOM_CHARS.length),
    );
  }
  return result;
}

function HeaderIcon({ children }: { children: React.ReactNode }) {
  return (
    <Box
      p="2"
      position="relative"
      color="white"
      display="flex"
      alignItems="center"
      justifyContent="center"
      _before={{
        content: `""`,
        position: "absolute",
        top: 0,
        left: 0,
        bg: "primary.400",
        display: "block",
        w: "full",
        h: "full",
        borderRadius: "5px",
        opacity: ".5",
        zIndex: "1",
      }}
      _after={{
        content: `""`,
        position: "absolute",
        top: "-5px",
        left: "-5px",
        bg: "primary.400",
        display: "block",
        w: "calc(100% + 10px)",
        h: "calc(100% + 10px)",
        borderRadius: "8px",
        opacity: ".4",
        zIndex: "1",
      }}
    >
      <Box position="relative" zIndex="2" w={5} h={5}>
        {children}
      </Box>
    </Box>
  );
}

export default function UserDialog() {
  const { t, i18n } = useTranslation();
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
    disableMutation,
  } = useUserContext();

  const isCreate = createOpen;
  const isOpen = createOpen || !!editUser;

  const [form, setForm] = useState<FormState>(emptyForm());
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [usernameLoading, setUsernameLoading] = useState(false);

  useEffect(() => {
    if (createOpen) {
      setForm(emptyForm());
      setErrors({});
    } else if (editUser) {
      setForm(userToForm(editUser));
      setErrors({});
    }
  }, [createOpen, editUser]);

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["users"] });

  const createMutation = useMutation({
    mutationFn: async (f: FormState) => {
      const body: Record<string, unknown> = { username: f.username };
      const limit = parseLimitBytes(f.dataLimit);
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
      toaster.create({ title: t("userDialog.created"), type: "success" });
    },
    onError: (err: any) => {
      toaster.create({
        title: err?.response?.data?.detail || t("userDialog.createFailed"),
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
      const limit = parseLimitBytes(f.dataLimit);
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
      toaster.create({ title: t("userDialog.updated"), type: "success" });
    },
    onError: (err: any) => {
      toaster.create({
        title: err?.response?.data?.detail || t("userDialog.updateFailed"),
        type: "error",
      });
    },
  });

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (isCreate) {
      if (!form.username.trim()) e.username = t("validate.required");
      else if (!/^[a-zA-Z0-9_-]+$/.test(form.username.trim()))
        e.username = t("validate.usernameChars");
    }
    if (
      form.dataLimit &&
      (isNaN(parseFloat(form.dataLimit)) || parseFloat(form.dataLimit) <= 0)
    ) {
      e.dataLimit = t("validate.positiveNumber");
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

  const nodesPlaceholder = useMemo(
    () => [
      { name: "Main", address: "Default", selected: true },
      { name: "Node 2", address: "Coming soon", selected: false },
    ],
    [],
  );

  return (
    <Dialog.Root
      open={isOpen}
      size="lg"
      onOpenChange={(e) => {
        if (!e.open) closeDialog();
      }}
    >
      <Portal>
        <Dialog.Backdrop
          bg="blackAlpha.300"
          _dark={{ bg: "blackAlpha.500" }}
          backdropFilter="blur(10px)"
        />
        <Dialog.Positioner>
          <Dialog.Content mx="3">
            <Dialog.Header pt={6} pb={4}>
              <HStack gap={2}>
                <HeaderIcon>
                  {isCreate ? (
                    <FiUserPlus size={20} />
                  ) : (
                    <FiEdit3 size={20} />
                  )}
                </HeaderIcon>
                <Text fontWeight="semibold" fontSize="lg">
                  {isCreate
                    ? t("userDialog.createTitle")
                    : t("userDialog.editTitle")}
                </Text>
              </HStack>
            </Dialog.Header>
            <Dialog.CloseTrigger mt={3} />

            <Dialog.Body>
              <Grid
                templateColumns={{ base: "repeat(1, 1fr)", md: "repeat(2, 1fr)" }}
                gap={3}
              >
                <GridItem>
                  <VStack justifyContent="space-between" h="full">
                    <VStack gap={0} w="full">
                      {isCreate && (
                        <Field.Root invalid={!!errors.username} mb="10px">
                          <Field.Label>
                            <HStack gap={1.5} align="center">
                              {t("userDialog.username")}
                              <IconButton
                                aria-label={t("userDialog.random")}
                                size="2xs"
                                variant="ghost"
                                onClick={() => {
                                  setUsernameLoading(true);
                                  const name = createRandomUsername();
                                  set({ username: name });
                                  setTimeout(
                                    () => setUsernameLoading(false),
                                    350,
                                  );
                                }}
                              >
                                <FiRefreshCw
                                  style={{
                                    width: 12,
                                    height: 12,
                                    animation: usernameLoading
                                      ? "spin 1s linear infinite"
                                      : undefined,
                                  }}
                                />
                              </IconButton>
                            </HStack>
                          </Field.Label>
                          <HStack w="full">
                            <Input
                              size="sm"
                              borderRadius="6px"
                              value={form.username}
                              onChange={(e) => set({ username: e.target.value })}
                              placeholder={t("userDialog.username")}
                            />
                          </HStack>
                          {errors.username && (
                            <Field.ErrorText>{errors.username}</Field.ErrorText>
                          )}
                        </Field.Root>
                      )}

                      {!isCreate && editUser && (
                        <Field.Root mb="10px">
                          <Field.Label>
                            <HStack gap={2} align="center">
                              <Text>{editUser.username}</Text>
                              <StatusBadge status={editUser.status} />
                              <Switch.Root
                                size="sm"
                                colorPalette="primary"
                                checked={form.status === "active"}
                                onCheckedChange={(e) =>
                                  set({
                                    status: e.checked ? "active" : "disabled",
                                  })
                                }
                                title={`status: ${form.status}`}
                              >
                                <Switch.HiddenInput />
                                <Switch.Control />
                                <Switch.Thumb />
                              </Switch.Root>
                            </HStack>
                          </Field.Label>
                          <Text fontSize="sm" color="fg.muted">
                            {formatBytes(editUser.data_used)}{" "}
                            {t("userDialog.usedOf")}{" "}
                            {editUser.data_limit
                              ? formatBytes(editUser.data_limit)
                              : t("userDialog.unlimited")}
                          </Text>
                        </Field.Root>
                      )}

                      <Field.Root invalid={!!errors.dataLimit} mb="10px">
                        <Field.Label>{t("userDialog.dataLimit")}</Field.Label>
                        <Input
                          size="sm"
                          borderRadius="6px"
                          type="number"
                          min="0"
                          value={form.dataLimit}
                          onChange={(e) => set({ dataLimit: e.target.value })}
                          placeholder={t("userDialog.unlimited")}
                        />
                        {errors.dataLimit && (
                          <Field.ErrorText>{errors.dataLimit}</Field.ErrorText>
                        )}
                      </Field.Root>

                      <Field.Root mb="10px">
                        <Field.Label>{t("userDialog.expiryDate")}</Field.Label>
                        <ReactDatePicker
                          selected={
                            form.expireAt ? new Date(`${form.expireAt}T00:00:00`) : null
                          }
                          onChange={(date: Date | null) => {
                            set({
                              expireAt: date
                                ? date.toISOString().slice(0, 10)
                                : "",
                            });
                          }}
                          locale={i18n.language === "fa" ? "fa" : "en"}
                          dateFormat={i18n.language === "fa" ? "yyyy/MM/dd" : "MMMM d, yyyy"}
                          isClearable
                          minDate={new Date()}
                          customInput={
                            <Input size="sm" borderRadius="6px" data-testid="expiry-date" />
                          }
                        />
                        {form.expireAt && (
                          <Field.HelperText>
                            {t("userDialog.expiresIn", {
                              time: relativeTime(form.expireAt),
                            })}
                          </Field.HelperText>
                        )}
                      </Field.Root>

                      <Field.Root mb="10px">
                        <Field.Label>
                          {t("userDialog.timeWindow")}{" "}
                          <Badge size="sm" colorPalette="gray">
                            {t("userDialog.optional")}
                          </Badge>
                        </Field.Label>
                        <HStack gap={2} w="full">
                          <Box flex="1">
                            <Input
                              size="sm"
                              borderRadius="6px"
                              type="time"
                              value={form.timeWindowStart}
                              onChange={(e) =>
                                set({ timeWindowStart: e.target.value })
                              }
                            />
                          </Box>
                          <Box flex="1">
                            <Input
                              size="sm"
                              borderRadius="6px"
                              type="time"
                              value={form.timeWindowEnd}
                              onChange={(e) =>
                                set({ timeWindowEnd: e.target.value })
                              }
                            />
                          </Box>
                        </HStack>
                      </Field.Root>

                      <Field.Root mb="10px">
                        <Field.Label>{t("userDialog.note")}</Field.Label>
                        <Textarea
                          rows={2}
                          size="sm"
                          borderRadius="6px"
                          value={form.note}
                          onChange={(e) => set({ note: e.target.value })}
                          placeholder="..."
                        />
                      </Field.Root>
                    </VStack>
                  </VStack>
                </GridItem>

                <GridItem>
                  <VStack w="full" align="stretch" gap={2}>
                    <Text fontWeight="semibold" fontSize="sm" mb={1}>
                      Nodes
                    </Text>
                    <Text fontSize="xs" color="fg.muted" mb={2}>
                      Select which nodes this user can access through their
                      subscription link.
                    </Text>
                    {nodesPlaceholder.map((node) => (
                      <Box
                        key={node.name}
                        p={2}
                        borderRadius="6px"
                        border="1px solid"
                        borderColor={node.selected ? "primary.500" : "border"}
                        bg={node.selected ? "bg.muted" : "transparent"}
                        boxShadow={node.selected ? "outline" : undefined}
                        display="flex"
                        alignItems="center"
                        justifyContent="space-between"
                        opacity={node.selected ? 1 : 0.55}
                        cursor="not-allowed"
                      >
                        <HStack gap={2}>
                          <FiServer size={16} color="var(--chakra-colors-primary-500)" />
                          <Text fontSize="sm" fontWeight="medium" textTransform="capitalize">
                            {node.name}
                          </Text>
                          <Text as="span" fontSize="xs" color="fg.muted">
                            ({node.address})
                          </Text>
                        </HStack>
                        <Box
                          width="18px"
                          height="18px"
                          borderRadius="4px"
                          border="1px solid"
                          borderColor="primary.500"
                          bg="primary.500"
                          display="inline-flex"
                          alignItems="center"
                          justifyContent="center"
                          color="white"
                          fontSize="xs"
                        >
                          {"\u2713"}
                        </Box>
                      </Box>
                    ))}
                    <Box
                      mt={1}
                      p={2}
                      borderRadius="6px"
                      border="1px dashed"
                      borderColor="border.strong"
                      textAlign="center"
                    >
                      <Text fontSize="xs" color="fg.muted">
                        Node management is coming in a future update.
                      </Text>
                    </Box>
                  </VStack>
                </GridItem>
              </Grid>
            </Dialog.Body>

            <Dialog.Footer mt="3" pt={4}>
              <HStack justifyContent="space-between" w="full" gap={3} flexWrap="wrap">
                <HStack justifyContent="flex-start" gap={1} flexWrap="wrap">
                  {!isCreate && editUser && (
                    <>
                      <IconButton
                        aria-label="Toggle status"
                        title="Toggle status"
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          if (editUser.status === "disabled") {
                            enableMutation.mutate(editUser.username);
                            closeEdit();
                          } else {
                            disableMutation.mutate(editUser.username);
                            closeEdit();
                          }
                        }}
                      >
                        <FiPower />
                      </IconButton>
                      <IconButton
                        aria-label="Reset usage"
                        title="Reset usage"
                        size="sm"
                        variant="outline"
                        onClick={() => openReset(editUser)}
                      >
                        <FiRotateCcw />
                      </IconButton>
                      <IconButton
                        aria-label="Regenerate subscription"
                        title="Regenerate subscription"
                        size="sm"
                        variant="outline"
                        onClick={() => openRegenerate(editUser)}
                      >
                        <FiRefreshCw />
                      </IconButton>
                      <IconButton
                        aria-label="Delete"
                        title="Delete"
                        size="sm"
                        variant="outline"
                        colorPalette="red"
                        onClick={() => openDelete(editUser)}
                      >
                        <FiTrash2 />
                      </IconButton>
                    </>
                  )}
                </HStack>
                <HStack w="full" maxW={{ md: "50%", base: "full" }} justify="end">
                  <Button
                    variant="outline"
                    css={buttonOutline}
                    size="sm"
                    onClick={closeDialog}
                  >
                    {t("userDialog.cancel")}
                  </Button>
                  <Button
                    css={buttonSolid}
                    size="sm"
                    px="8"
                    onClick={handleSubmit}
                    loading={createMutation.isPending || updateMutation.isPending}
                  >
                    {isCreate
                      ? t("userDialog.createTitle")
                      : t("userDialog.editTitle")}
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
