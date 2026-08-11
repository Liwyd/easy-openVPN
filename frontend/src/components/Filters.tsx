import { Flex, Input, Box, IconButton, Button } from "@chakra-ui/react";
import { FiSearch, FiRefreshCw, FiPlus } from "react-icons/fi";
import { buttonSolid, buttonOutline } from "../theme-components";
import { useUserContext } from "../contexts/UserContext";

interface FiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  onRefresh: () => void;
  isRefreshing: boolean;
}

export default function Filters({
  search,
  onSearchChange,
  onRefresh,
  isRefreshing,
}: FiltersProps) {
  const { openCreate } = useUserContext();

  return (
    <Flex
      position="sticky"
      top="0"
      zIndex="1"
      bg="bg"
      py={3}
      gap={3}
      wrap="wrap"
      align="center"
    >
      <Box position="relative" flex="1" maxW="320px" minW="200px">
        <Input
          placeholder="Search by username..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          pe="36px"
          data-testid="users-search"
        />
        <Box
          position="absolute"
          right="10px"
          top="50%"
          transform="translateY(-50%)"
          pointerEvents="none"
          color="fg.muted"
        >
          <FiSearch />
        </Box>
      </Box>

      <Box flex="1" />

      <IconButton
        aria-label="Refresh users list"
        variant="outline"
        css={buttonOutline}
        onClick={onRefresh}
        disabled={isRefreshing}
        title="Refresh users list"
      >
        <FiRefreshCw />
      </IconButton>

      <Button css={buttonSolid} onClick={openCreate} data-testid="create-user-btn">
        <FiPlus />
        Create User
      </Button>
    </Flex>
  );
}
