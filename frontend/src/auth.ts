import type { PublicClientApplication } from '@azure/msal-browser';

export type AuthConfig = { tenant_id: string; client_id: string; scopes: string[]; app_service: boolean; development: boolean };
let configPromise: Promise<AuthConfig> | undefined;
let clientPromise: Promise<PublicClientApplication | null> | undefined;

export function authConfig() {
  return configPromise ??= fetch('/api/auth/config').then(async r => {
    if (!r.ok) throw new Error('No se pudo cargar la configuración de acceso');
    return r.json() as Promise<AuthConfig>;
  }).catch(error => {
    configPromise = undefined;
    throw error;
  });
}

async function client() {
  return clientPromise ??= (async () => {
    const config = await authConfig();
    if (!config.client_id || !config.scopes.length || config.development) return null;
    const { PublicClientApplication } = await import('@azure/msal-browser');
    const instance = new PublicClientApplication({
      auth: { clientId: config.client_id, authority: `https://login.microsoftonline.com/${config.tenant_id}`,
              redirectUri: `${location.origin}/`, postLogoutRedirectUri: `${location.origin}/` },
      cache: { cacheLocation: 'sessionStorage' },
    });
    await instance.initialize();
    const result = await instance.handleRedirectPromise();
    if (result?.account) instance.setActiveAccount(result.account);
    const accounts = instance.getAllAccounts();
    if (!instance.getActiveAccount() && accounts.length === 1) instance.setActiveAccount(accounts[0]);
    return instance;
  })().catch(error => {
    clientPromise = undefined;
    throw error;
  });
}

export async function accessToken(fallback = '') {
  const instance = await client();
  const account = instance?.getActiveAccount();
  if (!instance || !account) return fallback;
  try {
    const result = await instance.acquireTokenSilent({ account, scopes: (await authConfig()).scopes });
    return result.accessToken;
  } catch (error) {
    if (error instanceof Error && error.name === 'InteractionRequiredAuthError') throw new Error('Tu sesión requiere iniciar sesión nuevamente con Microsoft.');
    throw error;
  }
}

export async function signIn() {
  const config = await authConfig();
  const instance = await client();
  if (instance) await instance.loginRedirect({ scopes: config.scopes, prompt: 'select_account' });
  else if (config.app_service) location.assign('/.auth/login/aad?post_login_redirect_uri=/');
  else throw new Error('Falta configurar el registro de Microsoft Entra para esta instalación.');
}

export async function signOut() {
  const instance = await client();
  if (instance) await instance.logoutRedirect();
  else if ((await authConfig()).app_service) location.assign('/.auth/logout?post_logout_redirect_uri=/');
}

export async function restoreSession() {
  const token = await accessToken();
  if (token) return token;
  if (!(await authConfig()).app_service) return '';
  const response = await fetch('/.auth/me');
  const entries = response.ok ? await response.json() : [];
  return Array.isArray(entries) ? entries.find(e => e.provider_name === 'aad')?.access_token || '' : '';
}
