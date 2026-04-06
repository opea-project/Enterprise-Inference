import NextAuth, { AuthOptions, Session, User } from 'next-auth';
import { JWT } from 'next-auth/jwt';
import KeycloakProvider from 'next-auth/providers/keycloak';

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

export const authOptions: AuthOptions = {
  providers: [
    KeycloakProvider({
      clientId: process.env.KEYCLOAK_CLIENT_ID!,
      clientSecret: process.env.KEYCLOAK_CLIENT_SECRET || '',
      issuer: process.env.KEYCLOAK_ISSUER!,
      authorization: {
        params: {
          scope: 'openid email profile',
        },
      },
      client: {
        token_endpoint_auth_method: 'none',
      },
    })
  ],
  session: {
    strategy: 'jwt',
    maxAge:  60 * 60, // 1hr
  },
  pages: {
    signIn: `${basePath}/login`,
    error: `${basePath}/login`,
  },
  callbacks: {
    async jwt({ token, user, account }: { token: JWT; user?: User; account?: any }) {
      // Initial sign in
      if (account && user) {
        if (account.provider === 'keycloak') {
          // Keycloak login - store id_token for logout
          return {
            ...token,
            accessToken: account.access_token,
            refreshToken: account.refresh_token,
            idToken: account.id_token,
            accessTokenExpires: account.expires_at ? account.expires_at * 1000 : 0,
            provider: 'keycloak',
            user: {
              id: user.id,
              email: user.email,
              name: user.name,
            },
          };
        } else {
          // Credentials login
          return {
            ...token,
            accessToken: (user as User & { accessToken: string }).accessToken,
            provider: 'credentials',
            user: {
              id: user.id,
              email: user.email,
            },
          };
        }
      }

      // Return previous token if the access token has not expired yet
      if (token.accessTokenExpires && Date.now() < (token.accessTokenExpires as number)) {
        return token;
      }

      // Access token has expired for Keycloak, try to refresh it
      if (token.provider === 'keycloak' && token.refreshToken) {
        try {
          const refreshedTokens = await refreshAccessToken(token);
          return refreshedTokens;
        } catch (error) {
          console.error('Error refreshing access token:', error);
          return {
            ...token,
            error: 'RefreshAccessTokenError',
          };
        }
      }

      return token;
    },
    async session({ session, token }: { session: Session; token: JWT }) {
      if (token) {
        session.user = token.user as any;
        session.accessToken = token.accessToken as string;
        session.provider = token.provider as string;
        session.error = token.error as string | undefined;
        session.idToken = token.idToken as string | undefined;
      }
      return session;
    },
  },
  events: {
    async signOut({ token }: { token?: JWT }) {
      // Perform Keycloak logout if provider is keycloak
      if (token?.provider === 'keycloak' && token?.idToken) {
        try {
          console.log('Logging out from Keycloak');
          const logoutUrl = `${process.env.KEYCLOAK_ISSUER}/protocol/openid-connect/logout`;
          const params = new URLSearchParams({
            id_token_hint: token.idToken as string,
            post_logout_redirect_uri: `${process.env.NEXTAUTH_URL}${basePath}/login`,
          });

          await fetch(`${logoutUrl}?${params.toString()}`, {
            method: 'GET',
          });
        } catch (error) {
          console.error('Error logging out from Keycloak:', error);
        }
      }
    },
  },
  debug:  process.env.NODE_ENV === 'development',
};

async function refreshAccessToken(token: JWT): Promise<JWT> {
  try {
    const url = `${process.env.KEYCLOAK_ISSUER}/protocol/openid-connect/token`;

    const params: Record<string, string> = {
      client_id: process.env.KEYCLOAK_CLIENT_ID!,
      grant_type: 'refresh_token',
      refresh_token: token.refreshToken as string,
    };

    // Only include client_secret if it's provided (for confidential clients)
    if (process.env.KEYCLOAK_CLIENT_SECRET) {
      params.client_secret = process.env.KEYCLOAK_CLIENT_SECRET;
    }

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams(params),
    });

    const refreshedTokens = await response.json();

    if (!response.ok) {
      throw refreshedTokens;
    }

    return {
      ...token,
      accessToken: refreshedTokens.access_token,
      accessTokenExpires: Date.now() + refreshedTokens.expires_in * 1000,
      refreshToken: refreshedTokens.refresh_token ?? token.refreshToken
    };
  } catch (error) {
    console.error('Error refreshing token:', error);
    return {
      ...token,
      error: 'RefreshAccessTokenError',
    };
  }
}

const handler = NextAuth(authOptions);

export { handler as GET, handler as POST };
