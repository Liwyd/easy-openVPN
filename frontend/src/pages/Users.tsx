import { useState } from "react";
import { VStack, Text, Spinner, Flex, Alert, Box } from "@chakra-ui/react";
import { FiUsers } from "react-icons/fi";
import { card } from "../theme-components";
import { UserProvider, useUserContext } from "../contexts/UserContext";
import { useUsersQuery, USERS_PER_PAGE_KEY } from "../hooks/useUsers";
import { useDebouncedValue, useStoredPerPage } from "../hooks/useCommon";
import Statistics from "../components/Statistics";
import Filters from "../components/Filters";
import UsersTable from "../components/UsersTable";
import Pagination from "../components/Pagination";
import UserDialog from "../components/UserDialog";
import UserModals from "../components/UserModals";
import QRCodeDialog from "../components/QRCodeDialog";

function UsersContent() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const { perPage, setPerPage } = useStoredPerPage(USERS_PER_PAGE_KEY);
  const { openCreate } = useUserContext();

  const debouncedSearch = useDebouncedValue(search, 300);

  const {
    data,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useUsersQuery({
    search: debouncedSearch,
    page,
    perPage,
  });

  const users = data?.users ?? [];
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
      <Statistics />
      <Filters
        search={search}
        onSearchChange={handleSearch}
        onRefresh={() => refetch()}
        isRefreshing={isFetching}
        onCreate={openCreate}
      />

      {isLoading && (
        <Flex py={20} justify="center">
          <Spinner size="lg" color="accent" />
        </Flex>
      )}

      {error && (
        <Alert.Root status="error" borderRadius="lg">
          <Alert.Title>Failed to load users</Alert.Title>
          <Alert.Description>
            {(error as Error).message || "An unexpected error occurred."}
          </Alert.Description>
        </Alert.Root>
      )}

      {!isLoading && !error && users.length === 0 && (
        <Box css={card} p={12} textAlign="center">
          <FiUsers size={40} style={{ margin: "0 auto 16px", opacity: 0.3 }} />
          <Text color="fg.muted">
            {search
              ? "No users match your search."
              : "No users yet. Create your first user to get started."}
          </Text>
        </Box>
      )}

      {!isLoading && !error && users.length > 0 && (
        <>
          <UsersTable users={users} isFetching={isFetching} />
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

      <UserDialog />
      <UserModals />
      <QRCodeDialog />
    </VStack>
  );
}

export default function Users() {
  return (
    <UserProvider>
      <UsersContent />
    </UserProvider>
  );
}
