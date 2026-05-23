import { getArticles, getTags } from '@/lib/strapi';
import { ArticleCard } from '@/components/blog/ArticleCard';
import { Pagination } from '@/components/ui/Pagination';
import Link from 'next/link';
import { cn } from '@/lib/utils';

export const metadata = { title: 'Blog — ShopGeneric' };

interface PageProps {
  searchParams: Promise<{ tag?: string; page?: string }>;
}

export default async function BlogPage({ searchParams }: PageProps) {
  const params = await searchParams;
  const tagSlug = params.tag;
  const page = Number(params.page ?? 1);

  const [articlesRes, tags] = await Promise.all([
    getArticles({ page, tagSlug, pageSize: 9 }),
    getTags(),
  ]);

  const { data: articles, meta } = articlesRes;

  function buildHref(p: number) {
    const qs = new URLSearchParams();
    if (tagSlug) qs.set('tag', tagSlug);
    qs.set('page', String(p));
    return `/blog?${qs.toString()}`;
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Blog</h1>
        <p className="text-gray-500">Insights, news, and stories from our team</p>
      </div>

      {/* Tag filters */}
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-8">
          <Link
            href="/blog"
            className={cn(
              'px-4 py-1.5 rounded-full text-sm font-medium border transition-colors',
              !tagSlug ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 border-gray-300 hover:border-blue-400'
            )}
          >
            All
          </Link>
          {tags.map((tag) => (
            <Link
              key={tag.id}
              href={`/blog?tag=${tag.slug}`}
              className={cn(
                'px-4 py-1.5 rounded-full text-sm font-medium border transition-colors',
                tagSlug === tag.slug
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white text-gray-700 border-gray-300 hover:border-blue-400'
              )}
            >
              {tag.name}
            </Link>
          ))}
        </div>
      )}

      {articles.length === 0 ? (
        <div className="text-center py-16 text-gray-500">No articles found.</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {articles.map((article) => (
            <ArticleCard key={article.id} article={article} />
          ))}
        </div>
      )}

      <Pagination
        currentPage={page}
        pageCount={meta.pagination.pageCount}
        buildHref={buildHref}
      />
    </div>
  );
}
