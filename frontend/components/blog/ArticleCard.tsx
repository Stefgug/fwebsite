import Link from 'next/link';
import Image from 'next/image';
import type { Article } from '@/types';
import { getStrapiImageUrl } from '@/lib/strapi';
import { Badge } from '@/components/ui/Badge';

interface ArticleCardProps {
  article: Article;
}

export function ArticleCard({ article }: ArticleCardProps) {
  const coverUrl = article.cover
    ? getStrapiImageUrl(article.cover.formats?.medium?.url ?? article.cover.url)
    : null;

  const date = new Date(article.publishedAt).toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric',
  });

  return (
    <Link href={`/blog/${article.slug}`} className="group flex flex-col bg-white rounded-xl border border-gray-200 overflow-hidden hover:shadow-md transition-shadow">
      <div className="aspect-video bg-gray-100 relative overflow-hidden">
        {coverUrl ? (
          <Image
            src={coverUrl}
            alt={article.cover?.alternativeText ?? article.title}
            fill
            className="object-cover group-hover:scale-105 transition-transform duration-300"
            sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-gray-300">
            <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
            </svg>
          </div>
        )}
      </div>

      <div className="p-5 flex flex-col flex-1">
        {article.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-2">
            {article.tags.slice(0, 2).map((tag) => (
              <Badge key={tag.id} variant="blue">{tag.name}</Badge>
            ))}
          </div>
        )}

        <h3 className="text-base font-semibold text-gray-900 mb-2 line-clamp-2 group-hover:text-blue-600 transition-colors flex-1">
          {article.title}
        </h3>

        {article.excerpt && (
          <p className="text-sm text-gray-500 line-clamp-2 mb-3">{article.excerpt}</p>
        )}

        <div className="flex items-center justify-between text-xs text-gray-400 mt-auto pt-3 border-t border-gray-100">
          {article.author && <span>{article.author.username}</span>}
          <span>{date}</span>
        </div>
      </div>
    </Link>
  );
}
