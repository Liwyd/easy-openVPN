import { Dialog, Portal, Text, Button } from "@chakra-ui/react";
import { buttonOutline } from "../theme-components";
import { useAdminContext } from "../contexts/AdminContext";

export default function AdminModals() {
  const { deleteAdmin, closeDelete, deleteMutation } = useAdminContext();

  return (
    <Dialog.Root
      open={!!deleteAdmin}
      onOpenChange={(e) => {
        if (!e.open) closeDelete();
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
                <strong>{deleteAdmin?.username}</strong>? This cannot be undone.
              </Text>
            </Dialog.Body>
            <Dialog.Footer>
              <Button variant="outline" css={buttonOutline} onClick={closeDelete}>
                Cancel
              </Button>
              <Button
                colorPalette="red"
                loading={deleteMutation.isPending}
                onClick={() => deleteAdmin && deleteMutation.mutate(deleteAdmin.id)}
              >
                Delete
              </Button>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  );
}
