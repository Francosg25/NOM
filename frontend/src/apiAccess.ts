export type AuthConfig = {
  mode: "portal" | "entra";
  app_service: boolean;
  development: boolean;
  demo_enabled: boolean;
};
let configPromise: Promise<AuthConfig> | undefined;

export function authConfig() {
  return (configPromise ??= fetch("/api/auth/config")
    .then(async (response) => {
      if (!response.ok) throw new Error("No se pudo conectar con el portal.");
      return response.json() as Promise<AuthConfig>;
    })
    .catch((error) => {
      configPromise = undefined;
      throw error;
    }));
}

// Open reading needs no token. Optional Easy Auth can supply one when enabled.
export async function accessToken(fallback = "") {
  return fallback;
}

export async function restoreSession() {
  const config = await authConfig();
  if (config.mode === "portal" || !config.app_service) return "";
  const response = await fetch("/.auth/me");
  const entries = response.ok ? await response.json() : [];
  return Array.isArray(entries)
    ? entries.find((entry) => entry.provider_name === "aad")?.access_token || ""
    : "";
}

export async function signIn() {
  if ((await authConfig()).app_service)
    location.assign("/.auth/login/aad?post_login_redirect_uri=/");
  else throw new Error("El acceso Microsoft opcional no está configurado.");
}

export async function signOut() {
  if ((await authConfig()).app_service)
    location.assign("/.auth/logout?post_logout_redirect_uri=/");
}
