import { Dialog, Portal, Text, Button, VStack, HStack, Code } from "@chakra-ui/react";
import { QRCodeSVG } from "qrcode.react";
import { FiCopy, FiCheck } from "react-icons/fi";
import { useState, useEffect } from "react";
import api from "../lib/api";
import { toaster } from "../lib/toaster";
import { buttonOutline } from "../theme-components";
import { useUserContext } from "../contexts/UserContext";

export default function QRCodeDialog() {
  const { qrUser, closeQR } = useUserContext();
  const [link, setLink] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const username = qrUser?.user.username;
  const source = qrUser?.source;

  useEffect(() => {
    if (!username || !source) return;
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
        if (!cancelled) toaster.create({ title: "Failed to load QR code", type: "error" });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [username, source]);

  async function handleCopy() {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toaster.create({ title: "Failed to copy link", type: "error" });
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
              <Dialog.Title>QR Code</Dialog.Title>
            </Dialog.Header>
            <Dialog.Body>
              <VStack gap={4}>
                {loading ? (
                  <Text color="fg.muted">Loading...</Text>
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
                      Scan with an OpenVPN client app to import the
                      subscription for <strong>{username}</strong>.
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
                  Close
                </Button>
                <Button css={buttonOutline} onClick={handleCopy} disabled={!link}>
                  {copied ? <FiCheck /> : <FiCopy />}
                  {copied ? "Copied" : "Copy Link"}
                </Button>
              </HStack>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  );
}
