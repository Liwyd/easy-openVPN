import {
  Dialog,
  Portal,
  Text,
  Button,
  VStack,
  HStack,
} from "@chakra-ui/react";
import { buttonOutline } from "../theme-components";

interface ConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  body: React.ReactNode;
  confirmLabel?: string;
  confirmColorPalette?: string;
  onConfirm: () => void;
  isLoading?: boolean;
}

export default function ConfirmDialog({
  open,
  onClose,
  title,
  body,
  confirmLabel = "Confirm",
  confirmColorPalette = "accent",
  onConfirm,
  isLoading,
}: ConfirmDialogProps) {
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(e) => {
        if (!e.open) onClose();
      }}
    >
      <Portal>
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content maxW="sm">
            <Dialog.Header>
              <Dialog.Title>{title}</Dialog.Title>
            </Dialog.Header>
            <Dialog.Body>
              <VStack align="stretch" gap={3}>
                {typeof body === "string" ? <Text>{body}</Text> : body}
              </VStack>
            </Dialog.Body>
            <Dialog.Footer>
              <HStack gap={2} justify="flex-end">
                <Button variant="outline" css={buttonOutline} onClick={onClose}>
                  Cancel
                </Button>
                <Button
                  colorPalette={confirmColorPalette}
                  loading={isLoading}
                  onClick={() => {
                    onConfirm();
                  }}
                >
                  {confirmLabel}
                </Button>
              </HStack>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  );
}
