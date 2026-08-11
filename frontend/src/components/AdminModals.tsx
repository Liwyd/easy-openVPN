import { Text } from "@chakra-ui/react";
import ConfirmDialog from "./ConfirmDialog";
import { useAdminContext } from "../contexts/AdminContext";

export default function AdminModals() {
  const { deleteAdmin, closeDelete, deleteMutation } = useAdminContext();

  return (
    <ConfirmDialog
      open={!!deleteAdmin}
      onClose={closeDelete}
      title="Delete Admin"
      confirmLabel="Delete"
      confirmColorPalette="red"
      onConfirm={() => deleteAdmin && deleteMutation.mutate(deleteAdmin.id)}
      isLoading={deleteMutation.isPending}
      body={
        <Text>
          Are you sure you want to delete <strong>{deleteAdmin?.username}</strong>?
          This cannot be undone.
        </Text>
      }
    />
  );
}
