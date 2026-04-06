'use client';

import { useState, useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
// import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import AntdProvider from "@components/AntdProvider";
import { GlobalStateProvider, useGlobalState } from "@core/state/globalState";
import QueryProvider from "@core/providers/QueryProvider";
import { ErrorBoundaryWrapper } from "@/app/components/ErrorBoundary";
import AppHeader from "@components/AppHeader";
import AppSidebar from "@components/AppSidebar";
import { Layout, Spin } from "antd";
import { useNextAuth, SessionProvider } from "@/src/features/auth";

const { Content } = Layout;

// const geistSans = Geist({
//   variable: "--font-geist-sans",
//   subsets: ["latin"],
// });

// const geistMono = Geist_Mono({
//   variable: "--font-geist-mono",
//   subsets: ["latin"],
// });

function LayoutContent({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const [collapsed, setCollapsed] = useState(false);
  const [mounted, setMounted] = useState(false);
  const { state, toggleTheme } = useGlobalState();
  const { theme: { mode: theme } } = state;
  const { isAuthenticated, isLoading } = useNextAuth();
  const pathname = usePathname();
  const router = useRouter();

  // Public routes that don't require authentication
  const publicRoutes = ['/login', '/auth'];
  const isPublicRoute = publicRoutes.includes(pathname);

  // Redirect to login if not authenticated and not on a public route
  useEffect(() => {
    if (!isLoading && !isAuthenticated && !isPublicRoute) {
      router.push('/login');
    }
  }, [isAuthenticated, isLoading, isPublicRoute, router]);

  // Ensure theme is properly hydrated before rendering
  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const rafId = window.requestAnimationFrame(() => setMounted(true));
    return () => {
      window.cancelAnimationFrame(rafId);
    };
  }, []);

  const handleCollapse = () => {
    setCollapsed(!collapsed);
  };

  const handleAuthClick = () => {
    // Navigate to dedicated auth page
    window.location.href = '/auth';
  };

  // Show loading during hydration or authentication check
  if (!mounted || isLoading) {
    return (
      <div style={{
        minHeight: '100vh',
        backgroundColor: theme === 'dark' ? '#090B1C' : '#F2F3FF',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        <Spin size="large" />
      </div>
    );
  }

  // If not authenticated and not on a public route, show loading while redirecting
  if (!isAuthenticated && !isPublicRoute) {
    return (
      <div style={{
        minHeight: '100vh',
        backgroundColor: theme === 'dark' ? '#090B1C' : '#F2F3FF',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <AntdProvider theme={theme}>
      <Layout style={{ minHeight: '100vh' }}>
        {/* Show header and sidebar only for authenticated users */}
        {isAuthenticated && (
          <>
            <AppHeader
              collapsed={collapsed}
              onCollapse={handleCollapse}
              theme={theme}
              onThemeChange={toggleTheme}
              onAuthClick={handleAuthClick}
            />
            <Layout style={{ marginTop: 64 }}>
              <AppSidebar
                collapsed={collapsed}
                onCollapse={setCollapsed}
              />
              <Content style={{
                marginLeft: collapsed ? 80 : 240,
                padding: '24px',
                minHeight: 'calc(100vh - 64px)',
                transition: 'margin-left 0.2s ease'
              }}>
                {children}
              </Content>
            </Layout>
          </>
        )}

        {/* Show content without header/sidebar for public routes */}
        {!isAuthenticated && isPublicRoute && (
          <Content style={{ minHeight: '100vh' }}>
            {children}
          </Content>
        )}
      </Layout>
    </AntdProvider>
  );
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <title>Intel AI for Enterprise Fine-Tuning</title>
      </head>
      <body
        className="antialiased"
      >
        <ErrorBoundaryWrapper>
          <SessionProvider>
            <QueryProvider>
              <GlobalStateProvider>
                <LayoutContent>
                  {children}
                </LayoutContent>
              </GlobalStateProvider>
            </QueryProvider>
          </SessionProvider>
        </ErrorBoundaryWrapper>
      </body>
    </html>
  );
}