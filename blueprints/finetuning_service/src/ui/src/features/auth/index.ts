// Types
export type {
  RegisterRequest,
  LoginRequest,
  AuthResponse,
  UserProfile as UserProfileType,
  AuthState,
  ValidationError,
  HTTPValidationError,
} from './types';
export { AuthError } from './types';

// API
export {AuthApiError } from './api/client';

// Hooks
export {
  useNextAuth,
} from './hooks';

// Components
export {
  LoginForm,
  AuthModal,
  UserProfile,
  UserAvatar,
  AuthGuard,
  RequireAuth,
  SessionProvider,
} from './components';
export type {
  AuthFormsProps,
  AuthModalProps,
  UserProfileProps,
  AuthGuardProps,
  RequireAuthProps,
} from './components';