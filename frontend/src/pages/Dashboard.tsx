import {
  Box,
  Heading,
  Text,
  VStack,
  Progress,
  Spinner,
  Flex,
} from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";

interface UsageData {
  admin_id: number;
  username: string;
  data_limit: number | null;
  data_used: number;
  remaining: number | null;
  child_admins_bytes: number;
  direct_users_bytes: number;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / 1024 ** i).toFixed(1)} ${units[i]}`;
}

export default function Dashboard() {
  const { admin } = useAuth();

  const { data: usage, isLoading: usageLoading } = useQuery<UsageData>({
    queryKey: ["admin-usage", admin?.id],
    queryFn: async () => {
      const { data } = await api.get(`/admins/${admin!.id}/usage`);
      return data;
    },
    enabled: !!admin?.id,
  });

  if (usageLoading) {
    return (
      <Flex align="center" justify="center" py={20}>
        <Spinner size="lg" color="accent" />
      </Flex>
    );
  }

  const used = usage?.data_used ?? admin?.data_used ?? 0;
  const limit = usage?.data_limit ?? admin?.data_limit;
  const pct = limit ? Math.min((used / limit) * 100, 100) : 0;

  return (
    <VStack align="stretch" gap={6}>
      <Heading size="lg">Dashboard</Heading>

      <Box
        border="1px solid"
        borderColor="border.strong"
        borderRadius="lg"
        p={6}
        bg="bg"
      >
        <VStack align="stretch" gap={4}>
          <Heading size="md">Quota Usage</Heading>

          {limit ? (
            <>
              <Flex justify="space-between" fontSize="sm" color="fg.muted">
                <Text>
                  {formatBytes(used)} used
                </Text>
                <Text>
                  {formatBytes(limit)} total
                </Text>
              </Flex>
              <Progress.Root
                value={pct}
                colorPalette={pct > 90 ? "red" : pct > 70 ? "orange" : "green"}
                size="lg"
              >
                <Progress.Track>
                  <Progress.Range />
                </Progress.Track>
              </Progress.Root>
              <Text fontSize="sm" color="fg.muted">
                {formatBytes(limit - used)} remaining
              </Text>
            </>
          ) : (
            <Text color="fg.muted">
              No quota limit set. Usage: {formatBytes(used)}
            </Text>
          )}

          {usage && (
            <Box pt={2} borderTop="1px solid" borderColor="border">
              <Text fontSize="xs" color="fg.subtle">
                Direct users: {formatBytes(usage.direct_users_bytes)} |
                Child admins: {formatBytes(usage.child_admins_bytes)}
              </Text>
            </Box>
          )}
        </VStack>
      </Box>
    </VStack>
  );
}
