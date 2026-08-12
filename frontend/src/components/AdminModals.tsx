import { Text } from "@chakra-ui/react";
import { Trans, useTranslation } from "react-i18next";
import ConfirmDialog from "./ConfirmDialog";
import { useAdminContext } from "../contexts/AdminContext";

export default function AdminModals() {
  const { t } = useTranslation();
  const { deleteAdmin, closeDelete, deleteMutation } = useAdminContext();

  return (
    <ConfirmDialog
      open={!!deleteAdmin}
      onClose={closeDelete}
      title={t("adminModals.deleteTitle")}
      confirmLabel={t("adminModals.delete")}
      confirmColorPalette="red"
      onConfirm={() => deleteAdmin && deleteMutation.mutate(deleteAdmin.id)}
      isLoading={deleteMutation.isPending}
      body={
        <Text>
          <Trans
            i18nKey="adminModals.deletePrompt"
            values={{ username: deleteAdmin?.username ?? "" }}
          />
        </Text>
      }
    />
  );
}
