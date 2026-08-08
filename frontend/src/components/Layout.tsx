import { Box, Flex } from "@chakra-ui/react";
import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

export default function Layout() {
  return (
    <Flex h="100vh" overflow="hidden">
      <Sidebar />
      <Flex flexDir="column" flex="1" minW="0">
        <Topbar />
        <Box flex="1" overflowY="auto" p={6} bg="bg.subtle">
          <Outlet />
        </Box>
      </Flex>
    </Flex>
  );
}
