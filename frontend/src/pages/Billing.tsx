import { useState } from "react";
import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import {
  Box,
  Text,
  VStack,
  HStack,
  Flex,
  Button,
  Badge,
  Input,
  Spinner,
  Alert,
  Dialog,
  Portal,
  Field,
  Table,
  SimpleGrid,
  For,
  Tooltip,
} from "@chakra-ui/react";
import {
  FiDollarSign,
  FiArrowUp,
  FiCheck,
  FiEye,
  FiUsers,
  FiShield,
  FiHelpCircle,
} from "react-icons/fi";
import api from "../lib/api";
import { toaster } from "../lib/toaster";
import { useTranslation } from "react-i18next";
import { card, tableRoot, buttonSolid, buttonOutline } from "../theme-components";
import StatCard from "../components/StatCard";
import EmptyState from "../components/EmptyState";
import { formatBytes } from "../utils/formatByte";
import { formatDate } from "../utils/dateFormatter";

interface BillingAdmin {
  admin_id: number;
  username: string;
  is_sudo: boolean;
  price_per_user: number | null;
  price_per_gb: number | null;
  debt: number;
  data_limit: number | null;
  data_used: number;
  unlimited_user_count: number;
  volumed_user_count: number;
  total_user_months: number;
}

interface BillingRecord {
  id: number;
  admin_id: number;
  type: string;
  amount: number;
  description: string;
  created_at: string;
}

function fmtDebt(v: number): string {
  return `$${v.toFixed(2)}`;
}

function HeaderWithHelp({ label, help }: { label: string; help: string }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: "5px" }}>
      {label}
      <Tooltip.Root positioning={{ placement: "top" }}>
        <Tooltip.Trigger>
          <span style={{ display: "inline-flex", cursor: "help" }}>
            <FiHelpCircle size={13} style={{ opacity: 0.65 }} />
          </span>
        </Tooltip.Trigger>
        <Tooltip.Positioner>
          <Tooltip.Content fontSize="xs" maxW="220px">
            {help}
          </Tooltip.Content>
        </Tooltip.Positioner>
      </Tooltip.Root>
    </span>
  );
}

export default function Billing() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const { data: admins, isLoading, error } = useQuery<BillingAdmin[]>({
    queryKey: ["billing-summary"],
    queryFn: async () => {
      const { data } = await api.get("/billing/summary");
      return data;
    },
  });

  const [settleTarget, setSettleTarget] = useState<BillingAdmin | null>(null);
  const [settleAmount, setSettleAmount] = useState("");

  const [topupTarget, setTopupTarget] = useState<BillingAdmin | null>(null);
  const [topupGB, setTopupGB] = useState("");

  const [pricingTarget, setPricingTarget] = useState<BillingAdmin | null>(null);
  const [pricingUser, setPricingUser] = useState("");
  const [pricingGB, setPricingGB] = useState("");

  const [recordsTarget, setRecordsTarget] = useState<BillingAdmin | null>(null);
  const { data: records, isLoading: recordsLoading } = useQuery<BillingRecord[]>({
    queryKey: ["billing-records", recordsTarget?.admin_id],
    queryFn: async () => {
      const { data } = await api.get(`/billing/${recordsTarget!.admin_id}`);
      return data;
    },
    enabled: !!recordsTarget,
  });

  const settleMutation = useMutation({
    mutationFn: async ({ adminId, amount }: { adminId: number; amount: number }) =>
      api.post(`/billing/${adminId}/settle`, { amount }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["billing-summary"] });
      queryClient.invalidateQueries({ queryKey: ["billing-records"] });
      setSettleTarget(null);
      setSettleAmount("");
      toaster.create({ title: t("billing.debtSettled"), type: "success" });
    },
    onError: (err: any) => {
      toaster.create({ title: typeof err?.response?.data?.detail === "string" ? err.response.data.detail : t("billing.settlementFailed"), type: "error" });
    },
  });

  const topupMutation = useMutation({
    mutationFn: async ({ adminId, bytes }: { adminId: number; bytes: number }) =>
      api.post(`/billing/${adminId}/topup`, { bytes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["billing-summary"] });
      setTopupTarget(null);
      setTopupGB("");
      toaster.create({ title: t("billing.capacityToppedUp"), type: "success" });
    },
    onError: (err: any) => {
      toaster.create({ title: typeof err?.response?.data?.detail === "string" ? err.response.data.detail : t("billing.topupFailed"), type: "error" });
    },
  });

  const pricingMutation = useMutation({
    mutationFn: async ({ adminId, price_per_user, price_per_gb }: { adminId: number; price_per_user: number | null; price_per_gb: number | null }) =>
      api.put(`/billing/${adminId}/pricing`, { price_per_user, price_per_gb }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["billing-summary"] });
      setPricingTarget(null);
      toaster.create({ title: t("billing.pricingUpdated"), type: "success" });
    },
    onError: (err: any) => {
      toaster.create({ title: typeof err?.response?.data?.detail === "string" ? err.response.data.detail : t("billing.pricingFailed"), type: "error" });
    },
  });

  const totalDebt = admins?.reduce((s, a) => s + a.debt, 0) ?? 0;
  const totalUsers = admins?.reduce((s, a) => s + a.unlimited_user_count + a.volumed_user_count, 0) ?? 0;

  return (
    <VStack align="stretch" gap={6}>
      <SimpleGrid columns={{ base: 1, md: 3 }} gap={4}>
        <StatCard
          label={t("billing.totalDebt")}
          value={fmtDebt(totalDebt)}
          icon={<FiDollarSign size={20} />}
          color="red.400"
          valueColor="red.400"
        />
        <StatCard
          label={t("billing.subAdmins")}
          value={admins?.length ?? 0}
          icon={<FiShield size={20} />}
          color="blue.400"
        />
        <StatCard
          label={t("billing.totalUsers")}
          value={totalUsers}
          icon={<FiUsers size={20} />}
          color="green.400"
        />
      </SimpleGrid>

      {isLoading ? (
        <Flex py={20} justify="center"><Spinner size="lg" color="accent" /></Flex>
      ) : error ? (
        <Alert.Root status="error" borderRadius="lg">
          <Alert.Title>{t("billing.failedToLoad")}</Alert.Title>
          <Alert.Description>
            {(error as Error).message || t("billing.unexpectedError")}
          </Alert.Description>
        </Alert.Root>
      ) : !admins || admins.length === 0 ? (
        <Box css={card} p={6}>
          <EmptyState
            icon={<FiUsers size={40} style={{ margin: "0 auto 16px", opacity: 0.3 }} />}
            message={t("billing.empty")}
          />
        </Box>
      ) : (
        <Box css={tableRoot} overflowX="auto">
          <Table.Root size="sm" variant="outline">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>
                  <HeaderWithHelp label={t("billing.admin")} help={t("billing.help.admin")} />
                </Table.ColumnHeader>
                <Table.ColumnHeader textAlign="center">
                  <HeaderWithHelp label={t("billing.users")} help={t("billing.help.users")} />
                </Table.ColumnHeader>
                <Table.ColumnHeader textAlign="center">
                  <HeaderWithHelp label={t("billing.unlimited")} help={t("billing.help.unlimited")} />
                </Table.ColumnHeader>
                <Table.ColumnHeader textAlign="center">
                  <HeaderWithHelp label={t("billing.userMonths")} help={t("billing.help.userMonths")} />
                </Table.ColumnHeader>
                <Table.ColumnHeader>
                  <HeaderWithHelp label={t("billing.capacity")} help={t("billing.help.capacity")} />
                </Table.ColumnHeader>
                <Table.ColumnHeader>
                  <HeaderWithHelp label={t("billing.pricePerUser")} help={t("billing.help.pricePerUser")} />
                </Table.ColumnHeader>
                <Table.ColumnHeader>
                  <HeaderWithHelp label={t("billing.pricePerGB")} help={t("billing.help.pricePerGB")} />
                </Table.ColumnHeader>
                <Table.ColumnHeader textAlign="right">
                  <HeaderWithHelp label={t("billing.debt")} help={t("billing.help.debt")} />
                </Table.ColumnHeader>
                <Table.ColumnHeader textAlign="right">{t("billing.actions")}</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              <For each={admins}>
                {(adm) => (
                  <Table.Row key={adm.admin_id}>
                    <Table.Cell fontWeight="medium">{adm.username}</Table.Cell>
                    <Table.Cell textAlign="center">
                      <Badge colorPalette="blue" variant="subtle" fontSize="xs">
                        {adm.volumed_user_count + adm.unlimited_user_count}
                      </Badge>
                    </Table.Cell>
                    <Table.Cell textAlign="center">
                      <Badge colorPalette="purple" variant="subtle" fontSize="xs">
                        {adm.unlimited_user_count}
                      </Badge>
                    </Table.Cell>
                    <Table.Cell textAlign="center">
                      <Text fontSize="sm">{adm.total_user_months}</Text>
                    </Table.Cell>
                    <Table.Cell>
                      <Text fontSize="xs" color="fg.muted">
                        {adm.data_limit ? `${formatBytes(adm.data_used)} / ${formatBytes(adm.data_limit)}` : t("billing.unlimited")}
                      </Text>
                    </Table.Cell>
                    <Table.Cell>
                      <Text fontSize="sm">{adm.price_per_user != null ? `$${adm.price_per_user}` : "—"}</Text>
                    </Table.Cell>
                    <Table.Cell>
                      <Text fontSize="sm">{adm.price_per_gb != null ? `$${adm.price_per_gb}` : "—"}</Text>
                    </Table.Cell>
                    <Table.Cell textAlign="right">
                      <Text fontSize="sm" fontWeight="bold" color={adm.debt > 0 ? "red.400" : "fg.muted"}>
                        {fmtDebt(adm.debt)}
                      </Text>
                    </Table.Cell>
                    <Table.Cell textAlign="right">
                      <HStack gap={1} justify="flex-end">
                        <Button size="xs" variant="ghost" title={t("billing.pricing")} onClick={() => {
                          setPricingTarget(adm);
                          setPricingUser(adm.price_per_user?.toString() ?? "");
                          setPricingGB(adm.price_per_gb?.toString() ?? "");
                        }}>
                          $
                        </Button>
                        <Button size="xs" variant="ghost" colorPalette="green" title={t("billing.topUp")} onClick={() => setTopupTarget(adm)}>
                          <FiArrowUp />
                        </Button>
                        <Button size="xs" variant="ghost" colorPalette="blue" title={t("billing.settle")} onClick={() => setSettleTarget(adm)}>
                          <FiCheck />
                        </Button>
                        <Button size="xs" variant="ghost" title={t("billing.records")} onClick={() => setRecordsTarget(adm)}>
                          <FiEye />
                        </Button>
                      </HStack>
                    </Table.Cell>
                  </Table.Row>
                )}
              </For>
            </Table.Body>
          </Table.Root>
        </Box>
      )}

      {/* Settle Dialog */}
      <Dialog.Root open={!!settleTarget} onOpenChange={(e) => { if (!e.open) { setSettleTarget(null); setSettleAmount(""); } }}>
        <Portal>
          <Dialog.Backdrop />
          <Dialog.Positioner>
            <Dialog.Content maxW="sm">
              <Dialog.Header><Dialog.Title>{t("billing.settleTitle", { username: settleTarget?.username })}</Dialog.Title></Dialog.Header>
              <Dialog.Body>
                <VStack gap={3} align="stretch">
                  <Text fontSize="sm" color="fg.muted">{t("billing.currentDebt", { amount: fmtDebt(settleTarget?.debt ?? 0) })}</Text>
                  <Field.Root>
                    <Field.Label>{t("billing.settlementAmount")}</Field.Label>
                    <Input
                      type="number"
                      value={settleAmount}
                      onChange={(e) => setSettleAmount(e.target.value)}
                      placeholder="0.00"
                      min="0"
                      step="0.01"
                    />
                  </Field.Root>
                </VStack>
              </Dialog.Body>
              <Dialog.Footer>
                <Dialog.CloseTrigger asChild>
                  <Button variant="outline" css={buttonOutline}>{t("billing.cancel")}</Button>
                </Dialog.CloseTrigger>
                <Button
                  css={buttonSolid}
                  disabled={!settleAmount || parseFloat(settleAmount) <= 0}
                  onClick={() => {
                    if (settleTarget && settleAmount) {
                      settleMutation.mutate({ adminId: settleTarget.admin_id, amount: parseFloat(settleAmount) });
                    }
                  }}
                  loading={settleMutation.isPending}
                >
                  {t("billing.settle")}
                </Button>
              </Dialog.Footer>
            </Dialog.Content>
          </Dialog.Positioner>
        </Portal>
      </Dialog.Root>

      {/* Top-Up Dialog */}
      <Dialog.Root open={!!topupTarget} onOpenChange={(e) => { if (!e.open) { setTopupTarget(null); setTopupGB(""); } }}>
        <Portal>
          <Dialog.Backdrop />
          <Dialog.Positioner>
            <Dialog.Content maxW="sm">
              <Dialog.Header><Dialog.Title>{t("billing.topUpTitle", { username: topupTarget?.username })}</Dialog.Title></Dialog.Header>
              <Dialog.Body>
                <VStack gap={3} align="stretch">
                  <Text fontSize="sm" color="fg.muted">
                    {t("billing.currentCapacity", { capacity: topupTarget?.data_limit ? formatBytes(topupTarget.data_limit) : t("billing.capacityNone") })}
                  </Text>
                  <Field.Root>
                    <Field.Label>{t("billing.addCapacity")}</Field.Label>
                    <Input
                      type="number"
                      value={topupGB}
                      onChange={(e) => setTopupGB(e.target.value)}
                      placeholder={t("billing.capacityPlaceholder")}
                      min="0"
                    />
                  </Field.Root>
                </VStack>
              </Dialog.Body>
              <Dialog.Footer>
                <Dialog.CloseTrigger asChild>
                  <Button variant="outline" css={buttonOutline}>{t("billing.cancel")}</Button>
                </Dialog.CloseTrigger>
                <Button
                  css={buttonSolid}
                  disabled={!topupGB || parseFloat(topupGB) <= 0}
                  onClick={() => {
                    if (topupTarget && topupGB) {
                      const bytes = Math.round(parseFloat(topupGB) * 1024 ** 3);
                      topupMutation.mutate({ adminId: topupTarget.admin_id, bytes });
                    }
                  }}
                  loading={topupMutation.isPending}
                >
                  {t("billing.topUp")}
                </Button>
              </Dialog.Footer>
            </Dialog.Content>
          </Dialog.Positioner>
        </Portal>
      </Dialog.Root>

      {/* Pricing Dialog */}
      <Dialog.Root open={!!pricingTarget} onOpenChange={(e) => { if (!e.open) setPricingTarget(null); }}>
        <Portal>
          <Dialog.Backdrop />
          <Dialog.Positioner>
            <Dialog.Content maxW="sm">
              <Dialog.Header><Dialog.Title>{t("billing.pricingTitle", { username: pricingTarget?.username })}</Dialog.Title></Dialog.Header>
              <Dialog.Body>
                <VStack gap={3} align="stretch">
                  <Field.Root>
                    <Field.Label>{t("billing.pricePerUnlimitedUser")}</Field.Label>
                    <Input
                      type="number"
                      value={pricingUser}
                      onChange={(e) => setPricingUser(e.target.value)}
                      placeholder="0.00"
                      min="0"
                      step="0.01"
                    />
                  </Field.Root>
                  <Field.Root>
                    <Field.Label>{t("billing.pricePerGBLabel")}</Field.Label>
                    <Input
                      type="number"
                      value={pricingGB}
                      onChange={(e) => setPricingGB(e.target.value)}
                      placeholder="0.00"
                      min="0"
                      step="0.01"
                    />
                  </Field.Root>
                </VStack>
              </Dialog.Body>
              <Dialog.Footer>
                <Dialog.CloseTrigger asChild>
                  <Button variant="outline" css={buttonOutline}>{t("billing.cancel")}</Button>
                </Dialog.CloseTrigger>
                <Button
                  css={buttonSolid}
                  onClick={() => {
                    if (pricingTarget) {
                      pricingMutation.mutate({
                        adminId: pricingTarget.admin_id,
                        price_per_user: pricingUser ? parseFloat(pricingUser) : null,
                        price_per_gb: pricingGB ? parseFloat(pricingGB) : null,
                      });
                    }
                  }}
                  loading={pricingMutation.isPending}
                >
                  {t("billing.savePricing")}
                </Button>
              </Dialog.Footer>
            </Dialog.Content>
          </Dialog.Positioner>
        </Portal>
      </Dialog.Root>

      {/* Records Dialog */}
      <Dialog.Root open={!!recordsTarget} onOpenChange={(e) => { if (!e.open) setRecordsTarget(null); }}>
        <Portal>
          <Dialog.Backdrop />
          <Dialog.Positioner>
            <Dialog.Content maxW="lg">
              <Dialog.Header>
                <Dialog.Title>{t("billing.recordsTitle", { username: recordsTarget?.username })}</Dialog.Title>
              </Dialog.Header>
              <Dialog.Body>
                {recordsLoading ? (
                  <Flex py={8} justify="center"><Spinner size="sm" /></Flex>
                ) : !records || records.length === 0 ? (
                  <Text color="fg.muted" fontSize="sm" py={4}>{t("billing.noRecords")}</Text>
                ) : (
                  <Box maxH="400px" overflowY="auto">
                    <Table.Root size="sm">
                      <Table.Header>
                        <Table.Row>
                          <Table.ColumnHeader>{t("billing.date")}</Table.ColumnHeader>
                          <Table.ColumnHeader>{t("billing.type")}</Table.ColumnHeader>
                          <Table.ColumnHeader>{t("billing.description")}</Table.ColumnHeader>
                          <Table.ColumnHeader textAlign="right">{t("billing.amount")}</Table.ColumnHeader>
                        </Table.Row>
                      </Table.Header>
                      <Table.Body>
                        {records.map((r) => (
                          <Table.Row key={r.id}>
                            <Table.Cell fontSize="xs">{formatDate(r.created_at)}</Table.Cell>
                            <Table.Cell>
                              <Badge
                                colorPalette={
                                  r.type === "settlement" ? "green" :
                                  r.type === "user_charge" ? "purple" : "blue"
                                }
                                variant="subtle"
                                fontSize="xs"
                              >
                                {r.type === "user_charge" ? t("billing.typeUsers") :
                                 r.type === "traffic_charge" ? t("billing.typeTraffic") : t("billing.typeSettlement")}
                              </Badge>
                            </Table.Cell>
                            <Table.Cell fontSize="xs">{r.description}</Table.Cell>
                            <Table.Cell textAlign="right" fontSize="xs" fontWeight="medium" color={r.amount < 0 ? "green.400" : "fg"}>
                              {r.amount < 0 ? `-${fmtDebt(Math.abs(r.amount))}` : fmtDebt(r.amount)}
                            </Table.Cell>
                          </Table.Row>
                        ))}
                      </Table.Body>
                    </Table.Root>
                  </Box>
                )}
              </Dialog.Body>
              <Dialog.Footer>
                <Dialog.CloseTrigger asChild>
                  <Button variant="outline" css={buttonOutline}>{t("billing.close")}</Button>
                </Dialog.CloseTrigger>
              </Dialog.Footer>
            </Dialog.Content>
          </Dialog.Positioner>
        </Portal>
      </Dialog.Root>
    </VStack>
  );
}
