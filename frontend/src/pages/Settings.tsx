import { useRef, useState, useEffect } from "react";
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
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
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
      toaster.create({ title: t("settings.backupScheduleSaved"), type: "success" });
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || t("settings.backupScheduleSaveFailed");
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
        title: sendToTelegram ? t("settings.backupCreatedAndSent") : t("settings.backupCreated"),
        type: "success",
      });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || t("settings.backupCreateFailed");
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
      toaster.create({ title: t("settings.backupDownloadFailed"), type: "error" });
    }
  };

  const deleteBackup = useMutation({
    mutationFn: async (name: string) => {
      await api.delete(`/backup/${name}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["backup-list"] });
      toaster.create({ title: t("settings.backupDeleted"), type: "success" });
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
        title: t("settings.panelRestored"),
        type: "success",
      });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || t("settings.restoreFailed");
      toaster.create({ title: msg, type: "error" });
    } finally {
      setFile(null);
    }
  };

  return (
    <SectionCard title={t("settings.backupTitle")}>
      <VStack align="stretch" gap={5}>
        {/* Create */}
        <Box>
          <Text fontSize="sm" color="fg.muted" mb={2}>
            {t("settings.backupIntro")}
          </Text>
          <HStack>
            <Button size="sm" onClick={createBackup} loading={creating} colorPalette="accent">
              <FiArchive style={{ marginRight: 6 }} />
              {t("settings.createBackupNow")}
            </Button>
            <Switch.Root checked={sendToTelegram} onCheckedChange={(e) => setSendToTelegram(e.checked)}>
              <Switch.HiddenInput />
              <Switch.Control>
                <Switch.Thumb />
              </Switch.Control>
              <Switch.Label>{t("settings.alsoSendToTelegram")}</Switch.Label>
            </Switch.Root>
          </HStack>
          {lastBackup && (
            <Text fontSize="xs" color="fg.muted" mt={2}>
              {lastBackup.size_bytes
                ? t("settings.createdFileSize", { filename: lastBackup.filename, size: formatBytes(lastBackup.size_bytes) })
                : t("settings.createdFile", { filename: lastBackup.filename })}
              <Text as="span" textDecoration="underline" cursor="pointer" onClick={() => downloadBackup(lastBackup.filename)}>
                {t("settings.download")}
              </Text>
            </Text>
          )}
        </Box>

        {/* Restore */}
        <Box>
          <Text fontSize="sm" color="fg.muted" mb={2}>
            {t("settings.restoreIntro")}
            <Text as="span" color="red.400" fontWeight="semibold">
              {t("settings.restoreWarning")}
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
              {file ? file.name : t("settings.chooseBackupFile")}
            </Button>
            <Button
              size="sm"
              variant="outline"
              colorPalette="red"
              disabled={!file}
              onClick={() => setShowRestore(true)}
            >
              <FiDownload style={{ marginRight: 6 }} />
              {t("settings.restorePanel")}
            </Button>
          </HStack>
        </Box>

        {/* Schedule */}
        <Box borderTop="1px solid" borderColor="bg.muted" pt={4}>
          <Heading size="xs" mb={2}>
            {t("settings.scheduledBackups")}
          </Heading>
          <Text fontSize="sm" color="fg.muted" mb={3}>
            {t("settings.scheduleIntro")}
          </Text>
          {config && (
            <VStack align="stretch" gap={3}>
              <HStack gap={4}>
                <Switch.Root
                  checked={config.enabled}
                  onCheckedChange={(e) => saveConfig.mutate({ enabled: e.checked })}
                >
                  <Switch.HiddenInput />
                  <Switch.Control>
                    <Switch.Thumb />
                  </Switch.Control>
                  <Switch.Label>{t("settings.enableScheduled")}</Switch.Label>
                </Switch.Root>
                <Switch.Root
                  checked={config.send_to_telegram}
                  onCheckedChange={(e) => saveConfig.mutate({ send_to_telegram: e.checked })}
                >
                  <Switch.HiddenInput />
                  <Switch.Control>
                    <Switch.Thumb />
                  </Switch.Control>
                  <Switch.Label>{t("settings.sendBackupsToTelegram")}</Switch.Label>
                </Switch.Root>
              </HStack>

              <HStack gap={4} alignItems="flex-end">
                <Field.Root>
                  <Field.Label>{t("settings.hourUtc")}</Field.Label>
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
                  <Field.Label>{t("settings.minute")}</Field.Label>
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
                  <Field.Label>{t("settings.keep")}</Field.Label>
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
                  {t("settings.lastScheduledBackup", { file: config.last_backup_file })}
                  {config.last_run_at ? ` — ${new Date(config.last_run_at).toLocaleString()}` : ""}
                </Text>
              )}
            </VStack>
          )}
        </Box>

        {/* Stored backups */}
        <Box borderTop="1px solid" borderColor="bg.muted" pt={4}>
          <Heading size="xs" mb={2}>
            {t("settings.storedBackups")}
          </Heading>
          {loadingBackups && <Text fontSize="sm" color="fg.muted">{t("settings.loading")}</Text>}
          {!loadingBackups && backups && backups.length === 0 && (
            <Text fontSize="sm" color="fg.muted">{t("settings.noBackupsStored")}</Text>
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
                    {t("settings.download")}
                  </Button>
                  <Button
                    size="xs"
                    variant="ghost"
                    colorPalette="red"
                    loading={false}
                    onClick={() => deleteBackup.mutate(b.name)}
                  >
                    <FiTrash2 />
                    {t("settings.delete")}
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
        title={t("settings.restoreConfirmTitle")}
        confirmLabel={t("settings.restorePanel")}
        confirmColorPalette="red"
        onConfirm={confirmRestore}
        body={
          <VStack align="stretch" gap={3}>
            <Text fontSize="sm">
              {t("settings.restoreConfirmPrompt", { filename: file?.name })}
            </Text>
            <Text fontSize="sm" color="fg.muted">
              {t("settings.restoreSignIn")}
            </Text>
          </VStack>
        }
      />
    </SectionCard>
  );
}

function TelegramSection() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [sending, setSending] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [botToken, setBotToken] = useState("");
  const [chatIds, setChatIds] = useState("");

  const { data } = useQuery<{
    enabled: boolean;
    bot_token: string;
    admin_chat_ids: string[];
  }>({
    queryKey: ["telegram-settings"],
    queryFn: async () => (await api.get("/settings/telegram")).data,
  });

  useEffect(() => {
    if (!data) return;
    setEnabled(!!data.enabled);
    setBotToken(data.bot_token ?? "");
    setChatIds((data.admin_chat_ids ?? []).join(", "));
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const { data: saved } = await api.put("/settings/telegram", {
        enabled,
        bot_token: botToken.trim(),
        admin_chat_ids: chatIds
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      });
      return saved;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["telegram-settings"] });
      toaster.create({ title: t("settings.telegramSaved"), type: "success" });
    },
    onError: () => {
      toaster.create({ title: t("settings.telegramSaveFailed"), type: "error" });
    },
  });

  const handleTest = async () => {
    setSending(true);
    try {
      const { data } = await api.post("/settings/telegram/test");
      toaster.create({ title: data.detail, type: "success" });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || t("settings.testFailed");
      toaster.create({ title: msg, type: "error" });
    } finally {
      setSending(false);
    }
  };

  return (
    <SectionCard title={t("settings.telegramTitle")}>
      <VStack align="stretch" gap={3}>
        <Text fontSize="sm" color="fg.muted">
          {t("settings.telegramHelp")}
        </Text>
        <Field.Root>
          <Field.Label>{t("settings.telegramEnabled")}</Field.Label>
          <Switch.Root checked={enabled} onCheckedChange={(e) => setEnabled(e.checked)}>
            <Switch.HiddenInput />
            <Switch.Control />
            <Switch.Thumb />
            <Switch.Label>
              {enabled ? t("status.active") : t("status.disabled")}
            </Switch.Label>
          </Switch.Root>
        </Field.Root>
        <Field.Root>
          <Field.Label>{t("settings.botToken")}</Field.Label>
          <Input
            value={botToken}
            onChange={(e) => setBotToken(e.target.value)}
            dir="ltr"
            placeholder="1234567890:AA..."
          />
          <Field.HelperText>{t("settings.botTokenHelp")}</Field.HelperText>
        </Field.Root>
        <Field.Root>
          <Field.Label>{t("settings.adminChatIds")}</Field.Label>
          <Input
            value={chatIds}
            onChange={(e) => setChatIds(e.target.value)}
            dir="ltr"
            placeholder={t("settings.adminChatIdsPlaceholder")}
          />
          <Field.HelperText>{t("settings.adminChatIdsHelp")}</Field.HelperText>
        </Field.Root>
        <HStack>
          <Button size="sm" onClick={handleTest} loading={sending} variant="outline">
            <FiSend style={{ marginRight: 6 }} />
            {t("settings.sendTestMessage")}
          </Button>
          <Button size="sm" onClick={() => saveMutation.mutate()} loading={saveMutation.isPending}>
            {t("settings.saveTelegram")}
          </Button>
        </HStack>
      </VStack>
    </SectionCard>
  );
}

function ServerConfigSection() {
  const { t } = useTranslation();
  const { data: config, isLoading, error } = useQuery<ServerConfig>({
    queryKey: ["server-config"],
    queryFn: async () => {
      const { data } = await api.get("/settings/server-config");
      return data;
    },
  });

  if (isLoading) return <LoadingState />;
  if (error || !config) return <ErrorState message={t("settings.failedToLoadServerConfig")} />;

  // Keyed by updated_at so the form remounts (fresh state) after every apply.
  return <ServerConfigForm key={config.updated_at} config={config} />;
}

function ServerConfigForm({ config }: { config: ServerConfig }) {
  const { t } = useTranslation();
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
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || t("settings.failedToApply");
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
      <SectionCard title={t("settings.serverConfigTitle")}>
        <form onSubmit={handleSubmit}>
          <VStack align="stretch" gap={4}>
            <SimpleGrid columns={{ base: 1, md: 2 }} gap={4}>
              <Field.Root>
                <Field.Label>{t("settings.protocol")}</Field.Label>
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
                <Field.Label>{t("settings.port")}</Field.Label>
                <Input name="port" type="number" defaultValue={config.port} />
              </Field.Root>

              <Field.Root>
                <Field.Label>{t("settings.cipher")}</Field.Label>
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
                <Field.Label>{t("settings.authDigest")}</Field.Label>
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
                <Field.Label>{t("settings.tlsMode")}</Field.Label>
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
                <Field.Label>{t("settings.dnsPreset")}</Field.Label>
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
                <Field.Label>{t("settings.mtu")}</Field.Label>
                <Input name="mtu" type="number" defaultValue={config.mtu ?? ""} placeholder={t("settings.mtuPlaceholder")} />
              </Field.Root>

              <Field.Root>
                <Field.Label>{t("settings.publicHost")}</Field.Label>
                <Input name="public_host" defaultValue={config.public_host} placeholder={t("settings.publicHostPlaceholder")} />
              </Field.Root>

              <Field.Root>
                <Field.Label>{t("settings.tunnelAddress")}</Field.Label>
                <Input name="tunnel_host" defaultValue={config.tunnel_host} placeholder={t("settings.tunnelAddressPlaceholder")} />
                <Field.HelperText>
                  {t("settings.tunnelHelp")}
                </Field.HelperText>
              </Field.Root>

              <Field.Root>
                <Field.Label>{t("settings.keepaliveInterval")}</Field.Label>
                <Input name="keepalive_interval" type="number" defaultValue={config.keepalive_interval} />
              </Field.Root>

              <Field.Root>
                <Field.Label>{t("settings.keepaliveTimeout")}</Field.Label>
                <Input name="keepalive_timeout" type="number" defaultValue={config.keepalive_timeout} />
              </Field.Root>
            </SimpleGrid>

            {dnsPreset === "custom" && (
              <VStack align="stretch" gap={2}>
                <Field.Label>{t("settings.customDnsServers")}</Field.Label>
                {(localDns.length > 0 ? localDns : ["", ""]).map((dns, i) => (
                  <Input
                    key={i}
                    placeholder={t("settings.dnsServerPlaceholder", { index: i + 1 })}
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
                  {t("settings.addDns")}
                </Button>
              </VStack>
            )}

            <HStack gap={6}>
              <Switch.Root
                checked={clientToClient}
                onCheckedChange={(e) => setClientToClient(e.checked)}
              >
                <Switch.HiddenInput />
                <Switch.Control>
                  <Switch.Thumb />
                </Switch.Control>
                <Switch.Label>{t("settings.clientToClient")}</Switch.Label>
              </Switch.Root>

              <Switch.Root
                checked={redirectGateway}
                onCheckedChange={(e) => setRedirectGateway(e.checked)}
              >
                <Switch.HiddenInput />
                <Switch.Control>
                  <Switch.Thumb />
                </Switch.Control>
                <Switch.Label>{t("settings.redirectAllTraffic")}</Switch.Label>
              </Switch.Root>
            </HStack>

            <Field.Root>
              <Field.Label>{t("settings.subscriptionUrlPrefix")}</Field.Label>
              <Input
                name="subscription_url_prefix"
                defaultValue={config.subscription_url_prefix}
                placeholder={t("settings.subscriptionUrlPrefixPlaceholder")}
              />
              <Field.HelperText>
                {t("settings.subscriptionUrlHelp")}
              </Field.HelperText>
            </Field.Root>

            <Button type="submit" alignSelf="flex-start" loading={applyMutation.isPending}>
              {t("settings.saveAndApply")}
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
        title={t("settings.applyTitle")}
        confirmLabel={t("settings.applyRestart")}
        confirmColorPalette="red"
        onConfirm={confirmApply}
        isLoading={applyMutation.isPending}
        body={
          <VStack align="stretch" gap={3}>
            <Text fontSize="sm">
              {t("settings.applyPrompt")}
            </Text>
            {pendingValues && (
              <Box bg="bg.muted" p={3} borderRadius="md" fontSize="xs" color="fg.muted">
                {t("settings.applyChanges")}
              </Box>
            )}
          </VStack>
        }
      />
    </>
  );
}

function ChangePasswordSection() {
  const { t } = useTranslation();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      toaster.create({ title: t("settings.passwordsDoNotMatch"), type: "error" });
      return;
    }
    if (newPassword.length < 6) {
      toaster.create({ title: t("settings.passwordMin"), type: "error" });
      return;
    }
    setLoading(true);
    try {
      await api.put("/admin/me/password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      toaster.create({ title: t("settings.passwordUpdated"), type: "success" });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || t("settings.passwordFailed");
      toaster.create({ title: msg, type: "error" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <SectionCard title={t("settings.changePassword")}>
      <Box as="form" onSubmit={handleSubmit}>
        <VStack align="stretch" gap={3} maxW="400px">
          <Field.Root required>
            <Field.Label>{t("settings.currentPassword")}</Field.Label>
            <Input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              autoComplete="current-password"
            />
          </Field.Root>
          <Field.Root required>
            <Field.Label>{t("settings.newPassword")}</Field.Label>
            <Input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete="new-password"
            />
          </Field.Root>
          <Field.Root required>
            <Field.Label>{t("settings.confirmNewPassword")}</Field.Label>
            <Input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
            />
          </Field.Root>
          <Button type="submit" loading={loading} alignSelf="flex-start" variant="outline">
            <FiKey style={{ marginRight: 6 }} />
            {t("settings.updatePassword")}
          </Button>
        </VStack>
      </Box>
    </SectionCard>
  );
}

export default function Settings() {
  const { t } = useTranslation();
  const { admin } = useAuth();
  const isSudo = admin?.is_sudo;

  return (
    <VStack align="stretch" gap={6}>
      <Tabs.Root defaultValue={isSudo ? "server" : "account"} variant="line">
        <Tabs.List>
          <Tabs.Trigger value="account">
            <FiLock />
            {t("settings.account")}
          </Tabs.Trigger>
          {isSudo && (
            <Tabs.Trigger value="server">
              <FiServer />
              {t("settings.server")}
            </Tabs.Trigger>
          )}
          {isSudo && (
            <Tabs.Trigger value="telegram">
              <FiSend />
              {t("settings.telegram")}
            </Tabs.Trigger>
          )}
          {isSudo && (
            <Tabs.Trigger value="backup">
              <FiArchive />
              {t("settings.backup")}
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
