import { useState } from "react";
import { VStack, Text, Spinner, Flex, Alert, Box } from "@chakra-ui/react";
import { FiShield } from "react-icons/fi";
import { card } from "../theme-components";
import { AdminProvider, useAdminContext } from "../contexts/AdminContext";
import { useAdminsQuery, ADMINS_PER_PAGE_KEY } from "../hooks/useAdmins";
import { useDebouncedValue, useStoredPerPage } from "../hooks/useCommon";
import Filters from "../components/Filters";
import AdminsTable from "../components/AdminsTable";
import Pagination from "../components/Pagination";
import AdminDialog from "../components/AdminDialog";
import AdminModals from "../components/AdminModals";

function AdminsContent() {
  const { openCreate } = useAdminContext();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const { perPage, setPerPage } = useStoredPerPage(ADMINS_PER_PAGE_KEY);

  const debouncedSearch = useDebouncedValue(search, 300);

  const {
    data,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useAdminsQuery({ search: debouncedSearch, page, perPage });

  const admins = data?.admins ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / perPage));

  function handleSearch(value: string) {
    setSearch(value);
    setPage(1);
  }

  function handlePerPage(value: number) {
    setPerPage(value);
    setPage(1);
  }

  return (
    <VStack align="stretch" gap={6}>
      <Filters
        search={search}
        onSearchChange={handleSearch}
        onRefresh={() => refetch()}
        isRefreshing={isFetching}
        createLabel="New Admin"
        onCreate={openCreate}
        searchPlaceholder="Search by username..."
        testId="admins-search"
      />

      {isLoading && (
        <Flex py={20} justify="center">
          <Spinner size="lg" color="accent" />
        </Flex>
      )}

      {error && (
        <Alert.Root status="error" borderRadius="lg">
          <Alert.Title>Failed to load admins</Alert.Title>
          <Alert.Description>
            {(error as Error).message || "An unexpected error occurred."}
          </Alert.Description>
        </Alert.Root>
      )}

      {!isLoading && !error && admins.length === 0 && (
        <Box css={card} p={12} textAlign="center">
          <FiShield size={40} style={{ margin: "0 auto 16px", opacity: 0.3 }} />
          <Text color="fg.muted">
            {search
              ? "No admins match your search."
              : "No admins yet. Create your first admin to get started."}
          </Text>
        </Box>
      )}

      {!isLoading && !error && admins.length > 0 && (
        <>
          <AdminsTable admins={admins} isFetching={isFetching} />
          <Pagination
            page={page}
            totalPages={totalPages}
            hasMore={page < totalPages}
            onPageChange={setPage}
            perPage={perPage}
            onPerPageChange={handlePerPage}
          />
        </>
      )}

      <AdminDialog />
      <AdminModals />
    </VStack>
  );
}

export default function Admins() {
  return (
    <AdminProvider>
      <AdminsContent />
    </AdminProvider>
  );
}
