import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Field,
  Heading,
  IconButton,
  Input,
  InputGroup,
  Text,
  VStack,
} from "@chakra-ui/react";
import { HiOutlineEye, HiOutlineEyeOff, HiOutlineLogout } from "react-icons/hi";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { HOME_PATH } from "../lib/base";
import Footer from "../components/Footer";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
      navigate(HOME_PATH, { replace: true });
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Login failed";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <VStack justifyContent="space-between" minH="100vh" p="6" w="full">
      <Box w="full" flex="1">
        <VStack w="full" justifyContent="center" alignItems="center" h="full">
          <Box w="full" maxW="340px">
            <VStack alignItems="center" w="full">
              <img src="/favicon.svg" alt="" width={48} height={48} />
              <Heading as="h2" fontSize="2xl" fontWeight="semibold" textAlign="center">
                Login your account
              </Heading>
              <Text color="fg.muted" fontSize="sm">
                Welcome back, please login to your account.
              </Text>
            </VStack>
            <Box as="form" onSubmit={handleSubmit} w="full" maxW="300px" m="auto" pt="4">
              <VStack mt={4} gap={2}>
                <Field.Root>
                  <Input
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="Username"
                    autoComplete="username"
                  />
                </Field.Root>

                <Field.Root>
                  <InputGroup endElement={
                    <IconButton
                      variant="ghost"
                      size="xs"
                      onClick={() => setShowPassword(!showPassword)}
                      aria-label={showPassword ? "Hide password" : "Show password"}
                    >
                      {showPassword ? <HiOutlineEyeOff /> : <HiOutlineEye />}
                    </IconButton>
                  }>
                    <Input
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Password"
                      autoComplete="current-password"
                    />
                  </InputGroup>
                </Field.Root>

                {error && (
                  <Alert.Root status="error" rounded="md">
                    <Alert.Description>{error}</Alert.Description>
                  </Alert.Root>
                )}

                <Button
                  type="submit"
                  loading={loading}
                  w="full"
                  colorPalette="accent"
                >
                  <HiOutlineLogout style={{ marginRight: 4 }} />
                  Login
                </Button>
              </VStack>
            </Box>
          </Box>
        </VStack>
      </Box>
      <Footer />
    </VStack>
  );
}
