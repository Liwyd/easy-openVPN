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
import type { Admin } from "../types/Admin";

interface AdminContextValue {
  editAdmin: Admin | null;
  openEdit: (admin: Admin) => void;
  closeEdit: () => void;
  deleteAdmin: Admin | null;
  openDelete: (admin: Admin) => void;
  closeDelete: () => void;
  createOpen: boolean;
  openCreate: () => void;
  closeCreate: () => void;
  createMutation: { mutate: (a: { username: string; password: string; data_limit: number | null; is_sudo: boolean }) => void; isPending: boolean };
  updateMutation: { mutate: (a: { adminId: number; data_limit: number | null; disabled: boolean; password: string | null }) => void; isPending: boolean };
  deleteMutation: { mutate: (adminId: number) => void; isPending: boolean };
  toggleMutation: { mutate: (a: { adminId: number; disabled: boolean }) => void; isPending: boolean };
}

const AdminContext = createContext<AdminContextValue | null>(null);

export function useAdminContext(): AdminContextValue {
  const ctx = useContext(AdminContext);
  if (!ctx) throw new Error("useAdminContext must be used within AdminProvider");
  return ctx;
}

export function AdminProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [editAdmin, setEditAdmin] = useState<Admin | null>(null);
  const [deleteAdmin, setDeleteAdmin] = useState<Admin | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["admins"] });
  }, [queryClient]);

  const createMutation = useMutation({
    mutationFn: async (body: {
      username: string;
      password: string;
      data_limit: number | null;
      is_sudo: boolean;
    }) => api.post("/admins", body),
    onSuccess: () => {
      invalidate();
      setCreateOpen(false);
      toaster.create({ title: "Admin created", type: "success" });
    },
    onError: (err: any) => {
      toaster.create({
        title: err?.response?.data?.detail || "Failed to create admin",
        type: "error",
      });
    },
  });

  const updateMutation = useMutation({
    mutationFn: async (body: {
      adminId: number;
      data_limit: number | null;
      disabled: boolean;
      password: string | null;
    }) =>
      api.put(`/admins/${body.adminId}`, {
        data_limit: body.data_limit,
        disabled: body.disabled,
        password: body.password,
      }),
    onSuccess: () => {
      invalidate();
      setEditAdmin(null);
      toaster.create({ title: "Admin updated", type: "success" });
    },
    onError: (err: any) => {
      toaster.create({
        title: err?.response?.data?.detail || "Failed to update admin",
        type: "error",
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (adminId: number) => api.delete(`/admins/${adminId}`),
    onSuccess: () => {
      invalidate();
      setDeleteAdmin(null);
      toaster.create({ title: "Admin deleted", type: "success" });
    },
    onError: (err: any) => {
      toaster.create({
        title: err?.response?.data?.detail || "Failed to delete admin",
        type: "error",
      });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: async ({ adminId, disabled }: { adminId: number; disabled: boolean }) =>
      api.put(`/admins/${adminId}`, { disabled }),
    onSuccess: () => {
      invalidate();
      toaster.create({
        title: "Admin status updated",
        type: "success",
      });
    },
    onError: (err: any) => {
      toaster.create({
        title: err?.response?.data?.detail || "Failed to update admin",
        type: "error",
      });
    },
  });

  return (
    <AdminContext.Provider
      value={{
        editAdmin,
        openEdit: setEditAdmin,
        closeEdit: () => setEditAdmin(null),
        deleteAdmin,
        openDelete: setDeleteAdmin,
        closeDelete: () => setDeleteAdmin(null),
        createOpen,
        openCreate: () => setCreateOpen(true),
        closeCreate: () => setCreateOpen(false),
        createMutation,
        updateMutation,
        deleteMutation,
        toggleMutation,
      }}
    >
      {children}
    </AdminContext.Provider>
  );
}
