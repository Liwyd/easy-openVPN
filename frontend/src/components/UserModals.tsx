import { Text } from "@chakra-ui/react";
import ConfirmDialog from "./ConfirmDialog";
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

  const isDelete = deleteState.user?.status === "disabled";

  return (
    <>
      <ConfirmDialog
        open={deleteState.open}
        onClose={closeDelete}
        title={isDelete ? "Delete User" : "Disable User"}
        confirmLabel={isDelete ? "Delete" : "Disable"}
        confirmColorPalette={isDelete ? "red" : "orange"}
        onConfirm={() => {
          if (!deleteState.user) return;
          const u = deleteState.user.username;
          if (isDelete) deleteMutation.mutate(u);
          else disableMutation.mutate(u);
        }}
        isLoading={deleteMutation.isPending || disableMutation.isPending}
        body={
          isDelete ? (
            <Text>
              Are you sure you want to delete{" "}
              <strong>{deleteState.user?.username}</strong>? This will revoke
              their certificate permanently.
            </Text>
          ) : (
            <Text>
              Disable <strong>{deleteState.user?.username}</strong>? They will
              lose access immediately.
            </Text>
          )
        }
      />

      <ConfirmDialog
        open={resetState.open}
        onClose={closeReset}
        title="Reset Usage"
        confirmLabel="Reset"
        onConfirm={() =>
          resetState.user && resetMutation.mutate(resetState.user.username)
        }
        isLoading={resetMutation.isPending}
        body={
          <Text>
            Reset data usage for{" "}
            <strong>{resetState.user?.username}</strong> to zero?
          </Text>
        }
      />

      <ConfirmDialog
        open={regenerateState.open}
        onClose={closeRegenerate}
        title="Regenerate Subscription Link"
        confirmLabel="Regenerate"
        confirmColorPalette="orange"
        onConfirm={() =>
          regenerateState.user &&
          revokeMutation.mutate(regenerateState.user.username)
        }
        isLoading={revokeMutation.isPending}
        body={
          <Text>
            This will invalidate the current subscription link for{" "}
            <strong>{regenerateState.user?.username}</strong>. A new link will
            be generated.
          </Text>
        }
      />
    </>
  );
}
