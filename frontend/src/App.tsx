import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster, Toast } from "@chakra-ui/react";
import { AuthProvider } from "./context/AuthContext";
import { toaster } from "./lib/toaster";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Users from "./pages/Users";
import Admins from "./pages/Admins";
import Billing from "./pages/Billing";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Toaster toaster={toaster}>
          {(toast) => (
            <Toast.Root>
              <Toast.Indicator />
              <Toast.Title>{toast.title}</Toast.Title>
              {toast.description && (
                <Toast.Description>{toast.description}</Toast.Description>
              )}
              <Toast.CloseTrigger />
            </Toast.Root>
          )}
        </Toaster>
        <Routes>
          <Route path="/login" element={<Login />} />

          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/users" element={<Users />} />
            <Route
              path="/admins"
              element={
                <ProtectedRoute requireSudo>
                  <Admins />
                </ProtectedRoute>
              }
            />
            <Route
              path="/billing"
              element={
                <ProtectedRoute requireSudo>
                  <Billing />
                </ProtectedRoute>
              }
            />
            <Route path="/settings" element={<Settings />} />
          </Route>

          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
