import { Flex, Link, Text } from "@chakra-ui/react";

const REPO_URL = "https://github.com/M0r3z/eovpanel";

export default function Footer() {
  return (
    <Flex w="full" py="4" px={6} justify="center">
      <Text display="inline-block" textAlign="center" color="fg.muted" fontSize="xs">
        <Link color="accent" href={REPO_URL}>
          eovpanel
        </Link>
        , Made with ❤️ for OpenVPN admins
      </Text>
    </Flex>
  );
}
