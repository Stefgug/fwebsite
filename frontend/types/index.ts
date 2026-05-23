export interface StrapiImage {
  id: number;
  documentId: string;
  url: string;
  alternativeText: string | null;
  width: number;
  height: number;
  formats: {
    thumbnail?: { url: string; width: number; height: number };
    small?: { url: string; width: number; height: number };
    medium?: { url: string; width: number; height: number };
    large?: { url: string; width: number; height: number };
  } | null;
}

export interface StrapiPagination {
  page: number;
  pageSize: number;
  pageCount: number;
  total: number;
}

export interface StrapiListResponse<T> {
  data: T[];
  meta: { pagination: StrapiPagination };
}

export interface StrapiSingleResponse<T> {
  data: T;
  meta: Record<string, unknown>;
}

// Strapi 5: flat responses — no .attributes wrapper
export interface Category {
  id: number;
  documentId: string;
  name: string;
  slug: string;
  description: string | null;
}

export interface Product {
  id: number;
  documentId: string;
  name: string;
  slug: string;
  description: string | null;
  excerpt: string | null;
  price: number;
  comparePrice: number | null;
  stock: number;
  sku: string | null;
  images: StrapiImage[] | null;
  category: Category | null;
  featured: boolean;
  publishedAt: string;
}

export interface Tag {
  id: number;
  documentId: string;
  name: string;
  slug: string;
}

export interface StrapiUser {
  id: number;
  username: string;
  email: string;
}

export interface Article {
  id: number;
  documentId: string;
  title: string;
  slug: string;
  content: unknown;
  excerpt: string | null;
  cover: StrapiImage | null;
  author: StrapiUser | null;
  tags: Tag[];
  publishedAt: string;
}

export interface ContactPayload {
  name: string;
  email: string;
  subject: string;
  message: string;
}

export interface CartItem {
  productId: number;
  documentId: string;
  name: string;
  slug: string;
  price: number;
  image: string | null;
  quantity: number;
}

export interface AuthResponse {
  jwt: string;
  user: StrapiUser;
}

export interface LoginPayload {
  identifier: string;
  password: string;
}

export interface RegisterPayload {
  username: string;
  email: string;
  password: string;
}

export interface SearchResults {
  products: Product[];
  articles: Article[];
}
