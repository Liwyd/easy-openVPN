import { Flex, Text, Button, Select, For } from "@chakra-ui/react";
import { FiChevronLeft, FiChevronRight, FiChevronsLeft, FiChevronsRight } from "react-icons/fi";
import { createListCollection } from "@chakra-ui/react";
import { buttonOutline } from "../theme-components";

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

function pagesToShow(current: number, total: number): (number | "ellipsis")[] {
  const pages: (number | "ellipsis")[] = [];
  const push = (p: number) => {
    if (pages[pages.length - 1] !== p) pages.push(p);
  };

  if (total <= 7) {
    for (let i = 1; i <= total; i++) push(i);
    return pages;
  }

  push(1);
  if (current > 3) pages.push("ellipsis");
  for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) {
    push(i);
  }
  if (current < total - 2) pages.push("ellipsis");
  push(total);
  return pages;
}

export default function Pagination({
  page,
  totalPages,
  hasMore,
  onPageChange,
  perPage,
  onPerPageChange,
}: PaginationProps) {
  const safeTotal = Math.max(1, totalPages);

  return (
    <Flex justify="space-between" align="center" wrap="wrap" gap={3}>
      <Flex align="center" gap={2}>
        <Select.Root
          collection={perPageOptions}
          value={[String(perPage)]}
          onValueChange={(details) => onPerPageChange(Number(details.value[0]))}
          size="sm"
          width="80px"
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
        <Text fontSize="sm" color="fg.muted">
          Rows per page
        </Text>
      </Flex>

      <Flex align="center" gap={1}>
        <Button
          size="sm"
          variant="ghost"
          disabled={page <= 1}
          onClick={() => onPageChange(1)}
          title="First page"
        >
          <FiChevronsLeft />
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          title="Previous page"
        >
          <FiChevronLeft />
        </Button>

        <For each={pagesToShow(page, safeTotal)}>
          {(p, idx) =>
            p === "ellipsis" ? (
              <Text key={`e-${idx}`} px={1} color="fg.muted" fontSize="sm">
                {"\u2026"}
              </Text>
            ) : (
              <Button
                key={p}
                size="sm"
                variant="ghost"
                css={p === page ? buttonOutline : undefined}
                fontWeight={p === page ? "bold" : "normal"}
                onClick={() => onPageChange(p)}
              >
                {p}
              </Button>
            )
          }
        </For>

        <Button
          size="sm"
          variant="ghost"
          disabled={!hasMore || page >= safeTotal}
          onClick={() => onPageChange(page + 1)}
          title="Next page"
        >
          <FiChevronRight />
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={page >= safeTotal}
          onClick={() => onPageChange(safeTotal)}
          title="Last page"
        >
          <FiChevronsRight />
        </Button>
      </Flex>
    </Flex>
  );
}
