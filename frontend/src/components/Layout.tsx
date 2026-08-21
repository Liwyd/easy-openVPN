import { Box, VStack } from "@chakra-ui/react";
import { Outlet } from "react-router-dom";
import Header from "./Header";

export default function Layout() {
  return (
    <VStack justifyContent="flex-start" minH="100vh" p={{ base: 4, md: 6 }} rowGap={0} align="stretch">
      <Box w="full" flex="1">
        <Header />
        <Outlet />
      </Box>
    </VStack>
  );
}
