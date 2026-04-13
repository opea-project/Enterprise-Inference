'use client';

import { App } from 'antd';
import type { ArgsProps, NotificationInstance, IconType } from 'antd/es/notification/interface';
import type { ReactNode } from 'react';

type NotificationType = IconType;

interface NotificationConfig extends Partial<Omit<ArgsProps, 'type'>> {
  message: ReactNode;
  title?: ReactNode;
  type?: NotificationType;
}

// Custom hook to use notification API
export const useNotification = () => {
  const { notification } = App.useApp();
  return createNotificationMethods(notification);
};

// Helper function to create notification methods
const createNotificationMethods = (notificationApi: NotificationInstance) => ({
  // Success notification
  success: (config: NotificationConfig) => {
    const { message, title, ...rest } = config;
    notificationApi.success({
      message,
      title: title ?? message,
      placement: 'topRight',
      duration: 4.5,
      ...rest,
    });
  },

  // Info notification
  info: (config: NotificationConfig) => {
    const { message, title, ...rest } = config;
    notificationApi.info({
      message,
      title: title ?? message,
      placement: 'topRight',
      duration: 4.5,
      ...rest,
    });
  },

  // Warning notification
  warning: (config: NotificationConfig) => {
    const { message, title, ...rest } = config;
    notificationApi.warning({
      message,
      title: title ?? message,
      placement: 'topRight',
      duration: 4.5,
      ...rest,
    });
  },

  // Error notification
  error: (config: NotificationConfig) => {
    const { message, title, ...rest } = config;
    notificationApi.error({
      message,
      title: title ?? message,
      placement: 'topRight',
      duration: 0, // Don't auto close error notifications
      ...rest,
    });
  },

  // Generic notification
  open: (config: NotificationConfig & { type: NotificationType }) => {
    const { type, message, title, ...rest } = config;
    notificationApi[type]({
      message,
      title: title ?? message,
      placement: 'topRight',
      duration: type === 'error' ? 0 : 4.5,
      ...rest,
    });
  },

  // Destroy all notifications
  destroy: (key?: string) => {
    if (key) {
      notificationApi.destroy(key);
    } else {
      notificationApi.destroy();
    }
  },
});

// Global notification instance
let globalNotificationApi: NotificationInstance | null = null;

// Function to initialize the global notification API
export const initializeNotification = (notificationApi: NotificationInstance) => {
  globalNotificationApi = notificationApi;
};

// Direct notification service for non-hook usage
export const notify = {
  success: (config: NotificationConfig) => {
    if (!globalNotificationApi) {
      return;
    }
    createNotificationMethods(globalNotificationApi).success(config);
  },

  info: (config: NotificationConfig) => {
    if (!globalNotificationApi) {
      return;
    }
    createNotificationMethods(globalNotificationApi).info(config);
  },

  warning: (config: NotificationConfig) => {
    if (!globalNotificationApi) {
      return;
    }
    createNotificationMethods(globalNotificationApi).warning(config);
  },

  error: (config: NotificationConfig) => {
    if (!globalNotificationApi) {
      return;
    }
    createNotificationMethods(globalNotificationApi).error(config);
  },

  open: (config: NotificationConfig & { type: NotificationType }) => {
    if (!globalNotificationApi) {
      return;
    }
    createNotificationMethods(globalNotificationApi).open(config);
  },

  destroy: (key?: string) => {
    if (!globalNotificationApi) {
      return;
    }
    createNotificationMethods(globalNotificationApi).destroy(key);
  },
};

// Export types for TypeScript users
export type { NotificationConfig, NotificationType };
