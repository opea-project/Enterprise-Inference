import { theme } from 'antd';
import type { ThemeConfig } from 'antd';

// Design tokens - Color palette
const colors = {
  // Primary colors

  /**
   * whole screen background colors
   */
  darkBg: '#090B1C', //whole screen background
  lightBg: '#F2F3FF',


  /**
   * sidebar colors
   */

  deepPurple: '#3D447F',
  darkPurple: '#222647',
  brightPurple: '#6b77db',

  // Background colors
  lightGrey: '#1f2133',
  lightPurple: '#e3e5fd',

  // Utility colors
  white60: '#ffffff60',
} as const;

/**
 * Creates a theme configuration for Ant Design components
 * @param themeMode - 'light' or 'dark' theme mode
 * @returns ThemeConfig object
 */
export const createThemeConfig = (themeMode: 'light' | 'dark'): ThemeConfig => {
  const isDark = themeMode === 'dark';

  return {
    algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
    token: {
      // Seed tokens - Primary brand colors
      colorPrimary: colors.deepPurple,
      colorPrimaryHover: isDark ? '#646999' : '#003E71',

      colorSuccess: '#52c41a',
      colorWarning: '#faad14',
      colorError: '#ff4d4f',
      colorInfo: colors.brightPurple,
      borderRadius: 8,
      wireframe: false,
      colorIcon: isDark ? '#E5E7FE' : colors.deepPurple,

      // Background colors
      colorBgContainer: isDark ? '#161b22' : '#ffffff',
      colorBgElevated: isDark ? '#161b22' : '#ffffff',
      colorBgLayout: isDark ? colors.darkBg : colors.lightBg,
      colorBgBase: isDark ? colors.darkBg : colors.lightBg,

      // Text colors
      colorText: isDark ? '#c9d1d9' : '#000000',
      colorTextSecondary: isDark ? '#ffffff' : colors.deepPurple,
      colorTextTertiary: isDark ? '#ffffff90' : '#6b7280',

      // Border colors
      colorBorder: isDark ? colors.white60 : `${colors.deepPurple}22`,
      colorBorderSecondary: isDark ? '#ffffff20' : `${colors.deepPurple}10`,

      colorPrimaryBgHover: isDark ? '#646999' : '#003E71',


      // Font
      fontFamily: 'Roboto, Arial, sans-serif',
    },

    components: {
      Button: {
        borderRadius: 25,
        fontWeight: 400,
        colorPrimary: colors.deepPurple,
        boxShadow: 'none',
        defaultShadow: 'none',
        primaryShadow: 'none',

        // colorPrimaryHover: isDark ? '#646999' : '#003E71',
        colorPrimaryActive: isDark ? colors.darkPurple : colors.lightPurple,

        // defaultColor: isDark ? '#ffffff' : colors.deepPurple,
        defaultBorderColor: isDark ? colors.white60 : `${colors.deepPurple}60`,
        defaultHoverBg: isDark ? colors.darkPurple : colors.lightPurple,
        defaultHoverBorderColor: isDark ? colors.white60 : `${colors.deepPurple}60`,
      },
      Card: {
      },
      Input: {
        borderRadius: 8,
        // colorBgContainer: isDark ? colors.lightGrey : colors.lightPurple,
        colorBorder: isDark ? '#ffffff20' : `${colors.deepPurple}10`,
        colorText: isDark ? '#fff' : '#3D447F',
        colorTextPlaceholder: isDark ? '#ffffff90' : '#6b7280',
      },
      Layout: {
        headerBg: isDark ? colors.darkBg : colors.lightBg,
        headerPadding: '0 24px',
        headerHeight: 64,
        lightSiderBg: '#E5E7FE',
        siderBg: colors.lightGrey,
        bodyBg: isDark ? colors.darkBg : colors.lightBg,
        headerColor: isDark ? '#c9d1d9' : '#000000',
      },
      Menu: {
        itemBg: isDark ? 'rgb(31, 33, 51)' : 'rgb(229, 231, 254)',
        darkItemBg: 'rgb(31, 33, 51)',

        itemColor: isDark ? '#c9d1d9' : '#000000',
        darkItemColor: '#c9d1d9',

        itemHoverBg: isDark ? 'rgba(230, 232, 253, 0.50)' : colors.lightPurple,
        itemHoverColor: isDark ? '#ffffff' : colors.deepPurple,
        itemSelectedBg: isDark ? colors.darkPurple : colors.lightPurple,
        itemSelectedColor: isDark ? '#ffffff' : colors.deepPurple,

        darkItemHoverBg: colors.darkPurple,
        darkItemHoverColor: '#ffffff',

        darkItemSelectedBg: colors.darkPurple,
        darkItemSelectedColor: '#ffffff',
      },
      Tooltip: {
        colorBgSpotlight: isDark ? colors.lightGrey : colors.darkPurple,
      },
      Modal: {
        headerBg: isDark ? colors.lightGrey : colors.lightBg,
        contentBg: isDark ? colors.lightGrey : colors.lightBg,
      },
      Divider: {
        colorSplit: isDark ? colors.white60 : colors.deepPurple,
      },
      Notification: {
        zIndexPopup: 1000,
        width: 384,
      }
    },
  };
};

// Legacy export for backward compatibility
export const customTheme: ThemeConfig = createThemeConfig('dark');

// Common breakpoints for responsive design
export const breakpoints = {
  xs: '(max-width: 575px)',
  sm: '(min-width: 576px)',
  md: '(min-width: 768px)',
  lg: '(min-width: 992px)',
  xl: '(min-width: 1200px)',
  xxl: '(min-width: 1600px)',
} as const;

// Helper function to get theme tokens
export const useThemeTokens = () => {
  const { token } = theme.useToken();
  return token;
};

// Export colors for use throughout the app
export { colors };