import { useState } from "react";
import {
  Box,
  Button,
  Field,
  Heading,
  IconButton,
  Input,
  InputGroup,
  Stack,
  Text,
  VStack,
} from "@chakra-ui/react";
import { HiOutlineEye, HiOutlineEyeOff } from "react-icons/hi";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { HOME_PATH } from "../lib/base";

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
    <Box minH="100vh" bg="bg" display="flex" alignItems="center" justifyContent="center">
      <VStack
        w="100%"
        maxW="400px"
        p={8}
        gap={8}
        border="1px solid"
        borderColor="border.strong"
        borderRadius="lg"
        bg="bg"
        mx={4}
      >
        <VStack gap={2}>
          <img src="/favicon.svg" alt="" width={32} height={32} />
          <Heading size="lg" color="accent">
            eovpanel
          </Heading>
          <Text color="fg.muted" fontSize="sm">
            Sign in to your account
          </Text>
        </VStack>

        <Box as="form" onSubmit={handleSubmit} w="100%">
          <Stack gap={4}>
            <Field.Root required>
              <Field.Label>Username</Field.Label>
              <Input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                autoComplete="username"
              />
            </Field.Root>

            <Field.Root required>
              <Field.Label>Password</Field.Label>
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
              <Text color="fg" fontSize="sm" bg="bg.subtle" p={2} borderRadius="md">
                {error}
              </Text>
            )}

            <Button type="submit" loading={loading} w="100%">
              Sign In
            </Button>
          </Stack>
        </Box>
      </VStack>
    </Box>
  );
}
