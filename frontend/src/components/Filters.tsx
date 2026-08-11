import { Flex, Input, Box, IconButton, Button } from "@chakra-ui/react";
import { FiSearch, FiRefreshCw, FiPlus } from "react-icons/fi";
import { buttonSolid, buttonOutline } from "../theme-components";

interface FiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  onRefresh: () => void;
  isRefreshing: boolean;
  createLabel?: string;
  onCreate?: () => void;
  searchPlaceholder?: string;
  testId?: string;
}

export default function Filters({
  search,
  onSearchChange,
  onRefresh,
  isRefreshing,
  createLabel = "Create User",
  onCreate,
  searchPlaceholder = "Search...",
  testId = "users-search",
}: FiltersProps) {
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
          placeholder={searchPlaceholder}
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          pe="36px"
          data-testid={testId}
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
        aria-label="Refresh"
        variant="outline"
        css={buttonOutline}
        onClick={onRefresh}
        disabled={isRefreshing}
        title="Refresh"
      >
        <FiRefreshCw />
      </IconButton>

      {onCreate && (
        <Button css={buttonSolid} onClick={onCreate}>
          <FiPlus />
          {createLabel}
        </Button>
      )}
    </Flex>
  );
}
