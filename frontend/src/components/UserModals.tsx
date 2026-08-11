import { Dialog, Portal, Text, Button } from "@chakra-ui/react";
import { buttonSolid, buttonOutline } from "../theme-components";
import { useUserContext } from "../contexts/UserContext";

export default function UserModals() {
  const {
    deleteState,
    closeDelete,
    resetState,
    closeReset,
    regenerateState,
    closeRegenerate,
    deleteMutation,
    disableMutation,
    resetMutation,
    revokeMutation,
  } = useUserContext();

  return (
    <>
      {/* Delete / Disable confirmation */}
      <Dialog.Root
        open={deleteState.open}
        onOpenChange={(e) => {
          if (!e.open) closeDelete();
        }}
      >
        <Portal>
          <Dialog.Backdrop />
          <Dialog.Positioner>
            <Dialog.Content maxW="sm">
              <Dialog.Header>
                <Dialog.Title>
                  {deleteState.user?.status === "disabled"
                    ? "Delete User"
                    : "Disable User"}
                </Dialog.Title>
              </Dialog.Header>
              <Dialog.Body>
                {deleteState.user?.status === "disabled" ? (
                  <Text>
                    Are you sure you want to delete{" "}
                    <strong>{deleteState.user.username}</strong>? This will
                    revoke their certificate permanently.
                  </Text>
                ) : (
                  <Text>
                    Disable <strong>{deleteState.user?.username}</strong>? They
                    will lose access immediately.
                  </Text>
                )}
              </Dialog.Body>
              <Dialog.Footer>
                <Button variant="outline" css={buttonOutline} onClick={closeDelete}>
                  Cancel
                </Button>
                <Button
                  colorPalette={
                    deleteState.user?.status === "disabled" ? "red" : "orange"
                  }
                  loading={deleteMutation.isPending || disableMutation.isPending}
                  onClick={() => {
                    if (!deleteState.user) return;
                    const u = deleteState.user.username;
                    if (deleteState.user.status === "disabled") {
                      deleteMutation.mutate(u);
                    } else {
                      disableMutation.mutate(u);
                    }
                  }}
                >
                  {deleteState.user?.status === "disabled" ? "Delete" : "Disable"}
                </Button>
              </Dialog.Footer>
            </Dialog.Content>
          </Dialog.Positioner>
        </Portal>
      </Dialog.Root>

      {/* Reset usage confirmation */}
      <Dialog.Root
        open={resetState.open}
        onOpenChange={(e) => {
          if (!e.open) closeReset();
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
                  <strong>{resetState.user?.username}</strong> to zero?
                </Text>
              </Dialog.Body>
              <Dialog.Footer>
                <Button variant="outline" css={buttonOutline} onClick={closeReset}>
                  Cancel
                </Button>
                <Button
                  css={buttonSolid}
                  loading={resetMutation.isPending}
                  onClick={() =>
                    resetState.user && resetMutation.mutate(resetState.user.username)
                  }
                >
                  Reset
                </Button>
              </Dialog.Footer>
            </Dialog.Content>
          </Dialog.Positioner>
        </Portal>
      </Dialog.Root>

      {/* Regenerate link confirmation */}
      <Dialog.Root
        open={regenerateState.open}
        onOpenChange={(e) => {
          if (!e.open) closeRegenerate();
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
                  <strong>{regenerateState.user?.username}</strong>. A new link
                  will be generated.
                </Text>
              </Dialog.Body>
              <Dialog.Footer>
                <Button variant="outline" css={buttonOutline} onClick={closeRegenerate}>
                  Cancel
                </Button>
                <Button
                  colorPalette="orange"
                  loading={revokeMutation.isPending}
                  onClick={() =>
                    regenerateState.user &&
                    revokeMutation.mutate(regenerateState.user.username)
                  }
                >
                  Regenerate
                </Button>
              </Dialog.Footer>
            </Dialog.Content>
          </Dialog.Positioner>
        </Portal>
      </Dialog.Root>
    </>
  );
}
