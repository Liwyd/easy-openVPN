import {
  Box,
  Text,
  VStack,
  Progress,
  Flex,
  SimpleGrid,
  Table,
  HStack,
} from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { FiUsers, FiShield, FiActivity, FiCpu, FiDatabase, FiServer } from "react-icons/fi";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import StatusBadge from "../components/StatusBadge";
import LoadingState from "../components/LoadingState";
import ErrorState from "../components/ErrorState";
import EmptyState from "../components/EmptyState";
import StatCard from "../components/StatCard";
import SectionCard from "../components/SectionCard";
import { formatBytes } from "../utils/formatByte";

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

interface SystemMetrics {
  cpu_percent: number;
  ram: { total_bytes: number; used_bytes: number; available_bytes: number; percent: number };
  disk: { total_bytes: number; used_bytes: number; free_bytes: number; percent: number };
}

interface BillingMe {
  debt: number;
  price_per_user: number | null;
  price_per_gb: number | null;
  unlimited_user_count: number;
  volumed_user_count: number;
  total_user_months: number;
  volumed_total_bytes: number;
  estimated_monthly_user_cost: number;
  estimated_monthly_traffic_cost: number;
}

function StatusDonut({ data }: { data: StatusBreakdown }) {
  const total = data.active + data.limited + data.expired + data.disabled;
  const chartData = [
    { key: "active", label: "Active", color: "#38A169", count: data.active },
    { key: "limited", label: "Limited", color: "#ED8936", count: data.limited },
    { key: "expired", label: "Expired", color: "#E53E3E", count: data.expired },
    { key: "disabled", label: "Disabled", color: "#A0AEC0", count: data.disabled },
  ].filter((seg) => seg.count > 0);

  return (
    <SectionCard title="User Status">
      {total === 0 ? (
        <EmptyState icon={<FiActivity size={32} style={{ opacity: 0.3 }} />} message="No users yet" />
      ) : (
        <HStack gap={6} align="center" wrap="wrap">
          <Box width="160px" height="160px">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={chartData}
                  dataKey="count"
                  nameKey="label"
                  cx="50%"
                  cy="50%"
                  innerRadius={48}
                  outerRadius={72}
                  paddingAngle={2}
                  stroke="none"
                >
                  {chartData.map((seg) => (
                    <Cell key={seg.key} fill={seg.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: "#1a1a1a",
                    border: "1px solid #262626",
                    borderRadius: 8,
                    fontSize: 12,
                    color: "#ededed",
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </Box>
          <VStack align="stretch" gap={1.5} flex="1" minW="160px">
            {chartData.map((seg) => (
              <Flex key={seg.key} align="center" gap={2} fontSize="sm">
                <Box w={3} h={3} borderRadius="full" bg={seg.color} flexShrink={0} />
                <Text color="fg.muted" textTransform="capitalize" minW="70px">
                  {seg.label}
                </Text>
                <Box flex="1" />
                <Text fontWeight="medium">{seg.count}</Text>
                <Text color="fg.muted" w="42px" textAlign="right">
                  {total > 0 ? `${Math.round((seg.count / total) * 100)}%` : "0%"}
                </Text>
              </Flex>
            ))}
          </VStack>
        </HStack>
      )}
    </SectionCard>
  );
}

function GaugeBar({ label, percent, color }: { label: string; percent: number; color: string }) {
  return (
    <VStack align="stretch" gap={1}>
      <Flex justify="space-between" fontSize="sm">
        <Text color="fg.muted">{label}</Text>
        <Text fontWeight="medium">{percent.toFixed(1)}%</Text>
      </Flex>
      <Progress.Root value={percent} size="sm" colorPalette={percent > 90 ? "red" : percent > 70 ? "orange" : color as any}>
        <Progress.Track>
          <Progress.Range />
        </Progress.Track>
      </Progress.Root>
    </VStack>
  );
}

export default function Dashboard() {
  const { admin } = useAuth();
  const isSudo = admin?.is_sudo;

  const { data: usage, isLoading: usageLoading, error: usageError } = useQuery<UsageData>({
    queryKey: ["stats-me-usage"],
    queryFn: async () => {
      const { data } = await api.get("/stats/me/usage");
      return data;
    },
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

  const { data: systemMetrics } = useQuery<SystemMetrics>({
    queryKey: ["stats-system"],
    queryFn: async () => {
      const { data } = await api.get("/stats/system");
      return data;
    },
    refetchInterval: 5000,
  });

  const { data: billingMe } = useQuery<BillingMe>({
    queryKey: ["billing-me"],
    queryFn: async () => {
      const { data } = await api.get("/billing/me");
      return data;
    },
    enabled: !isSudo,
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
      <SimpleGrid columns={{ base: 1, md: isSudo ? 3 : 2 }} gap={4}>
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
        <SectionCard title="Quota Usage">
          <VStack align="stretch" gap={3}>
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
        </SectionCard>
      ) : (
        <SectionCard title="Quota Usage">
          <Text color="fg.muted" fontSize="sm">No quota limit set. Usage: {formatBytes(used)}</Text>
        </SectionCard>
      )}

      {!isSudo && billingMe && (
        <SectionCard title="Billing">
          <VStack align="stretch" gap={3}>
            <Flex justify="space-between" align="center">
              <Text fontSize="sm" color="fg.muted">Current debt</Text>
              <Text fontSize="xl" fontWeight="bold" color={billingMe.debt > 0 ? "red.400" : "fg"}>
                ${billingMe.debt.toFixed(2)}
              </Text>
            </Flex>
            <SimpleGrid columns={2} gap={3} pt={2} borderTop="1px solid" borderColor="border">
              <VStack align="stretch" gap={1}>
                <Text fontSize="xs" color="fg.subtle">Unlimited users</Text>
                <Text fontSize="sm" fontWeight="medium">{billingMe.unlimited_user_count} ({billingMe.total_user_months} months)</Text>
                {billingMe.price_per_user != null && (
                  <Text fontSize="xs" color="fg.subtle">${billingMe.price_per_user}/user/mo</Text>
                )}
              </VStack>
              <VStack align="stretch" gap={1}>
                <Text fontSize="xs" color="fg.subtle">Volumed users</Text>
                <Text fontSize="sm" fontWeight="medium">{billingMe.volumed_user_count} ({formatBytes(billingMe.volumed_total_bytes)})</Text>
                {billingMe.price_per_gb != null && (
                  <Text fontSize="xs" color="fg.subtle">${billingMe.price_per_gb}/GB</Text>
                )}
              </VStack>
            </SimpleGrid>
          </VStack>
        </SectionCard>
      )}

      {systemMetrics && (
        <SimpleGrid columns={{ base: 1, md: 3 }} gap={4}>
          <SectionCard title={<Flex align="center" gap={2}><FiCpu /> CPU</Flex>}>
            <GaugeBar label="Usage" percent={systemMetrics.cpu_percent} color="blue" />
          </SectionCard>
          <SectionCard title={<Flex align="center" gap={2}><FiServer /> RAM</Flex>}>
            <GaugeBar label="Usage" percent={systemMetrics.ram.percent} color="purple" />
            <Text fontSize="xs" color="fg.muted" mt={2}>
              {formatBytes(systemMetrics.ram.used_bytes)} / {formatBytes(systemMetrics.ram.total_bytes)}
            </Text>
          </SectionCard>
          <SectionCard title={<Flex align="center" gap={2}><FiDatabase /> Disk</Flex>}>
            <GaugeBar label="Usage" percent={systemMetrics.disk.percent} color="teal" />
            <Text fontSize="xs" color="fg.muted" mt={2}>
              {formatBytes(systemMetrics.disk.used_bytes)} / {formatBytes(systemMetrics.disk.total_bytes)}
            </Text>
          </SectionCard>
        </SimpleGrid>
      )}

      <SimpleGrid columns={{ base: 1, lg: 2 }} gap={4}>
        <SectionCard title="Traffic Over Time (30 days)">
          {chartData.length === 0 ? (
            <EmptyState icon={<FiActivity size={32} style={{ opacity: 0.3 }} />} message="No traffic data yet" />
          ) : (
            <Box h="200px">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="trafficGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#396fe4" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#396fe4" stopOpacity={0} />
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
                    stroke="#396fe4"
                    strokeWidth={2}
                    fill="url(#trafficGrad)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </Box>
          )}
        </SectionCard>

        {statusBreakdown && <StatusDonut data={statusBreakdown} />}
      </SimpleGrid>

      {topUsers && topUsers.length > 0 && (
        <SectionCard title="Top Users by Usage">
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
        </SectionCard>
      )}
    </VStack>
  );
}
