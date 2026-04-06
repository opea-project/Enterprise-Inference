'use client';
import { useSession, signIn, signOut } from 'next-auth/react';
import { useCallback } from 'react';

export const useNextAuth = () => {
  const { data: session, status } = useSession();

  const loginWithKeycloak = useCallback(async () => {
    await signIn('keycloak');
  }, []);

  const logout = useCallback(async () => {
    await signOut();
  }, []);

  return {
    // Session data
    session,
    user: session?.user || null,
    accessToken: session?.accessToken,
    provider: session?.provider,

    // Status
    isLoading: status === 'loading',
    isAuthenticated: status === 'authenticated',
    isUnauthenticated: status === 'unauthenticated',

    // Actions
    loginWithKeycloak,
    logout,

    // Error handling
    error: session?.error,
  };
};
