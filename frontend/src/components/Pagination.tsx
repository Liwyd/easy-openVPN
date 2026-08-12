import { HStack, Text, Button, ButtonGroup, Select, For, Box, Icon } from "@chakra-ui/react";
import { FiArrowLeft, FiArrowRight } from "react-icons/fi";
import { createListCollection } from "@chakra-ui/react";
import { buttonSolid, buttonOutline } from "../theme-components";
import { useTranslation } from "react-i18next";

const perPageOptions = createListCollection({
  items: [10, 20, 30, 50].map((n) => ({ label: String(n), value: String(n) })),
});

interface PaginationProps {
  page: number;
  totalPages: number;
  hasMore: boolean;
  onPageChange: (page: number) => void;
  perPage: number;
  onPerPageChange: (value: number) => void;
}

/**
 * Generate numeric page items around current page (0-indexed).
 *   - Always include first and last page
 *   - Add ellipsis if needed
 */
function generatePageItems(total: number, current: number, width = 7) {
  const MINIMAL_PAGE_ITEM_COUNT = 5;
  if (width < MINIMAL_PAGE_ITEM_COUNT) {
    throw new Error(`Must allow at least ${MINIMAL_PAGE_ITEM_COUNT} page items`);
  }
  if (width % 2 === 0) {
    throw new Error("Must allow odd number of page items");
  }
  if (total < width) {
    return [...Array(total).keys()];
  }
  const left = Math.max(
    0,
    Math.min(total - width, current - Math.floor(width / 2)),
  );
  const items: (string | number)[] = Array(width);
  for (let i = 0; i < width; i += 1) {
    items[i] = i + left;
  }
  if ((items[0] as number) > 0) {
    items[0] = 0;
    items[1] = "prev-more";
  }
  if ((items[items.length - 1] as number) < total - 1) {
    items[items.length - 1] = total - 1;
    items[items.length - 2] = "next-more";
  }
  return items;
}

export default function Pagination({
  page,
  totalPages,
  hasMore,
  onPageChange,
  perPage,
  onPerPageChange,
}: PaginationProps) {
  const { t } = useTranslation();
  const safeTotal = Math.max(1, totalPages);
  const pageIndex = page - 1;
  const pages = generatePageItems(safeTotal, pageIndex, 7);

  return (
    <HStack
      justifyContent="space-between"
      mt={4}
      w="full"
      display="flex"
      columnGap={{ lg: 4, md: 0 }}
      rowGap={{ md: 0, base: 4 }}
      flexDirection={{ md: "row", base: "column" }}
    >
      <Box order={{ base: 2, md: 1 }}>
        <HStack>
          <Select.Root
            collection={perPageOptions}
            value={[String(perPage)]}
            onValueChange={(details) =>
              onPerPageChange(Number(details.value[0]))
            }
            size="sm"
            width="70px"
          >
            <Select.Control>
              <Select.Trigger>
                <Select.ValueText />
              </Select.Trigger>
            </Select.Control>
            <Select.Positioner>
              <Select.Content>
                <For each={perPageOptions.items}>
                  {(item) => (
                    <Select.Item key={item.value} item={item}>
                      <Select.ItemText>{item.label}</Select.ItemText>
                    </Select.Item>
                  )}
                </For>
              </Select.Content>
            </Select.Positioner>
          </Select.Root>
          <Text whiteSpace="nowrap" fontSize="sm">
            {t("pagination.itemsPerPage")}
          </Text>
        </HStack>
      </Box>

      <ButtonGroup size="sm" attached variant="outline" order={{ base: 1, md: 2 }}>
        <Button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          title={t("pagination.previousPage")}
        >
          <Icon as={FiArrowLeft} mr={2} />
          {t("pagination.previous")}
        </Button>
        {pages.map((pageIndexItem, idx) => {
          if (typeof pageIndexItem === "string")
            return <Button key={`${pageIndexItem}-${idx}`}>...</Button>;
          return (
            <Button
              key={pageIndexItem}
              css={pageIndexItem === pageIndex ? buttonSolid : buttonOutline}
              onClick={() => onPageChange(pageIndexItem + 1)}
            >
              {pageIndexItem + 1}
            </Button>
          );
        })}
        <Button
          onClick={() => onPageChange(page + 1)}
          disabled={!hasMore || page >= safeTotal}
          title={t("pagination.nextPage")}
        >
          {t("pagination.next")}
          <Icon as={FiArrowRight} ml={2} />
        </Button>
      </ButtonGroup>
    </HStack>
  );
}

