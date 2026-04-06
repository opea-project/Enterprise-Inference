import { getSession } from 'next-auth/react';

/**
 * Get the access token from NextAuth session
 * This function can be used in both client and server components
 */
export async function getNextAuthToken(): Promise<string | null> {
  if (typeof window === 'undefined') {
    // Server-side: Cannot use getSession
    return null;
  }

  const session = await getSession();
  return session?.accessToken || null;
}

/**
 * Token storage utilities that work with both NextAuth and legacy auth
 */
export const nextAuthTokenStorage = {
  /**
   * Get token - tries NextAuth first, falls back to legacy localStorage
   */
  async get(): Promise<string | null> {
    // Try NextAuth session first
    const nextAuthToken = await getNextAuthToken();
    if (nextAuthToken) {
      return nextAuthToken;
    }

    // Fallback to legacy localStorage token
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('auth_token');
  },

  /**
   * Get user ID for dataprep API key
   */
  getDataprepApiKey(): string | null {
    if (typeof window === 'undefined') return null;
    const userId = localStorage.getItem('user_id');
    return userId ? btoa(userId) : null;
  },

  /**
   * Legacy set method (for backwards compatibility)
   */
  set(token: string): void {
    if (typeof window === 'undefined') return;
    localStorage.setItem('auth_token', token);
  },

  /**
   * Legacy setUserId method (for backwards compatibility)
   */
  setUserId(userId: string): void {
    if (typeof window === 'undefined') return;
    localStorage.setItem('user_id', userId);
  },

  /**
   * Remove all auth tokens
   */
  remove(): void {
    if (typeof window === 'undefined') return;
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_id');
  },
};
