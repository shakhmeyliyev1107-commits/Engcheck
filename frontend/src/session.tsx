import { createContext, useContext } from "react";
import type { User } from "./api";

export const SessionContext = createContext<{ user: User | null; setUser: (u: User | null) => void }>({
  user: null,
  setUser: () => {},
});
export const useSession = () => useContext(SessionContext);
export const can = (user: User | null, perm: string) => !!user && user.permissions.includes(perm);
