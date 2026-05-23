import { notFound } from 'next/navigation';
import Image from 'next/image';
import Link from 'next/link';
import { getArticleBySlug } from '@/lib/strapi';
import { getStrapiImageUrl } from '@/lib/strapi';
import { RichTextRenderer } from '@/components/blog/RichTextRenderer';
import { Badge } from '@/components/ui/Badge';

interface PageProps {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { slug } = await params;
  const article = await getArticleBySlug(slug);
  if (!article) return { title: 'Article not found' };
  return {
    title: `${article.title} — ShopGeneric Blog`,
    description: article.excerpt ?? undefined,
  };
}

export default async function ArticleDetailPage({ params }: PageProps) {
  const { slug } = await params;
  const article = await getArticleBySlug(slug);
  if (!article) notFound();

  const coverUrl = article.cover
    ? getStrapiImageUrl(article.cover.formats?.large?.url ?? article.cover.url)
    : null;

  const date = new Date(article.publishedAt).toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric',
  });

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-10">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-gray-500 mb-8">
        <Link href="/" className="hover:text-blue-600">Home</Link>
        <span>/</span>
        <Link href="/blog" className="hover:text-blue-600">Blog</Link>
        <span>/</span>
        <span className="text-gray-900 font-medium truncate">{article.title}</span>
      </nav>

      {/* Tags */}
      {article.tags.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {article.tags.map((tag) => (
            <Link key={tag.id} href={`/blog?tag=${tag.slug}`}>
              <Badge variant="blue">{tag.name}</Badge>
            </Link>
          ))}
        </div>
      )}

      <h1 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4 leading-tight">
        {article.title}
      </h1>

      <div className="flex items-center gap-3 text-sm text-gray-500 mb-8">
        {article.author && (
          <span className="font-medium text-gray-700">{article.author.username}</span>
        )}
        <span>•</span>
        <time dateTime={article.publishedAt}>{date}</time>
      </div>

      {/* Cover image */}
      {coverUrl && (
        <div className="aspect-video relative rounded-2xl overflow-hidden mb-10 bg-gray-100">
          <Image
            src={coverUrl}
            alt={article.cover?.alternativeText ?? article.title}
            fill
            className="object-cover"
            priority
            sizes="(max-width: 768px) 100vw, 768px"
          />
        </div>
      )}

      {/* Excerpt */}
      {article.excerpt && (
        <p className="text-xl text-gray-600 mb-8 leading-relaxed border-l-4 border-blue-200 pl-4">
          {article.excerpt}
        </p>
      )}

      {/* Content */}
      <RichTextRenderer content={article.content} />

      <div className="mt-12 pt-8 border-t border-gray-200">
        <Link href="/blog" className="text-sm text-blue-600 hover:underline font-medium">
          &larr; Back to Blog
        </Link>
      </div>
    </div>
  );
}
