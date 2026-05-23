import { globalSearch } from '@/lib/strapi';
import { ProductGrid } from '@/components/products/ProductGrid';
import { ArticleCard } from '@/components/blog/ArticleCard';

export const metadata = { title: 'Search — ShopGeneric' };

interface PageProps {
  searchParams: Promise<{ q?: string }>;
}

export default async function SearchPage({ searchParams }: PageProps) {
  const params = await searchParams;
  const query = params.q?.trim() ?? '';

  if (!query) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Search</h1>
        <p className="text-gray-500">Enter a search term in the bar above to find products and articles.</p>
      </div>
    );
  }

  const { products, articles } = await globalSearch(query);
  const total = products.length + articles.length;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">
        Results for &ldquo;{query}&rdquo;
      </h1>
      <p className="text-gray-500 text-sm mb-10">
        {total === 0 ? 'No results found.' : `${total} result${total !== 1 ? 's' : ''} found`}
      </p>

      {products.length > 0 && (
        <section className="mb-12">
          <h2 className="text-lg font-semibold text-gray-900 mb-5">
            Products ({products.length})
          </h2>
          <ProductGrid products={products} />
        </section>
      )}

      {articles.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-5">
            Articles ({articles.length})
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {articles.map((article) => (
              <ArticleCard key={article.id} article={article} />
            ))}
          </div>
        </section>
      )}

      {total === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-400 text-lg">Try a different search term.</p>
        </div>
      )}
    </div>
  );
}
