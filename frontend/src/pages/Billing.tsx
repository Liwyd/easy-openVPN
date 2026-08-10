import { useState } from "react";
import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import {
  Box,
  Heading,
  Text,
  VStack,
  HStack,
  Flex,
  Button,
  Badge,
  Input,
  Spinner,
  Dialog,
  Portal,
  Field,
  Table,
  SimpleGrid,
  For,
} from "@chakra-ui/react";
import {
  FiDollarSign,
  FiArrowUp,
  FiCheck,
  FiEye,
} from "react-icons/fi";
import api from "../lib/api";
import { toaster } from "../lib/toaster";
import {
  card,
  tableRoot,
  buttonSolid,
  buttonOutline,
} from "../theme-components";

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

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / 1024 ** i).toFixed(1)} ${units[i]}`;
}

function fmtDebt(v: number): string {
  return `$${v.toFixed(2)}`;
}

export default function Billing() {
  const queryClient = useQueryClient();

  const { data: admins, isLoading } = useQuery<BillingAdmin[]>({
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
      toaster.create({ title: "Debt settled", type: "success" });
    },
    onError: (err: any) => {
      toaster.create({ title: err?.response?.data?.detail || "Settlement failed", type: "error" });
    },
  });

  const topupMutation = useMutation({
    mutationFn: async ({ adminId, bytes }: { adminId: number; bytes: number }) =>
      api.post(`/billing/${adminId}/topup`, { bytes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["billing-summary"] });
      setTopupTarget(null);
      setTopupGB("");
      toaster.create({ title: "Capacity topped up", type: "success" });
    },
    onError: (err: any) => {
      toaster.create({ title: err?.response?.data?.detail || "Top-up failed", type: "error" });
    },
  });

  const pricingMutation = useMutation({
    mutationFn: async ({ adminId, price_per_user, price_per_gb }: { adminId: number; price_per_user: number | null; price_per_gb: number | null }) =>
      api.put(`/billing/${adminId}/pricing`, { price_per_user, price_per_gb }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["billing-summary"] });
      setPricingTarget(null);
      toaster.create({ title: "Pricing updated", type: "success" });
    },
    onError: (err: any) => {
      toaster.create({ title: err?.response?.data?.detail || "Failed to update pricing", type: "error" });
    },
  });

  const totalDebt = admins?.reduce((s, a) => s + a.debt, 0) ?? 0;
  const totalUsers = admins?.reduce((s, a) => s + a.unlimited_user_count + a.volumed_user_count, 0) ?? 0;

  return (
    <VStack align="stretch" gap={6}>
      <Heading size="lg">Billing</Heading>

      <SimpleGrid columns={{ base: 1, md: 3 }} gap={4}>
        <Box {...card} p={5}>
          <Flex align="center" gap={3}>
            <Box color="red.400" p={2} borderRadius="md" bg="red.400/10">
              <FiDollarSign size={20} />
            </Box>
            <Box>
              <Text fontSize="xs" color="fg.muted" textTransform="uppercase">Total Debt</Text>
              <Text fontSize="2xl" fontWeight="bold" color="red.400">{fmtDebt(totalDebt)}</Text>
            </Box>
          </Flex>
        </Box>
        <Box {...card} p={5}>
          <Flex align="center" gap={3}>
            <Box color="blue.400" p={2} borderRadius="md" bg="blue.400/10">
              <FiArrowUp size={20} />
            </Box>
            <Box>
              <Text fontSize="xs" color="fg.muted" textTransform="uppercase">Sub-Admins</Text>
              <Text fontSize="2xl" fontWeight="bold">{admins?.length ?? 0}</Text>
            </Box>
          </Flex>
        </Box>
        <Box {...card} p={5}>
          <Flex align="center" gap={3}>
            <Box color="green.400" p={2} borderRadius="md" bg="green.400/10">
              <FiCheck size={20} />
            </Box>
            <Box>
              <Text fontSize="xs" color="fg.muted" textTransform="uppercase">Total Users</Text>
              <Text fontSize="2xl" fontWeight="bold">{totalUsers}</Text>
            </Box>
          </Flex>
        </Box>
      </SimpleGrid>

      {isLoading ? (
        <Flex py={20} justify="center"><Spinner size="lg" color="accent" /></Flex>
      ) : !admins || admins.length === 0 ? (
        <Box {...card} p={12} textAlign="center">
          <Text color="fg.muted">No sub-admins yet.</Text>
        </Box>
      ) : (
        <Box css={tableRoot} overflowX="auto">
          <Table.Root size="sm" variant="outline">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Admin</Table.ColumnHeader>
                <Table.ColumnHeader textAlign="center">Users</Table.ColumnHeader>
                <Table.ColumnHeader textAlign="center">Unlimited</Table.ColumnHeader>
                <Table.ColumnHeader textAlign="center">User-Mo</Table.ColumnHeader>
                <Table.ColumnHeader>Capacity</Table.ColumnHeader>
                <Table.ColumnHeader>$/User</Table.ColumnHeader>
                <Table.ColumnHeader>$/GB</Table.ColumnHeader>
                <Table.ColumnHeader textAlign="right">Debt</Table.ColumnHeader>
                <Table.ColumnHeader textAlign="right">Actions</Table.ColumnHeader>
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
                        {adm.data_limit ? `${formatBytes(adm.data_used)} / ${formatBytes(adm.data_limit)}` : "Unlimited"}
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
                        <Button size="xs" variant="ghost" onClick={() => {
                          setPricingTarget(adm);
                          setPricingUser(adm.price_per_user?.toString() ?? "");
                          setPricingGB(adm.price_per_gb?.toString() ?? "");
                        }}>
                          $
                        </Button>
                        <Button size="xs" variant="ghost" colorPalette="green" onClick={() => setTopupTarget(adm)}>
                          <FiArrowUp />
                        </Button>
                        <Button size="xs" variant="ghost" colorPalette="blue" onClick={() => setSettleTarget(adm)}>
                          <FiCheck />
                        </Button>
                        <Button size="xs" variant="ghost" onClick={() => setRecordsTarget(adm)}>
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
              <Dialog.Header><Dialog.Title>Settle: {settleTarget?.username}</Dialog.Title></Dialog.Header>
              <Dialog.Body>
                <VStack gap={3} align="stretch">
                  <Text fontSize="sm" color="fg.muted">Current debt: {fmtDebt(settleTarget?.debt ?? 0)}</Text>
                  <Field.Root>
                    <Field.Label>Settlement amount ($)</Field.Label>
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
                  <Button variant="outline" css={buttonOutline}>Cancel</Button>
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
                  Settle
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
              <Dialog.Header><Dialog.Title>Top Up: {topupTarget?.username}</Dialog.Title></Dialog.Header>
              <Dialog.Body>
                <VStack gap={3} align="stretch">
                  <Text fontSize="sm" color="fg.muted">
                    Current capacity: {topupTarget?.data_limit ? formatBytes(topupTarget.data_limit) : "None"}
                  </Text>
                  <Field.Root>
                    <Field.Label>Add capacity (GB)</Field.Label>
                    <Input
                      type="number"
                      value={topupGB}
                      onChange={(e) => setTopupGB(e.target.value)}
                      placeholder="e.g. 50"
                      min="0"
                    />
                  </Field.Root>
                </VStack>
              </Dialog.Body>
              <Dialog.Footer>
                <Dialog.CloseTrigger asChild>
                  <Button variant="outline" css={buttonOutline}>Cancel</Button>
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
                  Top Up
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
              <Dialog.Header><Dialog.Title>Pricing: {pricingTarget?.username}</Dialog.Title></Dialog.Header>
              <Dialog.Body>
                <VStack gap={3} align="stretch">
                  <Field.Root>
                    <Field.Label>Price per unlimited user ($)</Field.Label>
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
                    <Field.Label>Price per GB ($)</Field.Label>
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
                  <Button variant="outline" css={buttonOutline}>Cancel</Button>
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
                  Save Pricing
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
                <Dialog.Title>Billing Records: {recordsTarget?.username}</Dialog.Title>
              </Dialog.Header>
              <Dialog.Body>
                {recordsLoading ? (
                  <Flex py={8} justify="center"><Spinner size="sm" /></Flex>
                ) : !records || records.length === 0 ? (
                  <Text color="fg.muted" fontSize="sm" py={4}>No records yet.</Text>
                ) : (
                  <Box maxH="400px" overflowY="auto">
                    <Table.Root size="sm">
                      <Table.Header>
                        <Table.Row>
                          <Table.ColumnHeader>Date</Table.ColumnHeader>
                          <Table.ColumnHeader>Type</Table.ColumnHeader>
                          <Table.ColumnHeader>Description</Table.ColumnHeader>
                          <Table.ColumnHeader textAlign="right">Amount</Table.ColumnHeader>
                        </Table.Row>
                      </Table.Header>
                      <Table.Body>
                        {records.map((r) => (
                          <Table.Row key={r.id}>
                            <Table.Cell fontSize="xs">{new Date(r.created_at).toLocaleDateString()}</Table.Cell>
                            <Table.Cell>
                              <Badge
                                colorPalette={
                                  r.type === "settlement" ? "green" :
                                  r.type === "user_charge" ? "purple" : "blue"
                                }
                                variant="subtle"
                                fontSize="xs"
                              >
                                {r.type === "user_charge" ? "users" :
                                 r.type === "traffic_charge" ? "traffic" : "settlement"}
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
                  <Button variant="outline" css={buttonOutline}>Close</Button>
                </Dialog.CloseTrigger>
              </Dialog.Footer>
            </Dialog.Content>
          </Dialog.Positioner>
        </Portal>
      </Dialog.Root>
    </VStack>
  );
}
