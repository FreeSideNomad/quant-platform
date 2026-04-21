import { useQuery } from '@tanstack/react-query';
import { api, ApiError } from './api';

export interface Me {
  sub: string;
  email: string;
  name: string | null;
  roles: string[];
  tenant_id: string | null;
}

export function useMe() {
  return useQuery<Me | null>({
    queryKey: ['me'],
    queryFn: async () => {
      try {
        return await api.get<Me>('/auth/me');
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return null;
        throw err;
      }
    },
    retry: false,
    staleTime: 30_000,
  });
}

export function login(): void {
  const returnTo = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.href = `/auth/login?return_to=${returnTo}`;
}

export function logout(): void {
  window.location.href = '/auth/logout';
}
