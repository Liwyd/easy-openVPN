import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../lib/api";
import { toaster } from "../lib/toaster";
import { copyToClipboard } from "../utils/copyToClipboard";
import type { User } from "../types/User";

interface ConfirmState {
  user: User;
  open: boolean;
}

interface UserMutation {
  mutate: (variables: string) => void;
  isPending: boolean;
}

interface UserContextValue {
  editUser: User | null;
  openEdit: (user: User) => void;
  closeEdit: () => void;
  qrUser: User | null;
  openQR: (user: User) => void;
  closeQR: () => void;
  deleteState: ConfirmState;
  openDelete: (user: User) => void;
  closeDelete: () => void;
  resetState: ConfirmState;
  openReset: (user: User) => void;
  closeReset: () => void;
  regenerateState: ConfirmState;
  openRegenerate: (user: User) => void;
  closeRegenerate: () => void;
  createOpen: boolean;
  openCreate: () => void;
  closeCreate: () => void;
  copyLink: (user: User) => Promise<void>;
  downloadConfig: (user: User, protocol?: string) => Promise<void>;
  deleteMutation: UserMutation;
  enableMutation: UserMutation;
  disableMutation: UserMutation;
  resetMutation: UserMutation;
  revokeMutation: UserMutation;
}

const UserContext = createContext<UserContextValue | null>(null);

export function useUserContext(): UserContextValue {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error("useUserContext must be used within UserProvider");
  return ctx;
}

export function UserProvider({
  children,
  onCreateSuccess,
}: {
  children: ReactNode;
  onCreateSuccess?: () => void;
}) {
  const queryClient = useQueryClient();
  const [editUser, setEditUser] = useState<User | null>(null);
  const [qrUser, setQrUser] = useState<User | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteState, setDeleteState] = useState<ConfirmState>({
    user: null as never,
    open: false,
  });
  const [resetState, setResetState] = useState<ConfirmState>({
    user: null as never,
    open: false,
  });
  const [regenerateState, setRegenerateState] = useState<ConfirmState>({
    user: null as never,
    open: false,
  });

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["users"] });
  }, [queryClient]);

  const deleteMutation = useMutation({
    mutationFn: async (username: string) => api.delete(`/users/${username}`),
    onSuccess: () => {
      invalidate();
      setDeleteState({ user: null as never, open: false });
      toaster.create({ title: "User deleted", type: "success" });
    },
    onError: (err: any) => {
      toaster.create({
        title: typeof err?.response?.data?.detail === "string" ? err.response.data.detail : "Failed to delete user",
        type: "error",
      });
    },
  });

  const enableMutation = useMutation({
    mutationFn: async (username: string) => api.post(`/users/${username}/enable`),
    onSuccess: () => {
      invalidate();
      toaster.create({ title: "User enabled", type: "success" });
    },
    onError: (err: any) => {
      toaster.create({
        title: typeof err?.response?.data?.detail === "string" ? err.response.data.detail : "Failed to enable user",
        type: "error",
      });
    },
  });

  const disableMutation = useMutation({
    mutationFn: async (username: string) => api.post(`/users/${username}/disable`),
    onSuccess: () => {
      invalidate();
      setDeleteState({ user: null as never, open: false });
      toaster.create({ title: "User disabled", type: "success" });
    },
    onError: (err: any) => {
      toaster.create({
        title: typeof err?.response?.data?.detail === "string" ? err.response.data.detail : "Failed to disable user",
        type: "error",
      });
    },
  });

  const resetMutation = useMutation({
    mutationFn: async (username: string) => api.post(`/users/${username}/reset-usage`),
    onSuccess: () => {
      invalidate();
      setResetState({ user: null as never, open: false });
      toaster.create({ title: "Usage reset", type: "success" });
    },
    onError: (err: any) => {
      toaster.create({
        title: typeof err?.response?.data?.detail === "string" ? err.response.data.detail : "Failed to reset usage",
        type: "error",
      });
    },
  });

  const revokeMutation = useMutation({
    mutationFn: async (username: string) =>
      api.post(`/users/${username}/subscription/revoke`),
    onSuccess: () => {
      invalidate();
      setRegenerateState({ user: null as never, open: false });
      toaster.create({
        title: "Link regenerated",
        description: "The old subscription link is now invalid.",
        type: "success",
      });
    },
    onError: (err: any) => {
      toaster.create({
        title: typeof err?.response?.data?.detail === "string" ? err.response.data.detail : "Failed to regenerate link",
        type: "error",
      });
    },
  });

  const copyLink = useCallback(async (user: User) => {
    try {
      const { data } = await api.get(`/users/${user.username}/subscription-url`);
      await copyToClipboard(data.subscription_url as string);
      toaster.create({ title: "Subscription link copied", type: "success" });
    } catch {
      toaster.create({ title: "Failed to copy link", type: "error" });
    }
  }, []);

  const downloadConfig = useCallback(async (user: User, protocol?: string) => {
    try {
      const url = protocol
        ? `/users/${user.username}/config?protocol=${protocol}`
        : `/users/${user.username}/config`;
      const { data } = await api.get(url, {
        responseType: "blob",
      });
      const blob = new Blob([data], {
        type: "application/x-openvpn-profile",
      });
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = protocol
        ? `${user.username}_${protocol}.ovpn`
        : `${user.username}.ovpn`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(blobUrl);
    } catch (err: any) {
      toaster.create({
        title: typeof err?.response?.data?.detail === "string" ? err.response.data.detail : "Failed to download config",
        type: "error",
      });
    }
  }, []);

  return (
    <UserContext.Provider
      value={{
        editUser,
        openEdit: setEditUser,
        closeEdit: () => setEditUser(null),
        qrUser,
        openQR: setQrUser,
        closeQR: () => setQrUser(null),
        deleteState,
        openDelete: (user) => setDeleteState({ user, open: true }),
        closeDelete: () => setDeleteState({ user: null as never, open: false }),
        resetState,
        openReset: (user) => setResetState({ user, open: true }),
        closeReset: () => setResetState({ user: null as never, open: false }),
        regenerateState,
        openRegenerate: (user) => setRegenerateState({ user, open: true }),
        closeRegenerate: () =>
          setRegenerateState({ user: null as never, open: false }),
        createOpen,
        openCreate: () => setCreateOpen(true),
        closeCreate: () => {
          setCreateOpen(false);
          onCreateSuccess?.();
        },
        copyLink,
        downloadConfig,
        deleteMutation,
        enableMutation,
        disableMutation,
        resetMutation,
        revokeMutation,
      }}
    >
      {children}
    </UserContext.Provider>
  );
}
