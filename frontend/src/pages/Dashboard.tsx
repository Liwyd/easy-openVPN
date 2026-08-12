import {
  Box,
  Text,
  VStack,
  Progress,
  Flex,
  SimpleGrid,
  HStack,
  Select,
  createListCollection,
} from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
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
import { FiUsers, FiShield, FiActivity, FiCpu, FiDatabase, FiServer, FiClock } from "react-icons/fi";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import LoadingState from "../components/LoadingState";
import ErrorState from "../components/ErrorState";
import EmptyState from "../components/EmptyState";
import StatCard from "../components/StatCard";
import SectionCard from "../components/SectionCard";
import { formatBytes } from "../utils/formatByte";
import { formatUptime } from "../utils/dateFormatter";
import { useTranslation } from "react-i18next";

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
  uptime_seconds: number;
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
  const { t } = useTranslation();
  const total = data.active + data.limited + data.expired + data.disabled;
  const chartData = [
    { key: "active", label: t("status.active"), color: "#38A169", count: data.active },
    { key: "limited", label: t("status.limited"), color: "#ED8936", count: data.limited },
    { key: "expired", label: t("status.expired"), color: "#E53E3E", count: data.expired },
    { key: "disabled", label: t("status.disabled"), color: "#A0AEC0", count: data.disabled },
  ].filter((seg) => seg.count > 0);

  return (
    <SectionCard title={t("dashboard.userStatus")}>
      {total === 0 ? (
        <EmptyState icon={<FiActivity size={32} style={{ opacity: 0.3 }} />} message={t("dashboard.noUsers")} />
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
  const { t } = useTranslation();
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

  const trafficDaysOptions = createListCollection({
    items: [1, 7, 30, 90, 180, 365].map((d) => ({
      value: String(d),
      label: d === 1 ? "24h" : `${d}d`,
    })),
  });

  const [trafficDays, setTrafficDays] = useState(30);

  const { data: usageOverTime } = useQuery<UsageOverTimePoint[]>({
    queryKey: ["stats-usage-over-time", trafficDays],
    queryFn: async () => {
      const { data } = await api.get("/stats/usage-over-time", {
        params: { days: trafficDays },
      });
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
  if (usageError) return <ErrorState message={t("dashboard.failedToLoad")} />;

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
          label={isSudo ? t("dashboard.totalUsers") : t("dashboard.myUsers")}
          value={summary?.total_users ?? 0}
          icon={<FiUsers size={20} />}
        />
        {isSudo && (
          <StatCard
            label={t("dashboard.totalAdmins")}
            value={summary?.total_admins ?? 0}
            icon={<FiShield size={20} />}
          />
        )}
        <StatCard
          label={isSudo ? t("dashboard.totalTraffic") : t("dashboard.myTraffic")}
          value={formatBytes(summary?.total_traffic_bytes ?? 0)}
          icon={<FiActivity size={20} />}
        />
      </SimpleGrid>

      {limit ? (
        <SectionCard title={t("dashboard.quotaUsage")}>
          <VStack align="stretch" gap={3}>
            <Flex justify="space-between" fontSize="sm" color="fg.muted">
              <Text>{formatBytes(used)} {t("dashboard.used")}</Text>
              <Text>{formatBytes(limit)} {t("dashboard.total")}</Text>
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
              <Text>{formatBytes(limit - used)} {t("dashboard.remaining")}</Text>
              <Text>{pct.toFixed(1)}%</Text>
            </Flex>
            {usage && (
              <Box pt={2} borderTop="1px solid" borderColor="border">
                <Text fontSize="xs" color="fg.subtle">
                  {t("dashboard.directUsers")}: {formatBytes(usage.direct_users_bytes)} |{" "}
                  {t("dashboard.childAdmins")}:{" "}
                  {formatBytes(usage.child_admins_bytes)}
                </Text>
              </Box>
            )}
          </VStack>
        </SectionCard>
      ) : (
        <SectionCard title={t("dashboard.quotaUsage")}>
          <Text color="fg.muted" fontSize="sm">
            {t("dashboard.noQuota", { usage: formatBytes(used) })}
          </Text>
        </SectionCard>
      )}

      {!isSudo && billingMe && (
        <SectionCard title={t("dashboard.billing")}>
          <VStack align="stretch" gap={3}>
            <Flex justify="space-between" align="center">
              <Text fontSize="sm" color="fg.muted">{t("dashboard.currentDebt")}</Text>
              <Text fontSize="xl" fontWeight="bold" color={billingMe.debt > 0 ? "red.400" : "fg"}>
                ${billingMe.debt.toFixed(2)}
              </Text>
            </Flex>
            <SimpleGrid columns={2} gap={3} pt={2} borderTop="1px solid" borderColor="border">
              <VStack align="stretch" gap={1}>
                <Text fontSize="xs" color="fg.subtle">{t("dashboard.unlimitedUsers")}</Text>
                <Text fontSize="sm" fontWeight="medium">{billingMe.unlimited_user_count} ({billingMe.total_user_months} {t("dashboard.months")})</Text>
                {billingMe.price_per_user != null && (
                  <Text fontSize="xs" color="fg.subtle">${billingMe.price_per_user}/user/mo</Text>
                )}
              </VStack>
              <VStack align="stretch" gap={1}>
                <Text fontSize="xs" color="fg.subtle">{t("dashboard.volumedUsers")}</Text>
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
        <>
          <SimpleGrid columns={{ base: 1, md: 3 }} gap={4}>
          <SectionCard title={<Flex align="center" gap={2}><FiCpu /> {t("dashboard.cpu")}</Flex>}>
            <GaugeBar label={t("dashboard.usage")} percent={systemMetrics.cpu_percent} color="blue" />
          </SectionCard>
          <SectionCard title={<Flex align="center" gap={2}><FiServer /> {t("dashboard.ram")}</Flex>}>
            <GaugeBar label={t("dashboard.usage")} percent={systemMetrics.ram.percent} color="purple" />
            <Text fontSize="xs" color="fg.muted" mt={2}>
              {formatBytes(systemMetrics.ram.used_bytes)} / {formatBytes(systemMetrics.ram.total_bytes)}
            </Text>
          </SectionCard>
          <SectionCard title={<Flex align="center" gap={2}><FiDatabase /> {t("dashboard.disk")}</Flex>}>
            <GaugeBar label={t("dashboard.usage")} percent={systemMetrics.disk.percent} color="teal" />
            <Text fontSize="xs" color="fg.muted" mt={2}>
              {formatBytes(systemMetrics.disk.used_bytes)} / {formatBytes(systemMetrics.disk.total_bytes)}
            </Text>
          </SectionCard>
        </SimpleGrid>
        <Flex align="center" gap={2} fontSize="sm" color="fg.muted">
          <FiClock size={14} />
          <Text>{t("dashboard.uptime")}: {formatUptime(systemMetrics.uptime_seconds)}</Text>
        </Flex>
        </>
      )}

      <SimpleGrid columns={{ base: 1, lg: 2 }} gap={4}>
        <SectionCard
          title={
            <Flex align="center" justify="space-between" gap={3} width="100%">
              <Text>{t("dashboard.trafficOverTime")}</Text>
              <Select.Root
                collection={trafficDaysOptions}
                value={[String(trafficDays)]}
                onValueChange={(details) =>
                  setTrafficDays(Number(details.value[0]))
                }
                size="xs"
                width="76px"
              >
                <Select.Control>
                  <Select.Trigger>
                    <Select.ValueText />
                  </Select.Trigger>
                </Select.Control>
                <Select.Positioner>
                  <Select.Content>
                    {trafficDaysOptions.items.map((item) => (
                      <Select.Item key={item.value} item={item}>
                        <Select.ItemText>{item.label}</Select.ItemText>
                      </Select.Item>
                    ))}
                  </Select.Content>
                </Select.Positioner>
              </Select.Root>
            </Flex>
          }
        >
          {chartData.length === 0 ? (
            <EmptyState icon={<FiActivity size={32} style={{ opacity: 0.3 }} />} message={t("dashboard.noTraffic")} />
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
        </SectionCard>

        {statusBreakdown && <StatusDonut data={statusBreakdown} />}
      </SimpleGrid>
    </VStack>
  );
}
