import { cookies } from 'next/headers';
import { strapiGetMe } from './strapi';
import type { StrapiUser } from '@/types';

export async function getCurrentUser(): Promise<StrapiUser | null> {
  const cookieStore = await cookies();
  const token = cookieStore.get('strapiToken')?.value;
  if (!token) return null;
  try {
    return await strapiGetMe(token);
  } catch {
    return null;
  }
}

export async function getAuthToken(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get('strapiToken')?.value ?? null;
}
