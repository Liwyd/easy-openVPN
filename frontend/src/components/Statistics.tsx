import { Box, Flex, HStack, Text } from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import { FiUsers, FiActivity, FiServer } from "react-icons/fi";
import api from "../lib/api";
import { formatBytes } from "../utils/formatByte";
import { useTranslation } from "react-i18next";

interface SummaryData {
  total_users: number;
  total_admins: number;
  total_traffic_bytes: number;
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

function StatisticCard({
  title,
  content,
  icon,
}: {
  title: string;
  content: React.ReactNode;
  icon: React.ReactNode;
}) {
  return (
    <Box
      p={6}
      borderWidth="1px"
      borderColor="border"
      bg="bg.subtle"
      _dark={{ borderColor: "gray.600", bg: "gray.750" }}
      borderStyle="solid"
      boxShadow="none"
      borderRadius="12px"
      width="full"
      display="flex"
      justifyContent="space-between"
      flexDirection="row"
      alignItems="center"
    >
      <HStack alignItems="center" columnGap="4">
        <Box
          p="2"
          position="relative"
          color="white"
          _before={{
            content: `""`,
            position: "absolute",
            top: 0,
            left: 0,
            bg: "primary.400",
            display: "block",
            w: "full",
            h: "full",
            borderRadius: "5px",
            opacity: ".5",
            zIndex: "1",
          }}
          _after={{
            content: `""`,
            position: "absolute",
            top: "-5px",
            left: "-5px",
            bg: "primary.400",
            display: "block",
            w: "calc(100% + 10px)",
            h: "calc(100% + 10px)",
            borderRadius: "8px",
            opacity: ".4",
            zIndex: "1",
          }}
        >
          <Box position="relative" zIndex="2" w={5} h={5}>
            {icon}
          </Box>
        </Box>
        <Text
          color="gray.600"
          _dark={{ color: "gray.300" }}
          fontWeight="medium"
          textTransform="capitalize"
          fontSize="sm"
        >
          {title}
        </Text>
      </HStack>
      <Box fontSize="3xl" fontWeight="semibold" mt="2">
        {content}
      </Box>
    </Box>
  );
}

export default function Statistics() {
  const { t } = useTranslation();
  const { data: summary } = useQuery<SummaryData>({
    queryKey: ["stats-summary"],
    queryFn: async () => {
      const { data } = await api.get("/stats/summary");
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

  return (
    <Flex
      gap={{ base: 4, lg: 0 }}
      columnGap={{ lg: 4, md: 0 }}
      rowGap={{ lg: 0, base: 4 }}
      display="flex"
      flexDirection={{ base: "column", lg: "row" }}
      justifyContent="space-between"
      mb={4}
    >
      <StatisticCard
        title={t("stats.activeUsers")}
        content={
          summary && statusBreakdown ? (
            <HStack alignItems="flex-end">
              <Text>{statusBreakdown.active.toLocaleString()}</Text>
              <Text
                fontWeight="normal"
                fontSize="lg"
                as="span"
                display="inline-block"
                pb="5px"
              >
                / {summary.total_users.toLocaleString()}
              </Text>
            </HStack>
          ) : (
            <Text>—</Text>
          )
        }
        icon={<FiUsers size={20} />}
      />
      <StatisticCard
        title={t("stats.dataUsage")}
        content={
          summary ? <Text>{formatBytes(summary.total_traffic_bytes)}</Text> : <Text>—</Text>
        }
        icon={<FiActivity size={20} />}
      />
      <StatisticCard
        title={t("stats.memoryUsage")}
        content={
          systemMetrics ? (
            <HStack alignItems="flex-end">
              <Text>{formatBytes(systemMetrics.ram.used_bytes)}</Text>
              <Text
                fontWeight="normal"
                fontSize="lg"
                as="span"
                display="inline-block"
                pb="5px"
              >
                / {formatBytes(systemMetrics.ram.total_bytes)}
              </Text>
            </HStack>
          ) : (
            <Text>—</Text>
          )
        }
        icon={<FiServer size={20} />}
      />
    </Flex>
  );
}