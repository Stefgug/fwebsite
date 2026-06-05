import { beforeEach, describe, expect, test, vi } from 'vitest';

type MockJson = Record<string, unknown>;

function mockFetchOnce({ ok = true, status = 200, json = {} as MockJson } = {}) {
  vi.spyOn(global, 'fetch').mockResolvedValueOnce({
    ok,
    status,
    json: vi.fn().mockResolvedValue(json),
  } as unknown as Response);
}

describe('strapi helpers', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    process.env.NEXT_PUBLIC_STRAPI_URL = 'http://localhost:1999';
    process.env.STRAPI_API_TOKEN = 'token-123';
  });

  test('getProducts builds query and returns data', async () => {
    const payload = { data: [{ id: 1, name: 'MacBook' }], meta: { pagination: { page: 1 } } };
    mockFetchOnce({ json: payload });

    const { getProducts } = await import('@/lib/strapi');
    const res = await getProducts({ categorySlug: 'electronics', search: 'mac' });

    expect(res.data).toHaveLength(1);
    const [url, options] = vi.mocked(global.fetch).mock.calls[0];
    expect(String(url)).toContain('/api/products?');
    expect(String(url)).toContain('filters[category][slug][$eq]=electronics');
    expect(String(url)).toContain('filters[name][$containsi]=mac');
    expect((options as RequestInit).headers).toMatchObject({
      Authorization: 'Bearer token-123',
      'Content-Type': 'application/json',
    });
  });

  test('strapiLogin throws API error message when request fails', async () => {
    mockFetchOnce({ ok: false, status: 400, json: { error: { message: 'Bad credentials' } } });
    const { strapiLogin } = await import('@/lib/strapi');

    await expect(strapiLogin({ identifier: 'x', password: 'y' })).rejects.toThrow('Bad credentials');
  });

  test('strapiRegister returns auth payload', async () => {
    const authPayload = { jwt: 'jwt', user: { id: 1, username: 'test', email: 'test@example.com' } };
    mockFetchOnce({ json: authPayload });
    const { strapiRegister } = await import('@/lib/strapi');

    await expect(
      strapiRegister({ username: 'test', email: 'test@example.com', password: 'pass1234' })
    ).resolves.toMatchObject({ jwt: 'jwt' });
  });

  test('getStrapiImageUrl keeps absolute URLs and prefixes relative ones', async () => {
    const { getStrapiImageUrl } = await import('@/lib/strapi');

    expect(getStrapiImageUrl('https://cdn.example.com/a.jpg')).toBe('https://cdn.example.com/a.jpg');
    expect(getStrapiImageUrl('/uploads/a.jpg')).toBe('http://localhost:1999/uploads/a.jpg');
  });
});
