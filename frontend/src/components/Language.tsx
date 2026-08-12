import { Button, Menu, Portal } from "@chakra-ui/react";
import { useTranslation } from "react-i18next";

function LanguageIcon({ size = 16 }: { size?: number }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
      width={size}
      height={size}
      aria-hidden
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M10.5 21l5.25-11.25L21 21m-9-3h7.5M3 5.621a48.474 48.474 0 016-.371m0 0c1.12 0 2.25.038 3.375.112M9 5.25c-1.12 0-2.25.038-3.375.112m3.375-.112c.857-1.08 1.75-2.127 2.625-3.142m-6 .731a48.501 48.501 0 00-6.27 4.187M15 5.25c.857-1.08 1.75-2.127 2.625-3.142m-6 .731a48.501 48.501 0 006.27 4.187M21 5.621a48.474 48.474 0 00-6-.371c-.857 0-1.714.037-2.571.112"
      />
    </svg>
  );
}

export function Language() {
  const { i18n, t } = useTranslation();

  const changeLanguage = (lang: string) => {
    i18n.changeLanguage(lang);
  };

  return (
    <Menu.Root positioning={{ placement: "bottom-end" }}>
      <Menu.Trigger asChild>
        <Button
          variant="outline"
          size="xs"
          aria-label={t("header.language")}
          title={t("header.language")}
        >
          <LanguageIcon size={16} />
        </Button>
      </Menu.Trigger>
      <Portal>
        <Menu.Positioner>
          <Menu.Content minW="100px" zIndex={9999}>
            <Menu.Item value="en" onClick={() => changeLanguage("en")}>
              English
            </Menu.Item>
            <Menu.Item value="fa" onClick={() => changeLanguage("fa")}>
              فارسی
            </Menu.Item>
          </Menu.Content>
        </Menu.Positioner>
      </Portal>
    </Menu.Root>
  );
}
