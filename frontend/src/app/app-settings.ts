export const APP_SETTINGS = {
  auth: {
    enabled: false
  },
  features: {
    specificationImportEnabled: false
  }
} as const;

export const AUTH_DISABLED_USER = {
  id: 0,
  username: 'workspace',
  email: 'workspace@sakura.local',
  first_name: 'Workspace',
  last_name: 'User',
  role: 'user'
} as const;
