import { Text } from "@chakra-ui/react";
import ConfirmDialog from "./ConfirmDialog";
import { useUserContext } from "../contexts/UserContext";
import { Trans, useTranslation } from "react-i18next";

export default function UserModals() {
  const { t } = useTranslation();
  const {
    deleteState,
    closeDelete,
    resetState,
    closeReset,
    regenerateState,
    closeRegenerate,
    deleteMutation,
    resetMutation,
    revokeMutation,
  } = useUserContext();

  return (
    <>
      <ConfirmDialog
        open={deleteState.open}
        onClose={closeDelete}
        title={t("confirm.deleteUser")}
        confirmLabel={t("confirm.delete")}
        confirmColorPalette="red"
        onConfirm={() => {
          if (!deleteState.user) return;
          deleteMutation.mutate(deleteState.user.username);
        }}
        isLoading={deleteMutation.isPending}
        body={
          <Text>
            <Trans
              i18nKey="confirm.deletePrompt"
              values={{ username: deleteState.user?.username ?? "" }}
            />
          </Text>
        }
      />

      <ConfirmDialog
        open={resetState.open}
        onClose={closeReset}
        title={t("confirm.resetUsage")}
        confirmLabel={t("confirm.reset")}
        onConfirm={() =>
          resetState.user && resetMutation.mutate(resetState.user.username)
        }
        isLoading={resetMutation.isPending}
        body={
          <Text>
            <Trans
              i18nKey="confirm.resetPrompt"
              values={{ username: resetState.user?.username ?? "" }}
            />
          </Text>
        }
      />

      <ConfirmDialog
        open={regenerateState.open}
        onClose={closeRegenerate}
        title={t("confirm.regenerateLink")}
        confirmLabel={t("confirm.regenerate")}
        confirmColorPalette="orange"
        onConfirm={() =>
          regenerateState.user &&
          revokeMutation.mutate(regenerateState.user.username)
        }
        isLoading={revokeMutation.isPending}
        body={
          <Text>
            <Trans
              i18nKey="confirm.regeneratePrompt"
              values={{ username: regenerateState.user?.username ?? "" }}
            />
          </Text>
        }
      />
    </>
  );
}
