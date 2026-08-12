import { Button, Flex, Box, Input, IconButton, Icon } from "@chakra-ui/react";
import { FiSearch, FiRefreshCw, FiPlus, FiX } from "react-icons/fi";
import { useTranslation } from "react-i18next";

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
  createLabel,
  onCreate,
  searchPlaceholder,
  testId = "users-search",
}: FiltersProps) {
  const { t } = useTranslation();
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
          placeholder={searchPlaceholder ?? t("users.search")}
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
              aria-label={t("users.clearSearch")}
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
        <IconButton
          aria-label={t("users.refresh")}
          variant="outline"
          onClick={onRefresh}
          disabled={isRefreshing}
          title={t("users.refresh")}
          size="sm"
        >
          <FiRefreshCw className={isRefreshing ? "animate-spin" : undefined} />
        </IconButton>

        {onCreate && (
          <Button colorPalette="accent" onClick={onCreate} size="sm" px={5}>
            <FiPlus />
            {createLabel ?? t("users.create")}
          </Button>
        )}
      </Flex>
    </Flex>
  );
}