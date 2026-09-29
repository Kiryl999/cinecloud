import { createContext } from 'react';

/** Shared auth state. Kept in its own module so the provider file exports
    nothing but a component, which keeps React Fast Refresh working. */
export const AuthContext = createContext(null);
