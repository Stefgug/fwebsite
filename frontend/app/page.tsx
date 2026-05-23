import Link from 'next/link';
import { getFeaturedProducts, getArticles } from '@/lib/strapi';
import { ProductGrid } from '@/components/products/ProductGrid';
import { ArticleCard } from '@/components/blog/ArticleCard';
import { Button } from '@/components/ui/Button';

export default async function HomePage() {
  const [featuredProducts, articlesRes] = await Promise.all([
    getFeaturedProducts(),
    getArticles({ pageSize: 3 }),
  ]);

  return (
    <div>
      {/* Hero */}
      <section className="bg-gradient-to-br from-blue-600 to-blue-800 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 sm:py-32 text-center">
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold mb-6 leading-tight">
            Shop Smarter,<br className="hidden sm:block" /> Live Better
          </h1>
          <p className="text-lg sm:text-xl text-blue-100 mb-10 max-w-2xl mx-auto">
            Discover thousands of products across electronics, clothing, books, and more.
            Quality you can trust, prices you will love.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/products">
              <Button variant="secondary" size="lg" className="text-blue-900 font-semibold">
                Shop Now
              </Button>
            </Link>
            <Link href="/blog">
              <Button variant="outline" size="lg" className="border-white text-white hover:bg-white/10">
                Read Our Blog
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Features bar */}
      <section className="border-b border-gray-200 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
            {[
              { icon: '🚚', title: 'Free Shipping', desc: 'On orders over €50' },
              { icon: '↩️', title: 'Easy Returns', desc: '30-day return policy' },
              { icon: '🔒', title: 'Secure Payment', desc: 'SSL encrypted checkout' },
              { icon: '💬', title: '24/7 Support', desc: 'Always here to help' },
            ].map(({ icon, title, desc }) => (
              <div key={title} className="flex flex-col items-center gap-1">
                <span className="text-2xl">{icon}</span>
                <p className="font-semibold text-sm text-gray-900">{title}</p>
                <p className="text-xs text-gray-500">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Featured products */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Featured Products</h2>
            <p className="text-gray-500 mt-1">Our top picks just for you</p>
          </div>
          <Link href="/products" className="text-sm font-medium text-blue-600 hover:underline">
            View all &rarr;
          </Link>
        </div>
        <ProductGrid products={featuredProducts} />
      </section>

      {/* Category shortcuts */}
      <section className="bg-gray-50 py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-8 text-center">Shop by Category</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
            {[
              { slug: 'electronics', label: 'Electronics', emoji: '💻' },
              { slug: 'clothing', label: 'Clothing', emoji: '👕' },
              { slug: 'books', label: 'Books', emoji: '📚' },
              { slug: 'home-garden', label: 'Home & Garden', emoji: '🏡' },
              { slug: 'sports', label: 'Sports', emoji: '⚽' },
              { slug: 'toys', label: 'Toys', emoji: '🎮' },
            ].map(({ slug, label, emoji }) => (
              <Link
                key={slug}
                href={`/products?category=${slug}`}
                className="flex flex-col items-center gap-2 p-5 bg-white rounded-xl border border-gray-200 hover:border-blue-400 hover:shadow-sm transition-all group"
              >
                <span className="text-3xl">{emoji}</span>
                <span className="text-sm font-medium text-gray-700 group-hover:text-blue-600 text-center">{label}</span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Latest articles */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">From Our Blog</h2>
            <p className="text-gray-500 mt-1">Insights, news, and tips</p>
          </div>
          <Link href="/blog" className="text-sm font-medium text-blue-600 hover:underline">
            All articles &rarr;
          </Link>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {articlesRes.data.map((article) => (
            <ArticleCard key={article.id} article={article} />
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="bg-gray-900 text-white py-16">
        <div className="max-w-3xl mx-auto px-4 text-center">
          <h2 className="text-3xl font-bold mb-4">Ready to start shopping?</h2>
          <p className="text-gray-400 mb-8">Join thousands of happy customers and discover amazing products at great prices.</p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/register">
              <Button size="lg">Create Free Account</Button>
            </Link>
            <Link href="/products">
              <Button variant="outline" size="lg" className="border-gray-600 text-gray-300 hover:bg-gray-800">
                Browse Products
              </Button>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
