#!/usr/bin/env node
/**
 * Mock Strapi 5 server for Playwright tests.
 * Starts on port 1338 (same as dev) so Next.js env vars need no change.
 */
const http = require('http');

const MOCK_CATEGORY = { id: 1, documentId: 'cat-1', name: 'Electronics', slug: 'electronics', description: null };
const MOCK_CATEGORIES = [
  MOCK_CATEGORY,
  { id: 2, documentId: 'cat-2', name: 'Clothing', slug: 'clothing', description: null },
  { id: 3, documentId: 'cat-3', name: 'Books', slug: 'books', description: null },
];

const MOCK_PRODUCTS = [
  {
    id: 1, documentId: 'prod-1', name: 'MacBook Pro 14', slug: 'macbook-pro-14',
    price: 1999, comparePrice: 2199, stock: 5, sku: 'MBP14-001', featured: true,
    excerpt: 'Powerful laptop for professionals',
    description: [{ type: 'paragraph', children: [{ type: 'text', text: 'Powerful laptop for professionals.' }] }],
    images: [{ id: 1, documentId: 'img-1', url: 'https://picsum.photos/seed/macbook14/400/400', alternativeText: 'MacBook Pro 14', width: 400, height: 400, formats: null }],
    category: MOCK_CATEGORY,
    publishedAt: '2025-01-01T00:00:00.000Z',
  },
  {
    id: 2, documentId: 'prod-2', name: 'Wireless Headphones', slug: 'wireless-headphones',
    price: 149, comparePrice: null, stock: 20, sku: 'WH-002', featured: true,
    excerpt: 'Premium sound quality',
    description: [{ type: 'paragraph', children: [{ type: 'text', text: 'Premium wireless headphones.' }] }],
    images: [{ id: 2, documentId: 'img-2', url: 'https://picsum.photos/seed/headphones/400/400', alternativeText: 'Wireless Headphones', width: 400, height: 400, formats: null }],
    category: MOCK_CATEGORY,
    publishedAt: '2025-01-02T00:00:00.000Z',
  },
  {
    id: 3, documentId: 'prod-3', name: 'Mechanical Keyboard', slug: 'mechanical-keyboard',
    price: 89, comparePrice: null, stock: 15, sku: 'MK-003', featured: false,
    excerpt: 'Tactile typing experience',
    description: [{ type: 'paragraph', children: [{ type: 'text', text: 'Best mechanical keyboard.' }] }],
    images: null,
    category: MOCK_CATEGORY,
    publishedAt: '2025-01-03T00:00:00.000Z',
  },
];

const MOCK_ARTICLES = [
  {
    id: 1, documentId: 'art-1', title: 'Top 10 Electronics of 2025', slug: 'top-10-electronics-2025',
    excerpt: 'Discover the best gadgets this year.',
    content: [{ type: 'paragraph', children: [{ type: 'text', text: 'Content here.' }] }],
    cover: null, author: { id: 1, username: 'admin', email: 'admin@example.com' },
    publishedAt: '2025-01-10T00:00:00.000Z', tags: [],
  },
  {
    id: 2, documentId: 'art-2', title: 'How to Choose the Right Laptop', slug: 'choose-right-laptop',
    excerpt: 'A complete buying guide.',
    content: [{ type: 'paragraph', children: [{ type: 'text', text: 'Guide content.' }] }],
    cover: null, author: null, publishedAt: '2025-01-15T00:00:00.000Z', tags: [],
  },
  {
    id: 3, documentId: 'art-3', title: 'Wireless Audio Revolution', slug: 'wireless-audio',
    excerpt: 'Everything about wireless headphones.',
    content: [{ type: 'paragraph', children: [{ type: 'text', text: 'Audio content.' }] }],
    cover: null, author: null, publishedAt: '2025-01-20T00:00:00.000Z', tags: [],
  },
];

function paginate(data, url) {
  const params = new URL(`http://x${url}`).searchParams;
  const page = parseInt(params.get('pagination[page]') || '1');
  const pageSize = parseInt(params.get('pagination[pageSize]') || '12');
  const start = (page - 1) * pageSize;
  const sliced = data.slice(start, start + pageSize);
  return {
    data: sliced,
    meta: { pagination: { page, pageSize, pageCount: Math.ceil(data.length / pageSize), total: data.length } },
  };
}

function send(res, status, body) {
  const json = JSON.stringify(body);
  res.writeHead(status, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*' });
  res.end(json);
}

const server = http.createServer((req, res) => {
  const path = req.url.split('?')[0];

  if (req.method === 'OPTIONS') {
    res.writeHead(204, { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*' });
    return res.end();
  }

  // Products
  if (req.method === 'GET' && path === '/api/products') {
    const urlObj = new URL(`http://x${req.url}`);
    const featuredFilter = urlObj.searchParams.get('filters[featured][$eq]');
    const slugFilter = urlObj.searchParams.get('filters[slug][$eq]');
    let filtered = MOCK_PRODUCTS;
    if (featuredFilter === 'true') filtered = filtered.filter(p => p.featured);
    if (slugFilter) filtered = filtered.filter(p => p.slug === slugFilter);
    return send(res, 200, paginate(filtered, req.url));
  }

  // Categories
  if (req.method === 'GET' && path === '/api/categories') {
    return send(res, 200, { data: MOCK_CATEGORIES, meta: { pagination: { page: 1, pageSize: 25, pageCount: 1, total: 3 } } });
  }

  // Articles
  if (req.method === 'GET' && path === '/api/articles') {
    return send(res, 200, paginate(MOCK_ARTICLES, req.url));
  }

  // Single article
  if (req.method === 'GET' && path.startsWith('/api/articles/')) {
    const slug = path.split('/').pop();
    const article = MOCK_ARTICLES.find(a => a.slug === slug) || MOCK_ARTICLES[0];
    return send(res, 200, { data: article, meta: {} });
  }

  // Auth: Login
  if (req.method === 'POST' && path === '/api/auth/local') {
    let body = '';
    req.on('data', d => body += d);
    req.on('end', () => {
      try {
        const { identifier, password } = JSON.parse(body);
        if (identifier === 'test@example.com' && password === 'password123') {
          return send(res, 200, { jwt: 'mock-jwt-token', user: { id: 1, username: 'testuser', email: 'test@example.com' } });
        }
        return send(res, 400, { error: { status: 400, name: 'ValidationError', message: 'Invalid identifier or password' } });
      } catch {
        return send(res, 400, { error: { message: 'Invalid body' } });
      }
    });
    return;
  }

  // Auth: Register
  if (req.method === 'POST' && path === '/api/auth/local/register') {
    let body = '';
    req.on('data', d => body += d);
    req.on('end', () => {
      return send(res, 200, { jwt: 'mock-jwt-token', user: { id: 2, username: 'newuser', email: 'new@example.com' } });
    });
    return;
  }

  // Contact
  if (req.method === 'POST' && path === '/api/contacts') {
    let body = '';
    req.on('data', d => body += d);
    req.on('end', () => send(res, 200, { data: { id: 1 }, meta: {} }));
    return;
  }

  // Current user
  if (req.method === 'GET' && path === '/api/users/me') {
    const auth = req.headers['authorization'];
    if (auth && auth.includes('mock-jwt-token')) {
      return send(res, 200, { id: 1, username: 'testuser', email: 'test@example.com' });
    }
    return send(res, 401, { error: { message: 'Unauthorized' } });
  }

  // Search
  if (req.method === 'GET' && path === '/api/search') {
    return send(res, 200, { products: MOCK_PRODUCTS.slice(0, 2), articles: MOCK_ARTICLES.slice(0, 1) });
  }

  // Fallback
  send(res, 404, { error: { message: 'Not found' } });
});

const PORT = process.env.MOCK_STRAPI_PORT || 1999;
server.listen(PORT, () => {
  console.log(`Mock Strapi running on http://localhost:${PORT}`);
});
