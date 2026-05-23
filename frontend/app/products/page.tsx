import { getProducts, getCategories } from '@/lib/strapi';
import { ProductGrid } from '@/components/products/ProductGrid';
import { Pagination } from '@/components/ui/Pagination';
import Link from 'next/link';
import { cn } from '@/lib/utils';

export const metadata = { title: 'Shop — ShopGeneric' };

interface PageProps {
  searchParams: Promise<{ category?: string; page?: string; q?: string }>;
}

export default async function ProductsPage({ searchParams }: PageProps) {
  const params = await searchParams;
  const categorySlug = params.category;
  const search = params.q;
  const page = Number(params.page ?? 1);

  const [productsRes, categories] = await Promise.all([
    getProducts({ page, categorySlug, search, pageSize: 12 }),
    getCategories(),
  ]);

  const { data: products, meta } = productsRes;

  function buildHref(p: number) {
    const qs = new URLSearchParams();
    if (categorySlug) qs.set('category', categorySlug);
    if (search) qs.set('q', search);
    qs.set('page', String(p));
    return `/products?${qs.toString()}`;
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="flex flex-col lg:flex-row gap-8">
        {/* Sidebar */}
        <aside className="lg:w-56 flex-shrink-0">
          <h2 className="font-semibold text-gray-900 mb-4 text-sm uppercase tracking-wider">Categories</h2>
          <ul className="space-y-1">
            <li>
              <Link
                href="/products"
                className={cn(
                  'block px-3 py-2 rounded-lg text-sm transition-colors',
                  !categorySlug ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-700 hover:bg-gray-100'
                )}
              >
                All Products ({meta.pagination.total})
              </Link>
            </li>
            {categories.map((cat) => (
              <li key={cat.id}>
                <Link
                  href={`/products?category=${cat.slug}`}
                  className={cn(
                    'block px-3 py-2 rounded-lg text-sm transition-colors',
                    categorySlug === cat.slug
                      ? 'bg-blue-50 text-blue-700 font-medium'
                      : 'text-gray-700 hover:bg-gray-100'
                  )}
                >
                  {cat.name}
                </Link>
              </li>
            ))}
          </ul>
        </aside>

        {/* Main content */}
        <div className="flex-1">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                {search ? `Results for "${search}"` : categorySlug ? categories.find((c) => c.slug === categorySlug)?.name ?? 'Products' : 'All Products'}
              </h1>
              <p className="text-sm text-gray-500 mt-1">{meta.pagination.total} products</p>
            </div>
          </div>

          <ProductGrid products={products} />

          <Pagination
            currentPage={page}
            pageCount={meta.pagination.pageCount}
            buildHref={buildHref}
          />
        </div>
      </div>
    </div>
  );
}
