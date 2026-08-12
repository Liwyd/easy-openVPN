import { Dialog, Portal, Text, Button, VStack, HStack, Code } from "@chakra-ui/react";
import { QRCodeSVG } from "qrcode.react";
import { FiCopy, FiCheck } from "react-icons/fi";
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import api from "../lib/api";
import { toaster } from "../lib/toaster";
import { copyToClipboard } from "../utils/copyToClipboard";
import { buttonOutline } from "../theme-components";
import { useUserContext } from "../contexts/UserContext";

export default function QRCodeDialog() {
  const { t } = useTranslation();
  const { qrUser, closeQR } = useUserContext();
  const [link, setLink] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const username = qrUser?.username;

  useEffect(() => {
    if (!username) return;
    let cancelled = false;
    setLoading(true);
    setCopied(false);
    setLink("");
    api
      .get(`/users/${username}/subscription-url`)
      .then(({ data }) => {
        if (!cancelled) setLink(data.subscription_url as string);
      })
      .catch(() => {
        if (!cancelled) toaster.create({ title: t("qrCode.failedToLoad"), type: "error" });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [username]);

  async function handleCopy() {
    if (!link) return;
    try {
      await copyToClipboard(link);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toaster.create({ title: t("qrCode.failedToCopy"), type: "error" });
    }
  }

  return (
    <Dialog.Root
      open={!!qrUser}
      onOpenChange={(e) => {
        if (!e.open) closeQR();
      }}
    >
      <Portal>
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content maxW="sm">
            <Dialog.Header>
              <Dialog.Title>{t("qrCode.title")}</Dialog.Title>
            </Dialog.Header>
            <Dialog.Body>
              <VStack gap={4}>
                {loading ? (
                  <Text color="fg.muted">{t("qrCode.loading")}</Text>
                ) : (
                  <>
                    <VStack
                      p={4}
                      border="1px solid"
                      borderColor="border.strong"
                      borderRadius="lg"
                      bg="white"
                    >
                      <QRCodeSVG value={link || username || ""} size={180} />
                    </VStack>
                    <Text fontSize="sm" color="fg.muted" textAlign="center">
                      {t("qrCode.scanPrompt", { username })}
                    </Text>
                    <Code fontSize="xs" maxW="100%" wordBreak="break-all">
                      {link || "\u2014"}
                    </Code>
                  </>
                )}
              </VStack>
            </Dialog.Body>
            <Dialog.Footer>
              <HStack gap={2} w="100%" justify="flex-end">
                <Button variant="outline" css={buttonOutline} onClick={closeQR}>
                  {t("qrCode.close")}
                </Button>
                <Button css={buttonOutline} onClick={handleCopy} disabled={!link}>
                  {copied ? <FiCheck /> : <FiCopy />}
                  {copied ? t("qrCode.copied") : t("qrCode.copyLink")}
                </Button>
              </HStack>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  );
}
