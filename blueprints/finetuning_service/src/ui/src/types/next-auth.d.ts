import 'next-auth';
import { DefaultSession } from 'next-auth';

declare module 'next-auth' {
  interface Session {
    accessToken?: string;
    provider?: string;
    error?: string;
    idToken?: string;
    user: {
      id: string;
      email?: string | null;
      name?: string | null;
    } & DefaultSession['user'];
  }

  interface User {
    accessToken?: string;
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    accessToken?: string;
    refreshToken?: string;
    idToken?: string;
    accessTokenExpires?: number;
    provider?: string;
    error?: string;
    user?: {
      id: string;
      email?: string | null;
      name?: string | null;
    };
  }
}
