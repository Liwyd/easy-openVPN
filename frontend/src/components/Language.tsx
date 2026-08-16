import { Button, Menu, Portal, Icon } from "@chakra-ui/react";
import { FiGlobe } from "react-icons/fi";
import { useTranslation } from "react-i18next";

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
          size="sm"
          aria-label={t("header.language")}
          title={t("header.language")}
        >
          <Icon as={FiGlobe} boxSize="4" />
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
