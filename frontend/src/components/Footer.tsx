import { Flex, Link, Text } from "@chakra-ui/react";
import { useTranslation } from "react-i18next";

const REPO_URL = "https://github.com/M0r3z/eovpanel";

export default function Footer() {
  const { t } = useTranslation();
  return (
    <Flex w="full" py="4" px={6} justify="center">
      <Text display="inline-block" textAlign="center" color="fg.muted" fontSize="xs">
        <Link color="accent" href={REPO_URL}>
          eovpanel
        </Link>
        , {t("footer.made")}
      </Text>
    </Flex>
  );
}