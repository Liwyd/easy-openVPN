import { FC } from "react";
import { Text } from "@chakra-ui/react";
import { relativeTime } from "../utils/dateFormatter";

type UserStatusProps = {
  lastConnectedSince: string | null;
};

export const OnlineStatus: FC<UserStatusProps> = ({ lastConnectedSince }) => {
  if (!lastConnectedSince) {
    return (
      <Text
        display="inline-block"
        fontSize="xs"
        fontWeight="medium"
        ml={2}
        color="fg.muted"
      >
        Not Connected Yet
      </Text>
    );
  }

  const lastConnectedDate = new Date(lastConnectedSince);
  const now = new Date();
  const diffMs = now.getTime() - lastConnectedDate.getTime();
  const diffSec = Math.floor(diffMs / 1000);

  if (diffSec <= 60) {
    return (
      <Text
        display="inline-block"
        fontSize="xs"
        fontWeight="medium"
        ml={2}
        color="green.500"
      >
        Online
      </Text>
    );
  }

  return (
    <Text
      display="inline-block"
      fontSize="xs"
      fontWeight="medium"
      ml={2}
      color="fg.muted"
    >
      {relativeTime(lastConnectedDate)}
    </Text>
  );
};
