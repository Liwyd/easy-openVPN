import {
  Box,
  Heading,
  Text,
  VStack,
  Progress,
  Flex,
  SimpleGrid,
  Table,
  Badge,
} from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { FiUsers, FiShield, FiActivity } from "react-icons/fi";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import StatusBadge from "../components/StatusBadge";
import LoadingState from "../components/LoadingState";
import ErrorState from "../components/ErrorState";
import { card } from "../theme-components";

interface UsageData {
  admin_id: number;
  username: string;
  data_limit: number | null;
  data_used: number;
  remaining: number | null;
  child_admins_bytes: number;
  direct_users_bytes: number;
}

interface SummaryData {
  total_users: number;
  total_admins: number;
  total_traffic_bytes: number;
}

interface UsageOverTimePoint {
  date: string;
  bytes: number;
}

interface TopUser {
  username: string;
  data_used: number;
  data_limit: number | null;
  status: string;
}

interface StatusBreakdown {
  active: number;
  limited: number;
  expired: number;
  disabled: number;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / 1024 ** i).toFixed(1)} ${units[i]}`;
}

function StatCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
}) {
  return (
    <Box {...card} p={5}>
      <Flex align="center" gap={3}>
        <Box color="accent" p={2} borderRadius="md" bg="accent.subtle">
          {icon}
        </Box>
        <Box>
          <Text fontSize="xs" color="fg.muted" textTransform="uppercase" fontWeight="medium">
            {label}
          </Text>
          <Text fontSize="2xl" fontWeight="bold">
            {value}
          </Text>
        </Box>
      </Flex>
    </Box>
  );
}

function StatusDonut({ data }: { data: StatusBreakdown }) {
  const total = data.active + data.limited + data.expired + data.disabled;
  const segments = [
    { key: "active", label: "Active", color: "green", count: data.active },
    { key: "limited", label: "Limited", color: "orange", count: data.limited },
    { key: "expired", label: "Expired", color: "red", count: data.expired },
    { key: "disabled", label: "Disabled", color: "gray", count: data.disabled },
  ];

  return (
    <Box {...card} p={5}>
      <Heading size="sm" mb={4}>
        User Status
      </Heading>
      {total === 0 ? (
        <Text color="fg.muted" fontSize="sm">
          No users yet
        </Text>
      ) : (
        <VStack align="stretch" gap={2}>
          {segments.map((seg) => (
            <Flex key={seg.key} align="center" gap={3}>
              <Badge colorPalette={seg.color} fontSize="xs" minW="60px" justifyContent="center">
                {seg.label}
              </Badge>
              <Box flex="1" h={2} bg="bg.muted" borderRadius="full" overflow="hidden">
                <Box
                  h="full"
                  bg={`${seg.color}.500`}
                  borderRadius="full"
                  w={`${total > 0 ? (seg.count / total) * 100 : 0}%`}
                  transition="width 0.3s"
                />
              </Box>
              <Text fontSize="sm" color="fg.muted" minW="30px" textAlign="right">
                {seg.count}
              </Text>
            </Flex>
          ))}
        </VStack>
      )}
    </Box>
  );
}

export default function Dashboard() {
  const { admin } = useAuth();
  const isSudo = admin?.is_sudo;

  const { data: usage, isLoading: usageLoading, error: usageError } = useQuery<UsageData>({
    queryKey: ["admin-usage", admin?.id],
    queryFn: async () => {
      const { data } = await api.get(`/admins/${admin!.id}/usage`);
      return data;
    },
    enabled: !!admin?.id,
  });

  const { data: summary, isLoading: summaryLoading } = useQuery<SummaryData>({
    queryKey: ["stats-summary"],
    queryFn: async () => {
      const { data } = await api.get("/stats/summary");
      return data;
    },
  });

  const { data: usageOverTime } = useQuery<UsageOverTimePoint[]>({
    queryKey: ["stats-usage-over-time"],
    queryFn: async () => {
      const { data } = await api.get("/stats/usage-over-time", { params: { days: 30 } });
      return data;
    },
  });

  const { data: topUsers } = useQuery<TopUser[]>({
    queryKey: ["stats-top-users"],
    queryFn: async () => {
      const { data } = await api.get("/stats/top-users", { params: { limit: 5 } });
      return data;
    },
  });

  const { data: statusBreakdown } = useQuery<StatusBreakdown>({
    queryKey: ["stats-status-breakdown"],
    queryFn: async () => {
      const { data } = await api.get("/stats/status-breakdown");
      return data;
    },
  });

  if (usageLoading || summaryLoading) return <LoadingState />;
  if (usageError) return <ErrorState message="Failed to load dashboard data." />;

  const used = usage?.data_used ?? admin?.data_used ?? 0;
  const limit = usage?.data_limit ?? admin?.data_limit;
  const pct = limit ? Math.min((used / limit) * 100, 100) : 0;

  const chartData = (usageOverTime ?? []).map((p) => ({
    date: p.date.slice(5),
    GB: Number((p.bytes / 1024 ** 3).toFixed(2)),
  }));

  return (
    <VStack align="stretch" gap={6}>
      <Heading size="lg">Dashboard</Heading>

      <SimpleGrid columns={{ base: 1, md: 3 }} gap={4}>
        <StatCard
          label={isSudo ? "Total Users" : "My Users"}
          value={summary?.total_users ?? 0}
          icon={<FiUsers size={20} />}
        />
        {isSudo && (
          <StatCard
            label="Total Admins"
            value={summary?.total_admins ?? 0}
            icon={<FiShield size={20} />}
          />
        )}
        <StatCard
          label={isSudo ? "Total Traffic" : "My Traffic"}
          value={formatBytes(summary?.total_traffic_bytes ?? 0)}
          icon={<FiActivity size={20} />}
        />
      </SimpleGrid>

      {limit ? (
        <Box {...card} p={5}>
          <VStack align="stretch" gap={3}>
            <Heading size="sm">Quota Usage</Heading>
            <Flex justify="space-between" fontSize="sm" color="fg.muted">
              <Text>{formatBytes(used)} used</Text>
              <Text>{formatBytes(limit)} total</Text>
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
            <Flex justify="space-between" fontSize="xs" color="fg.subtle">
              <Text>{formatBytes(limit - used)} remaining</Text>
              <Text>{pct.toFixed(1)}%</Text>
            </Flex>
            {usage && (
              <Box pt={2} borderTop="1px solid" borderColor="border">
                <Text fontSize="xs" color="fg.subtle">
                  Direct users: {formatBytes(usage.direct_users_bytes)} | Child admins:{" "}
                  {formatBytes(usage.child_admins_bytes)}
                </Text>
              </Box>
            )}
          </VStack>
        </Box>
      ) : (
        <Box {...card} p={5}>
          <Heading size="sm" mb={2}>Quota Usage</Heading>
          <Text color="fg.muted" fontSize="sm">No quota limit set. Usage: {formatBytes(used)}</Text>
        </Box>
      )}

      <SimpleGrid columns={{ base: 1, lg: 2 }} gap={4}>
        <Box {...card} p={5}>
          <Heading size="sm" mb={4}>
            Traffic Over Time (30 days)
          </Heading>
          {chartData.length === 0 ? (
            <Text color="fg.muted" fontSize="sm" py={8} textAlign="center">
              No traffic data yet
            </Text>
          ) : (
            <Box h="200px">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="trafficGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#fa5252" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#fa5252" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11, fill: "#737373" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "#737373" }}
                    axisLine={false}
                    tickLine={false}
                    width={50}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#1a1a1a",
                      border: "1px solid #262626",
                      borderRadius: 8,
                      fontSize: 12,
                      color: "#ededed",
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="GB"
                    stroke="#fa5252"
                    strokeWidth={2}
                    fill="url(#trafficGrad)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </Box>
          )}
        </Box>

        {statusBreakdown && <StatusDonut data={statusBreakdown} />}
      </SimpleGrid>

      {topUsers && topUsers.length > 0 && (
        <Box {...card} p={5}>
          <Heading size="sm" mb={4}>
            Top Users by Usage
          </Heading>
          <Table.Root size="sm">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Username</Table.ColumnHeader>
                <Table.ColumnHeader>Used</Table.ColumnHeader>
                <Table.ColumnHeader>Limit</Table.ColumnHeader>
                <Table.ColumnHeader>Status</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {topUsers.map((u) => (
                <Table.Row key={u.username}>
                  <Table.Cell fontWeight="medium">{u.username}</Table.Cell>
                  <Table.Cell>{formatBytes(u.data_used)}</Table.Cell>
                  <Table.Cell>{u.data_limit ? formatBytes(u.data_limit) : "Unlimited"}</Table.Cell>
                  <Table.Cell>
                    <StatusBadge status={u.status} />
                  </Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>
        </Box>
      )}
    </VStack>
  );
}
