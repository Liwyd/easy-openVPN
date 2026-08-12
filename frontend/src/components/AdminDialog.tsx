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
  Switch,
  Button,
  Text,
} from "@chakra-ui/react";
import { createListCollection } from "@chakra-ui/react";
import { useTranslation } from "react-i18next";
import { buttonSolid, buttonOutline } from "../theme-components";
import { formatBytes } from "../utils/formatByte";
import { useAdminContext } from "../contexts/AdminContext";

const unitCollection = createListCollection({
  items: [
    { label: "GB", value: "gb" },
    { label: "MB", value: "mb" },
  ],
});

interface FormState {
  username: string;
  password: string;
  dataLimit: string;
  dataUnit: string;
  isSudo: boolean;
  disabled: boolean;
}

const emptyForm: FormState = {
  username: "",
  password: "",
  dataLimit: "",
  dataUnit: "gb",
  isSudo: false,
  disabled: false,
};

function adminToForm(admin: {
  data_limit: number | null;
  disabled: boolean;
}): Pick<FormState, "dataLimit" | "dataUnit" | "disabled"> {
  let limitVal = "";
  let unit = "gb";
  if (admin.data_limit) {
    if (admin.data_limit % 1024 ** 3 === 0) {
      limitVal = String(admin.data_limit / 1024 ** 3);
      unit = "gb";
    } else {
      limitVal = String(admin.data_limit / 1024 ** 2);
      unit = "mb";
    }
  }
  return { dataLimit: limitVal, dataUnit: unit, disabled: admin.disabled };
}

function parseLimitBytes(value: string, unit: string): number | null {
  if (!value) return null;
  const num = parseFloat(value);
  if (isNaN(num) || num <= 0) return null;
  return Math.round(num * (unit === "gb" ? 1024 ** 3 : 1024 ** 2));
}

export default function AdminDialog() {
  const { t } = useTranslation();
  const {
    editAdmin,
    closeEdit,
    createOpen,
    closeCreate,
    createMutation,
    updateMutation,
  } = useAdminContext();

  const isCreate = createOpen;
  const isOpen = createOpen || !!editAdmin;

  const [form, setForm] = useState<FormState>(emptyForm);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (createOpen) {
      setForm(emptyForm);
      setErrors({});
    } else if (editAdmin) {
      setForm({ ...emptyForm, ...adminToForm(editAdmin) });
      setErrors({});
    }
  }, [createOpen, editAdmin]);

  const set = (patch: Partial<FormState>) =>
    setForm((f) => ({ ...f, ...patch }));

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (isCreate) {
      if (!form.username.trim()) e.username = t("adminDialog.usernameRequired");
      else if (!/^[a-zA-Z0-9_-]+$/.test(form.username.trim()))
        e.username = t("validate.usernameChars");
      if (form.password.length < 8)
        e.password = t("adminDialog.passwordMin");
    } else if (form.password && form.password.length < 8) {
      e.password = t("adminDialog.passwordMin");
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
    if (isCreate) {
      createMutation.mutate({
        username: form.username,
        password: form.password,
        data_limit: form.isSudo ? null : parseLimitBytes(form.dataLimit, form.dataUnit),
        is_sudo: form.isSudo,
      });
    } else if (editAdmin) {
      updateMutation.mutate({
        adminId: editAdmin.id,
        data_limit: parseLimitBytes(form.dataLimit, form.dataUnit),
        disabled: form.disabled,
        password: form.password || null,
      });
    }
  }

  function closeDialog() {
    if (isCreate) closeCreate();
    else closeEdit();
  }

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
                {isCreate ? t("adminDialog.createTitle") : t("adminDialog.editTitle", { username: editAdmin?.username })}
              </Dialog.Title>
            </Dialog.Header>
            <Dialog.Body>
              {!isCreate && editAdmin && (
                <Text fontSize="sm" color="fg.muted" mb={4}>
                  {formatBytes(editAdmin.data_used)} {t("adminDialog.usedOf")}{" "}
                  {editAdmin.data_limit ? formatBytes(editAdmin.data_limit) : t("adminDialog.unlimited")}
                </Text>
              )}
              <VStack gap={4} align="stretch">
                {isCreate && (
                  <Field.Root invalid={!!errors.username}>
                    <Field.Label>{t("adminDialog.username")}</Field.Label>
                    <Input
                      value={form.username}
                      onChange={(e) => set({ username: e.target.value })}
                      placeholder={t("adminDialog.usernamePlaceholder")}
                    />
                    {errors.username && (
                      <Field.ErrorText>{errors.username}</Field.ErrorText>
                    )}
                  </Field.Root>
                )}

                {isCreate && (
                  <Field.Root>
                    <Field.Label>{t("adminDialog.sudoAdmin")}</Field.Label>
                    <Switch.Root
                      checked={form.isSudo}
                      onCheckedChange={(e) => set({ isSudo: !!e.checked })}
                    >
                      <Switch.HiddenInput />
                      <Switch.Control />
                      <Switch.Label>
                        {form.isSudo
                          ? t("adminDialog.fullAccess")
                          : t("adminDialog.subAdminWithQuota")}
                      </Switch.Label>
                    </Switch.Root>
                  </Field.Root>
                )}

                <Field.Root invalid={!!errors.dataLimit}>
                  <Field.Label>
                    {t("adminDialog.dataLimit")} {form.isSudo ? t("adminDialog.unlimitedHint") : ""}
                  </Field.Label>
                  <HStack gap={2}>
                    <Input
                      type="number"
                      value={form.dataLimit}
                      onChange={(e) => set({ dataLimit: e.target.value })}
                      placeholder={form.isSudo ? t("adminDialog.unlimitedPlaceholder") : t("adminDialog.limitExample")}
                      flex="1"
                      min="0"
                      disabled={form.isSudo}
                    />
                    <Select.Root
                      collection={unitCollection}
                      value={[form.dataUnit]}
                      onValueChange={(details) =>
                        set({ dataUnit: details.value[0] ?? "gb" })
                      }
                      width="90px"
                      disabled={form.isSudo}
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
                  {!form.isSudo && (
                    <Field.HelperText>{t("adminDialog.optionalLimitHint")}</Field.HelperText>
                  )}
                </Field.Root>

                <Field.Root invalid={!!errors.password}>
                  <Field.Label>
                    {isCreate ? t("adminDialog.password") : t("adminDialog.newPasswordOptional")}
                  </Field.Label>
                  <Input
                    type="password"
                    value={form.password}
                    onChange={(e) => set({ password: e.target.value })}
                    placeholder={isCreate ? t("adminDialog.min8Chars") : t("adminDialog.leaveBlank")}
                    autoComplete="new-password"
                  />
                  {errors.password && (
                    <Field.ErrorText>{errors.password}</Field.ErrorText>
                  )}
                </Field.Root>

                {!isCreate && (
                  <Field.Root>
                    <Field.Label>{t("adminDialog.status")}</Field.Label>
                    <Switch.Root
                      checked={!form.disabled}
                      onCheckedChange={(e) => set({ disabled: !e.checked })}
                    >
                      <Switch.HiddenInput />
                      <Switch.Control />
                      <Switch.Label>
                        {form.disabled ? t("adminDialog.disabled") : t("adminDialog.active")}
                      </Switch.Label>
                    </Switch.Root>
                  </Field.Root>
                )}
              </VStack>
            </Dialog.Body>
            <Dialog.Footer>
              <Button variant="outline" css={buttonOutline} onClick={closeDialog}>
                {t("adminDialog.cancel")}
              </Button>
              <Button
                css={buttonSolid}
                onClick={handleSubmit}
                loading={createMutation.isPending || updateMutation.isPending}
              >
                {isCreate ? t("adminDialog.create") : t("adminDialog.save")}
              </Button>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  );
}
