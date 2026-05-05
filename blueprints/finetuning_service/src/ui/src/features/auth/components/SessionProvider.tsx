'use client';

import { SessionProvider as NextAuthSessionProvider } from 'next-auth/react';
import { config } from '@/src/core/config/appConfig';
import { ReactNode } from 'react';

interface SessionProviderProps {
  children: ReactNode;
}

export function SessionProvider({ children }: SessionProviderProps) {
  return <NextAuthSessionProvider basePath={`${config.basePath}/api/auth`}>{children}</NextAuthSessionProvider>;
}
