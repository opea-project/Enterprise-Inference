

export const config = {
  defaultTheme: 'light',
  basePath: process.env.NEXT_PUBLIC_BASE_PATH || '',  // Application base path
  filePathSeperator: "#", //seperator used to show files as paths
  endpoints: {
    base: process.env.NEXT_PUBLIC_AUTH_URL,
    files: process.env.NEXT_PUBLIC_FILES_BASE_URL,
    dataprep: process.env.NEXT_PUBLIC_DATAPREP_BASE_URL,
    fineTuning: process.env.NEXT_PUBLIC_FINETUNING_API_URL,
    timeout: 10000,
  }
} as const;
