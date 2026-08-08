import { Navigate } from "react-router-dom";
import { Box, Spinner, Flex } from "@chakra-ui/react";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute({
  children,
  requireSudo = false,
}: {
  children: React.ReactNode;
  requireSudo?: boolean;
}) {
  const { admin, loading } = useAuth();

  if (loading) {
    return (
      <Flex h="100vh" align="center" justify="center">
        <Spinner size="lg" color="accent" />
      </Flex>
    );
  }

  if (!admin) return <Navigate to="/login" replace />;

  if (requireSudo && !admin.is_sudo) return <Navigate to="/dashboard" replace />;

  return <Box>{children}</Box>;
}
