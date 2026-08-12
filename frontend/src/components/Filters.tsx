import { Button, Flex, Box, Input, IconButton, Icon, Spinner } from "@chakra-ui/react";
import { FiSearch, FiRefreshCw, FiPlus, FiX } from "react-icons/fi";

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
      zIndex="docked"
      bg="bg"
      py={4}
      gap={4}
      align="center"
      wrap="wrap"
    >
      <Flex position="relative" flex="1" minW="220px" align="center">
        <Box
          position="absolute"
          left="10px"
          top="50%"
          transform="translateY(-50%)"
          color="fg.muted"
          zIndex="2"
        >
          <Icon as={FiSearch} />
        </Box>
        <Input
          placeholder={searchPlaceholder}
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          pl="36px"
          pr={search ? "30px" : "10px"}
          data-testid={testId}
        />
        {search && (
          <Box
            position="absolute"
            right="6px"
            top="50%"
            transform="translateY(-50%)"
            zIndex="2"
          >
            <IconButton
              aria-label="Clear search"
              size="xs"
              variant="ghost"
              onClick={() => onSearchChange("")}
            >
              <FiX />
            </IconButton>
          </Box>
        )}
      </Flex>

      <Flex gap={2} align="center" ml="auto">
        {isRefreshing && <Spinner size="xs" />}
        <IconButton
          aria-label="Refresh"
          variant="outline"
          onClick={onRefresh}
          disabled={isRefreshing}
          title="Refresh"
          size="sm"
        >
          <FiRefreshCw />
        </IconButton>

        {onCreate && (
          <Button colorPalette="accent" onClick={onCreate} size="sm" px={5}>
            <FiPlus />
            {createLabel}
          </Button>
        )}
      </Flex>
    </Flex>
  );
}