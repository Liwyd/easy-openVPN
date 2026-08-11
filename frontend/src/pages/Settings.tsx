import { useRef, useState } from "react";
import {
  Box,
  Heading,
  Text,
  VStack,
  HStack,
  Button,
  Field,
  Input,
  Select,
  Switch,
  SimpleGrid,
  Portal,
  Tabs,
  createListCollection,
} from "@chakra-ui/react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { FiSend, FiKey, FiArchive, FiDownload, FiUpload, FiTrash2, FiLock, FiServer } from "react-icons/fi";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { toaster } from "../lib/toaster";
import LoadingState from "../components/LoadingState";
import ErrorState from "../components/ErrorState";
import SectionCard from "../components/SectionCard";
import ConfirmDialog from "../components/ConfirmDialog";
import { formatBytes } from "../utils/formatByte";

interface ServerConfig {
  id: number;
  protocol: string;
  port: number;
  interface: string;
  cipher: string;
  auth_digest: string;
  tls_mode: string;
  dns_preset: string;
  dns_servers: string[] | null;
  mtu: number | null;
  keepalive_interval: number;
  keepalive_timeout: number;
  client_to_client: boolean;
  redirect_gateway: boolean;
  public_host: string;
  tunnel_host: string;
  subscription_url_prefix: string;
  updated_at: string;
}

interface ApplyResult {
  success: boolean;
  requires_redownload: boolean;
  requires_redownload_fields: string[];
  message: string;
}

interface BackupConfig {
  enabled: boolean;
  schedule_hour: number;
  schedule_minute: number;
  send_to_telegram: boolean;
  keep_count: number;
  last_run_at: string | null;
  last_backup_file: string;
}

interface BackupEntry {
  name: string;
  size_bytes: number;
  created_at: string;
}

const DNS_SERVERS_MAP: Record<string, string[] | null> = {
  cloudflare: ["1.1.1.1", "1.0.0.1"],
  google: ["8.8.8.8", "8.8.4.4"],
  adguard: ["94.140.14.14", "94.140.15.15"],
  custom: null,
};

const protocolCollection = createListCollection({
  items: [
    { label: "UDP", value: "udp" },
    { label: "TCP", value: "tcp" },
  ],
});

const cipherCollection = createListCollection({
  items: [
    { label: "AES-256-GCM", value: "AES-256-GCM" },
    { label: "AES-128-GCM", value: "AES-128-GCM" },
    { label: "CHACHA20-POLY1305", value: "CHACHA20-POLY1305" },
  ],
});

const authCollection = createListCollection({
  items: [
    { label: "SHA256", value: "SHA256" },
    { label: "SHA512", value: "SHA512" },
  ],
});

const tlsCollection = createListCollection({
  items: [
    { label: "tls-crypt", value: "tls-crypt" },
    { label: "tls-auth", value: "tls-auth" },
    { label: "None", value: "none" },
  ],
});

const dnsCollection = createListCollection({
  items: [
    { label: "Cloudflare (1.1.1.1)", value: "cloudflare" },
    { label: "Google (8.8.8.8)", value: "google" },
    { label: "AdGuard (94.140.14.14)", value: "adguard" },
    { label: "Custom", value: "custom" },
  ],
});

const hourCollection = createListCollection({
  items: Array.from({ length: 24 }, (_, h) => ({
    label: String(h).padStart(2, "0"),
    value: String(h),
  })),
});

const minuteCollection = createListCollection({
  items: Array.from({ length: 60 }, (_, m) => ({
    label: String(m).padStart(2, "0"),
    value: String(m),
  })),
});

function BackupSection() {
  const queryClient = useQueryClient();
  const [sendToTelegram, setSendToTelegram] = useState(false);
  const [creating, setCreating] = useState(false);
  const [lastBackup, setLastBackup] = useState<{ filename: string; size_bytes: number } | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [showRestore, setShowRestore] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: config } = useQuery<BackupConfig>({
    queryKey: ["backup-config"],
    queryFn: async () => (await api.get("/backup/config")).data,
  });

  const { data: backups, isLoading: loadingBackups } = useQuery<BackupEntry[]>({
    queryKey: ["backup-list"],
    queryFn: async () => (await api.get("/backup/list")).data,
  });

  const saveConfig = useMutation({
    mutationFn: async (values: Partial<BackupConfig>) => {
      const { data } = await api.put<BackupConfig>("/backup/config", values);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["backup-config"] });
      toaster.create({ title: "Backup schedule saved", type: "success" });
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to save backup schedule";
      toaster.create({ title: msg, type: "error" });
    },
  });

  const createBackup = async () => {
    setCreating(true);
    try {
      const { data } = await api.post("/backup/create", { send_to_telegram: sendToTelegram });
      setLastBackup({ filename: data.filename, size_bytes: data.size_bytes });
      queryClient.invalidateQueries({ queryKey: ["backup-list"] });
      toaster.create({
        title: `Backup created${sendToTelegram ? " and sent to Telegram" : ""}`,
        type: "success",
      });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to create backup";
      toaster.create({ title: msg, type: "error" });
    } finally {
      setCreating(false);
    }
  };

  const downloadBackup = async (name: string) => {
    try {
      const { data } = await api.get("/backup/download", { params: { name }, responseType: "blob" });
      const url = URL.createObjectURL(data);
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toaster.create({ title: "Failed to download backup", type: "error" });
    }
  };

  const deleteBackup = useMutation({
    mutationFn: async (name: string) => {
      await api.delete(`/backup/${name}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["backup-list"] });
      toaster.create({ title: "Backup deleted", type: "success" });
    },
  });

  const confirmRestore = async () => {
    if (!file) return;
    setShowRestore(false);
    const formData = new FormData();
    formData.append("file", file);
    try {
      await api.post("/backup/restore", formData);
      queryClient.invalidateQueries();
      toaster.create({
        title: "Panel restored from backup. Please sign in again.",
        type: "success",
      });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Restore failed";
      toaster.create({ title: msg, type: "error" });
    } finally {
      setFile(null);
    }
  };

  return (
    <SectionCard title="Backup & Restore">
      <VStack align="stretch" gap={5}>
        {/* Create */}
        <Box>
          <Text fontSize="sm" color="fg.muted" mb={2}>
            Create a full backup of the panel: all users, admins, settings,
            billing records, logs and the VPN certificates. Download it and keep
            it safe — restoring it brings the panel back to exactly this state.
          </Text>
          <HStack>
            <Button size="sm" onClick={createBackup} loading={creating} colorPalette="accent">
              <FiArchive style={{ marginRight: 6 }} />
              Create Backup Now
            </Button>
            <Switch.Root checked={sendToTelegram} onCheckedChange={(e) => setSendToTelegram(e.checked)}>
              <Switch.Control>
                <Switch.Thumb />
              </Switch.Control>
              <Switch.Label>Also send to Telegram</Switch.Label>
            </Switch.Root>
          </HStack>
          {lastBackup && (
            <Text fontSize="xs" color="fg.muted" mt={2}>
              {lastBackup.size_bytes ? `Created ${lastBackup.filename} (${formatBytes(lastBackup.size_bytes)}) ` : `Created ${lastBackup.filename} `}
              <Text as="span" textDecoration="underline" cursor="pointer" onClick={() => downloadBackup(lastBackup.filename)}>
                Download
              </Text>
            </Text>
          )}
        </Box>

        {/* Restore */}
        <Box>
          <Text fontSize="sm" color="fg.muted" mb={2}>
            Restore the panel from a backup file.{" "}
            <Text as="span" color="red.400" fontWeight="semibold">
              Warning: this completely replaces all current users, admins and
              settings — only the backup's data remains.
            </Text>
          </Text>
          <HStack gap={3}>
            <input
              ref={fileInputRef}
              type="file"
              accept=".tar.gz,.tar"
              hidden
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            <Button size="sm" variant="outline" onClick={() => fileInputRef.current?.click()}>
              <FiUpload style={{ marginRight: 6 }} />
              {file ? file.name : "Choose Backup File"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              colorPalette="red"
              disabled={!file}
              onClick={() => setShowRestore(true)}
            >
              <FiDownload style={{ marginRight: 6 }} />
              Restore Panel
            </Button>
          </HStack>
        </Box>

        {/* Schedule */}
        <Box borderTop="1px solid" borderColor="bg.muted" pt={4}>
          <Heading size="xs" mb={2}>
            Scheduled Backups
          </Heading>
          <Text fontSize="sm" color="fg.muted" mb={3}>
            Run an automatic backup every day (UTC) and optionally deliver it to
            the configured Telegram chat alongside the notifications.
          </Text>
          {config && (
            <VStack align="stretch" gap={3}>
              <HStack gap={4}>
                <Switch.Root
                  checked={config.enabled}
                  onCheckedChange={(e) => saveConfig.mutate({ enabled: e.checked })}
                >
                  <Switch.Control>
                    <Switch.Thumb />
                  </Switch.Control>
                  <Switch.Label>Enable scheduled backups</Switch.Label>
                </Switch.Root>
                <Switch.Root
                  checked={config.send_to_telegram}
                  onCheckedChange={(e) => saveConfig.mutate({ send_to_telegram: e.checked })}
                >
                  <Switch.Control>
                    <Switch.Thumb />
                  </Switch.Control>
                  <Switch.Label>Send backups to Telegram</Switch.Label>
                </Switch.Root>
              </HStack>

              <HStack gap={4} alignItems="flex-end">
                <Field.Root>
                  <Field.Label>Hour (UTC)</Field.Label>
                  <Select.Root
                    width="100px"
                    value={[String(config.schedule_hour)]}
                    collection={hourCollection}
                    onValueChange={(d) => saveConfig.mutate({ schedule_hour: Number(d.value[0]) })}
                  >
                    <Select.Control>
                      <Select.Trigger>
                        <Select.ValueText />
                      </Select.Trigger>
                    </Select.Control>
                    <Portal>
                      <Select.Positioner>
                        <Select.Content maxH="200px">
                          {hourCollection.items.map((item) => (
                            <Select.Item key={item.value} item={item}>
                              <Select.ItemText>{item.label}</Select.ItemText>
                            </Select.Item>
                          ))}
                        </Select.Content>
                      </Select.Positioner>
                    </Portal>
                  </Select.Root>
                </Field.Root>

                <Field.Root>
                  <Field.Label>Minute</Field.Label>
                  <Select.Root
                    width="100px"
                    value={[String(config.schedule_minute)]}
                    collection={minuteCollection}
                    onValueChange={(d) => saveConfig.mutate({ schedule_minute: Number(d.value[0]) })}
                  >
                    <Select.Control>
                      <Select.Trigger>
                        <Select.ValueText />
                      </Select.Trigger>
                    </Select.Control>
                    <Portal>
                      <Select.Positioner>
                        <Select.Content maxH="200px">
                          {minuteCollection.items.map((item) => (
                            <Select.Item key={item.value} item={item}>
                              <Select.ItemText>{item.label}</Select.ItemText>
                            </Select.Item>
                          ))}
                        </Select.Content>
                      </Select.Positioner>
                    </Portal>
                  </Select.Root>
                </Field.Root>

                <Field.Root>
                  <Field.Label>Keep (0 = keep all)</Field.Label>
                  <Input
                    type="number"
                    width="110px"
                    defaultValue={config.keep_count}
                    onBlur={(e) => {
                      const v = Number(e.target.value);
                      if (!Number.isNaN(v) && v >= 0) saveConfig.mutate({ keep_count: v });
                    }}
                  />
                </Field.Root>
              </HStack>

              {config.last_backup_file && (
                <Text fontSize="xs" color="fg.muted">
                  Last scheduled backup: {config.last_backup_file}
                  {config.last_run_at ? ` — ${new Date(config.last_run_at).toLocaleString()}` : ""}
                </Text>
              )}
            </VStack>
          )}
        </Box>

        {/* Stored backups */}
        <Box borderTop="1px solid" borderColor="bg.muted" pt={4}>
          <Heading size="xs" mb={2}>
            Stored Backups
          </Heading>
          {loadingBackups && <Text fontSize="sm" color="fg.muted">Loading…</Text>}
          {!loadingBackups && backups && backups.length === 0 && (
            <Text fontSize="sm" color="fg.muted">No backups stored yet.</Text>
          )}
          <VStack align="stretch" gap={2}>
            {backups?.map((b) => (
              <HStack key={b.name} justify="space-between" p={2} borderRadius="md" bg="bg.muted">
                <VStack align="stretch" gap={0}>
                  <Text fontSize="sm" fontWeight="medium">{b.name}</Text>
                  <Text fontSize="xs" color="fg.muted">
                    {formatBytes(b.size_bytes)} · {new Date(b.created_at).toLocaleString()}
                  </Text>
                </VStack>
                <HStack>
                  <Button size="xs" variant="ghost" onClick={() => downloadBackup(b.name)}>
                    <FiDownload />
                    Download
                  </Button>
                  <Button
                    size="xs"
                    variant="ghost"
                    colorPalette="red"
                    loading={false}
                    onClick={() => deleteBackup.mutate(b.name)}
                  >
                    <FiTrash2 />
                    Delete
                  </Button>
                </HStack>
              </HStack>
            ))}
          </VStack>
        </Box>
      </VStack>

      <ConfirmDialog
        open={showRestore}
        onClose={() => setShowRestore(false)}
        title="Restore Panel from Backup?"
        confirmLabel="Restore Panel"
        confirmColorPalette="red"
        onConfirm={confirmRestore}
        body={
          <VStack align="stretch" gap={3}>
            <Text fontSize="sm">
              This will <strong>completely replace</strong> all current users, admins,
              settings and logs with the contents of{" "}
              <Text as="span" fontWeight="semibold">{file?.name}</Text>. If the backup
              contains VPN certificates, they will be re-imported and OpenVPN restarted.
            </Text>
            <Text fontSize="sm" color="fg.muted">
              You will need to sign in again afterwards. Continue?
            </Text>
          </VStack>
        }
      />
    </SectionCard>
  );
}

function TelegramSection() {
  const [sending, setSending] = useState(false);

  const handleTest = async () => {
    setSending(true);
    try {
      const { data } = await api.post("/settings/telegram/test");
      toaster.create({ title: data.detail, type: "success" });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to send test message";
      toaster.create({ title: msg, type: "error" });
    } finally {
      setSending(false);
    }
  };

  return (
    <SectionCard title="Telegram Notifications">
      <VStack align="stretch" gap={3}>
        <Text fontSize="sm" color="fg.muted">
          Telegram is configured via environment variables on the server. Use this section to test the connection.
        </Text>
        <HStack>
          <Button size="sm" onClick={handleTest} loading={sending} variant="outline">
            <FiSend style={{ marginRight: 6 }} />
            Send Test Message
          </Button>
        </HStack>
      </VStack>
    </SectionCard>
  );
}

function ServerConfigSection() {
  const { data: config, isLoading, error } = useQuery<ServerConfig>({
    queryKey: ["server-config"],
    queryFn: async () => {
      const { data } = await api.get("/settings/server-config");
      return data;
    },
  });

  if (isLoading) return <LoadingState />;
  if (error || !config) return <ErrorState message="Failed to load server config." />;

  // Keyed by updated_at so the form remounts (fresh state) after every apply.
  return <ServerConfigForm key={config.updated_at} config={config} />;
}

function ServerConfigForm({ config }: { config: ServerConfig }) {
  const queryClient = useQueryClient();
  const [showConfirm, setShowConfirm] = useState(false);
  const [pendingValues, setPendingValues] = useState<Record<string, unknown> | null>(null);
  const [localDns, setLocalDns] = useState<string[]>(config.dns_servers ?? []);

  const [protocol, setProtocol] = useState(config.protocol);
  const [cipher, setCipher] = useState(config.cipher);
  const [authDigest, setAuthDigest] = useState(config.auth_digest);
  const [tlsMode, setTlsMode] = useState(config.tls_mode);
  const [dnsPreset, setDnsPreset] = useState(config.dns_preset);
  const [clientToClient, setClientToClient] = useState(config.client_to_client);
  const [redirectGateway, setRedirectGateway] = useState(config.redirect_gateway);

  const applyMutation = useMutation({
    mutationFn: async (values: Record<string, unknown>) => {
      const { data } = await api.put<ApplyResult>("/settings/server-config", values);
      return data;
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["server-config"] });
      if (result.success) {
        toaster.create({
          title: result.message,
          type: result.requires_redownload ? "warning" : "success",
        });
      } else {
        toaster.create({ title: result.message, type: "error" });
      }
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to apply config";
      toaster.create({ title: msg, type: "error" });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const form = e.target as HTMLFormElement;
    const formData = new FormData(form);
    const values: Record<string, unknown> = {};

    values.protocol = protocol;
    values.port = Number(formData.get("port"));
    values.cipher = cipher;
    values.auth_digest = authDigest;
    values.tls_mode = tlsMode;
    values.dns_preset = dnsPreset;
    values.public_host = formData.get("public_host") as string;
    values.tunnel_host = formData.get("tunnel_host") as string;
    values.subscription_url_prefix = formData.get("subscription_url_prefix") as string;
    values.keepalive_interval = Number(formData.get("keepalive_interval"));
    values.keepalive_timeout = Number(formData.get("keepalive_timeout"));
    values.client_to_client = clientToClient;
    values.redirect_gateway = redirectGateway;

    const mtuVal = formData.get("mtu") as string;
    values.mtu = mtuVal ? Number(mtuVal) : null;

    if (dnsPreset === "custom") {
      values.dns_servers = localDns.filter((d) => d.trim());
    } else {
      values.dns_servers = DNS_SERVERS_MAP[dnsPreset] ?? null;
    }

    setPendingValues(values);
    setShowConfirm(true);
  };

  const confirmApply = () => {
    if (pendingValues) applyMutation.mutate(pendingValues);
    setShowConfirm(false);
    setPendingValues(null);
  };

  return (
    <>
      <SectionCard title="OpenVPN Server Configuration">
        <form onSubmit={handleSubmit}>
          <VStack align="stretch" gap={4}>
            <SimpleGrid columns={{ base: 1, md: 2 }} gap={4}>
              <Field.Root>
                <Field.Label>Protocol</Field.Label>
                <Select.Root
                  value={[protocol]}
                  onValueChange={(details) => setProtocol(details.value[0])}
                  collection={protocolCollection}
                >
                  <Select.Control>
                    <Select.Trigger>
                      <Select.ValueText />
                    </Select.Trigger>
                  </Select.Control>
                  <Portal>
                    <Select.Positioner>
                      <Select.Content>
                        {protocolCollection.items.map((item) => (
                          <Select.Item key={item.value} item={item}>
                            <Select.ItemText>{item.label}</Select.ItemText>
                          </Select.Item>
                        ))}
                      </Select.Content>
                    </Select.Positioner>
                  </Portal>
                </Select.Root>
              </Field.Root>

              <Field.Root>
                <Field.Label>Port</Field.Label>
                <Input name="port" type="number" defaultValue={config.port} />
              </Field.Root>

              <Field.Root>
                <Field.Label>Cipher</Field.Label>
                <Select.Root
                  value={[cipher]}
                  onValueChange={(details) => setCipher(details.value[0])}
                  collection={cipherCollection}
                >
                  <Select.Control>
                    <Select.Trigger>
                      <Select.ValueText />
                    </Select.Trigger>
                  </Select.Control>
                  <Portal>
                    <Select.Positioner>
                      <Select.Content>
                        {cipherCollection.items.map((item) => (
                          <Select.Item key={item.value} item={item}>
                            <Select.ItemText>{item.label}</Select.ItemText>
                          </Select.Item>
                        ))}
                      </Select.Content>
                    </Select.Positioner>
                  </Portal>
                </Select.Root>
              </Field.Root>

              <Field.Root>
                <Field.Label>Auth Digest</Field.Label>
                <Select.Root
                  value={[authDigest]}
                  onValueChange={(details) => setAuthDigest(details.value[0])}
                  collection={authCollection}
                >
                  <Select.Control>
                    <Select.Trigger>
                      <Select.ValueText />
                    </Select.Trigger>
                  </Select.Control>
                  <Portal>
                    <Select.Positioner>
                      <Select.Content>
                        {authCollection.items.map((item) => (
                          <Select.Item key={item.value} item={item}>
                            <Select.ItemText>{item.label}</Select.ItemText>
                          </Select.Item>
                        ))}
                      </Select.Content>
                    </Select.Positioner>
                  </Portal>
                </Select.Root>
              </Field.Root>

              <Field.Root>
                <Field.Label>TLS Mode</Field.Label>
                <Select.Root
                  value={[tlsMode]}
                  onValueChange={(details) => setTlsMode(details.value[0])}
                  collection={tlsCollection}
                >
                  <Select.Control>
                    <Select.Trigger>
                      <Select.ValueText />
                    </Select.Trigger>
                  </Select.Control>
                  <Portal>
                    <Select.Positioner>
                      <Select.Content>
                        {tlsCollection.items.map((item) => (
                          <Select.Item key={item.value} item={item}>
                            <Select.ItemText>{item.label}</Select.ItemText>
                          </Select.Item>
                        ))}
                      </Select.Content>
                    </Select.Positioner>
                  </Portal>
                </Select.Root>
              </Field.Root>

              <Field.Root>
                <Field.Label>DNS Preset</Field.Label>
                <Select.Root
                  value={[dnsPreset]}
                  collection={dnsCollection}
                  onValueChange={(details) => {
                    const val = details.value[0];
                    setDnsPreset(val);
                    if (val === "custom") {
                      setLocalDns(config.dns_servers ?? ["", ""]);
                    } else {
                      setLocalDns([]);
                    }
                  }}
                >
                  <Select.Control>
                    <Select.Trigger>
                      <Select.ValueText />
                    </Select.Trigger>
                  </Select.Control>
                  <Portal>
                    <Select.Positioner>
                      <Select.Content>
                        {dnsCollection.items.map((item) => (
                          <Select.Item key={item.value} item={item}>
                            <Select.ItemText>{item.label}</Select.ItemText>
                          </Select.Item>
                        ))}
                      </Select.Content>
                    </Select.Positioner>
                  </Portal>
                </Select.Root>
              </Field.Root>

              <Field.Root>
                <Field.Label>MTU (optional)</Field.Label>
                <Input name="mtu" type="number" defaultValue={config.mtu ?? ""} placeholder="1500" />
              </Field.Root>

              <Field.Root>
                <Field.Label>Public Host / Domain</Field.Label>
                <Input name="public_host" defaultValue={config.public_host} placeholder="vpn.example.com" />
              </Field.Root>

              <Field.Root>
                <Field.Label>Tunnel Address (optional)</Field.Label>
                <Input name="tunnel_host" defaultValue={config.tunnel_host} placeholder="tunnel.example.com" />
                <Field.HelperText>
                  When set, generated .ovpn configs use this address as the{" "}
                  <Text as="span" fontWeight="semibold">
                    remote
                  </Text>{" "}
                  endpoint instead of the Public Host. It forwards the OpenVPN port back to this
                  server — nothing needs to be installed on the tunnel itself.
                </Field.HelperText>
              </Field.Root>

              <Field.Root>
                <Field.Label>Keepalive Interval</Field.Label>
                <Input name="keepalive_interval" type="number" defaultValue={config.keepalive_interval} />
              </Field.Root>

              <Field.Root>
                <Field.Label>Keepalive Timeout</Field.Label>
                <Input name="keepalive_timeout" type="number" defaultValue={config.keepalive_timeout} />
              </Field.Root>
            </SimpleGrid>

            {dnsPreset === "custom" && (
              <VStack align="stretch" gap={2}>
                <Field.Label>Custom DNS Servers</Field.Label>
                {(localDns.length > 0 ? localDns : ["", ""]).map((dns, i) => (
                  <Input
                    key={i}
                    placeholder={`DNS server ${i + 1}`}
                    value={dns}
                    onChange={(e) => {
                      const updated = [...localDns];
                      updated[i] = e.target.value;
                      setLocalDns(updated);
                    }}
                  />
                ))}
                <Button
                  size="xs"
                  variant="ghost"
                  alignSelf="flex-start"
                  onClick={() => setLocalDns([...localDns, ""])}
                >
                  + Add DNS
                </Button>
              </VStack>
            )}

            <HStack gap={6}>
              <Switch.Root
                checked={clientToClient}
                onCheckedChange={(e) => setClientToClient(e.checked)}
              >
                <Switch.Control>
                  <Switch.Thumb />
                </Switch.Control>
                <Switch.Label>Client-to-Client</Switch.Label>
              </Switch.Root>

              <Switch.Root
                checked={redirectGateway}
                onCheckedChange={(e) => setRedirectGateway(e.checked)}
              >
                <Switch.Control>
                  <Switch.Thumb />
                </Switch.Control>
                <Switch.Label>Redirect All Traffic</Switch.Label>
              </Switch.Root>
            </HStack>

            <Field.Root>
              <Field.Label>Subscription URL Prefix</Field.Label>
              <Input
                name="subscription_url_prefix"
                defaultValue={config.subscription_url_prefix}
                placeholder="https://panel.example.com"
              />
              <Field.HelperText>
                Base URL used to build each user's subscription link (e.g.{" "}
                <Text as="span" fontWeight="semibold">
                  {"{prefix}/sub/{token}"}
                </Text>
                ). Clients use this link to auto-download their .ovpn config.
              </Field.HelperText>
            </Field.Root>

            <Button type="submit" alignSelf="flex-start" loading={applyMutation.isPending}>
              Save & Apply Configuration
            </Button>
          </VStack>
        </form>
      </SectionCard>

      <ConfirmDialog
        open={showConfirm}
        onClose={() => {
          setShowConfirm(false);
          setPendingValues(null);
        }}
        title="Apply Server Configuration?"
        confirmLabel="Apply & Restart"
        confirmColorPalette="red"
        onConfirm={confirmApply}
        isLoading={applyMutation.isPending}
        body={
          <VStack align="stretch" gap={3}>
            <Text fontSize="sm">
              This will restart your OpenVPN server and may require existing clients to
              redownload their config file. Continue?
            </Text>
            {pendingValues && (
              <Box bg="bg.muted" p={3} borderRadius="md" fontSize="xs" color="fg.muted">
                Changes will be applied to: protocol, port, cipher, auth, TLS, DNS, keepalive,
                and other modified fields.
              </Box>
            )}
          </VStack>
        }
      />
    </>
  );
}

function ChangePasswordSection() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      toaster.create({ title: "Passwords do not match", type: "error" });
      return;
    }
    if (newPassword.length < 6) {
      toaster.create({ title: "Password must be at least 6 characters", type: "error" });
      return;
    }
    setLoading(true);
    try {
      await api.put("/admin/me/password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      toaster.create({ title: "Password updated successfully", type: "success" });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to update password";
      toaster.create({ title: msg, type: "error" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <SectionCard title="Change Password">
      <Box as="form" onSubmit={handleSubmit}>
        <VStack align="stretch" gap={3} maxW="400px">
          <Field.Root required>
            <Field.Label>Current Password</Field.Label>
            <Input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              autoComplete="current-password"
            />
          </Field.Root>
          <Field.Root required>
            <Field.Label>New Password</Field.Label>
            <Input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete="new-password"
            />
          </Field.Root>
          <Field.Root required>
            <Field.Label>Confirm New Password</Field.Label>
            <Input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
            />
          </Field.Root>
          <Button type="submit" loading={loading} alignSelf="flex-start" variant="outline">
            <FiKey style={{ marginRight: 6 }} />
            Update Password
          </Button>
        </VStack>
      </Box>
    </SectionCard>
  );
}

export default function Settings() {
  const { admin } = useAuth();
  const isSudo = admin?.is_sudo;

  return (
    <VStack align="stretch" gap={6}>
      <Tabs.Root defaultValue={isSudo ? "server" : "account"} variant="line">
        <Tabs.List>
          <Tabs.Trigger value="account">
            <FiLock />
            Account
          </Tabs.Trigger>
          {isSudo && (
            <Tabs.Trigger value="server">
              <FiServer />
              Server
            </Tabs.Trigger>
          )}
          {isSudo && (
            <Tabs.Trigger value="telegram">
              <FiSend />
              Telegram
            </Tabs.Trigger>
          )}
          {isSudo && (
            <Tabs.Trigger value="backup">
              <FiArchive />
              Backup
            </Tabs.Trigger>
          )}
          <Tabs.Indicator />
        </Tabs.List>

        <Tabs.Content value="account">
          <ChangePasswordSection />
        </Tabs.Content>

        {isSudo && (
          <Tabs.Content value="server">
            <ServerConfigSection />
          </Tabs.Content>
        )}
        {isSudo && (
          <Tabs.Content value="telegram">
            <TelegramSection />
          </Tabs.Content>
        )}
        {isSudo && (
          <Tabs.Content value="backup">
            <BackupSection />
          </Tabs.Content>
        )}
      </Tabs.Root>
    </VStack>
  );
}
