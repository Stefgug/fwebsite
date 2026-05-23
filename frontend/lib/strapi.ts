import qs from 'qs';
import type {
  StrapiListResponse,
  Product,
  Category,
  Article,
  Tag,
  ContactPayload,
  AuthResponse,
  LoginPayload,
  RegisterPayload,
  SearchResults,
  StrapiUser,
} from '@/types';

const STRAPI_URL = process.env.NEXT_PUBLIC_STRAPI_URL!;
const API_TOKEN = process.env.STRAPI_API_TOKEN;

async function strapiFetch<T>(
  path: string,
  options: RequestInit & { params?: Record<string, unknown> } = {}
): Promise<T> {
  const { params, ...fetchOptions } = options;
  const query = params ? `?${qs.stringify(params, { encodeValuesOnly: true })}` : '';
  const url = `${STRAPI_URL}/api${path}${query}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(fetchOptions.headers as Record<string, string>),
  };

  if (API_TOKEN) {
    headers['Authorization'] = `Bearer ${API_TOKEN}`;
  }

  const res = await fetch(url, {
    ...fetchOptions,
    headers,
    next: { revalidate: 60 },
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(
      (error as { error?: { message?: string } })?.error?.message ??
        `Strapi error ${res.status}`
    );
  }

  return res.json() as Promise<T>;
}

export async function getProducts(opts?: {
  page?: number;
  pageSize?: number;
  categorySlug?: string;
  search?: string;
}): Promise<StrapiListResponse<Product>> {
  const filters: Record<string, unknown> = {};
  if (opts?.categorySlug) filters['category'] = { slug: { $eq: opts.categorySlug } };
  if (opts?.search) filters['name'] = { $containsi: opts.search };

  return strapiFetch('/products', {
    params: {
      populate: ['images', 'category'],
      filters,
      pagination: { page: opts?.page ?? 1, pageSize: opts?.pageSize ?? 12 },
      sort: ['createdAt:desc'],
    },
  });
}

export async function getProductBySlug(slug: string): Promise<Product | null> {
  const res = await strapiFetch<StrapiListResponse<Product>>('/products', {
    params: {
      filters: { slug: { $eq: slug } },
      populate: ['images', 'category'],
    },
  });
  return res.data[0] ?? null;
}

export async function getFeaturedProducts(): Promise<Product[]> {
  const res = await strapiFetch<StrapiListResponse<Product>>('/products', {
    params: {
      filters: { featured: { $eq: true } },
      populate: ['images', 'category'],
      pagination: { pageSize: 6 },
    },
  });
  return res.data;
}

export async function getCategories(): Promise<Category[]> {
  const res = await strapiFetch<StrapiListResponse<Category>>('/categories', {
    params: { sort: ['name:asc'] },
  });
  return res.data;
}

export async function getArticles(opts?: {
  page?: number;
  pageSize?: number;
  tagSlug?: string;
  search?: string;
}): Promise<StrapiListResponse<Article>> {
  const filters: Record<string, unknown> = {};
  if (opts?.tagSlug) filters['tags'] = { slug: { $eq: opts.tagSlug } };
  if (opts?.search) filters['title'] = { $containsi: opts.search };

  return strapiFetch('/articles', {
    params: {
      populate: ['cover', 'author', 'tags'],
      filters,
      pagination: { page: opts?.page ?? 1, pageSize: opts?.pageSize ?? 9 },
      sort: ['publishedAt:desc'],
    },
  });
}

export async function getArticleBySlug(slug: string): Promise<Article | null> {
  const res = await strapiFetch<StrapiListResponse<Article>>('/articles', {
    params: {
      filters: { slug: { $eq: slug } },
      populate: ['cover', 'author', 'tags'],
    },
  });
  return res.data[0] ?? null;
}

export async function getTags(): Promise<Tag[]> {
  const res = await strapiFetch<StrapiListResponse<Tag>>('/tags', {
    params: { sort: ['name:asc'] },
  });
  return res.data;
}

export async function globalSearch(query: string): Promise<SearchResults> {
  const [productsRes, articlesRes] = await Promise.all([
    getProducts({ search: query, pageSize: 6 }),
    getArticles({ search: query, pageSize: 6 }),
  ]);
  return { products: productsRes.data, articles: articlesRes.data };
}

export async function createContact(data: ContactPayload): Promise<void> {
  await strapiFetch('/contacts', {
    method: 'POST',
    body: JSON.stringify({ data }),
  });
}

// Auth functions — use Strapi built-in auth endpoints (no API token)
export async function strapiLogin(payload: LoginPayload): Promise<AuthResponse> {
  const res = await fetch(`${STRAPI_URL}/api/auth/local`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(
      (err as { error?: { message?: string } })?.error?.message ?? 'Login failed'
    );
  }
  return res.json();
}

export async function strapiRegister(payload: RegisterPayload): Promise<AuthResponse> {
  const res = await fetch(`${STRAPI_URL}/api/auth/local/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(
      (err as { error?: { message?: string } })?.error?.message ?? 'Registration failed'
    );
  }
  return res.json();
}

export async function strapiGetMe(jwt: string): Promise<StrapiUser> {
  const res = await fetch(`${STRAPI_URL}/api/users/me`, {
    headers: { Authorization: `Bearer ${jwt}` },
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Unauthorized');
  return res.json();
}

export function getStrapiImageUrl(url: string): string {
  if (url.startsWith('http')) return url;
  return `${STRAPI_URL}${url}`;
}
