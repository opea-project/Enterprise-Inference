import { nextAuthTokenStorage } from '../utils/tokenStorage';

export class AuthApiError extends Error {
  constructor(
    message: string,
    public code: string,
    public details?: unknown,
    public statusCode?: number
  ) {
    super(message);
    this.name = 'AuthApiError';
  }
}


// Export NextAuth-aware token storage
export { nextAuthTokenStorage };