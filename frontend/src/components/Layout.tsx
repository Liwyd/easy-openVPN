import { Box, Flex } from "@chakra-ui/react";
import { Outlet } from "react-router-dom";
import Header from "./Header";
import Footer from "./Footer";

export default function Layout() {
  return (
    <Flex minH="100vh" flexDir="column">
      <Header />
      <Box flex="1" p={6} bg="bg">
        <Outlet />
      </Box>
      <Footer />
    </Flex>
  );
}
