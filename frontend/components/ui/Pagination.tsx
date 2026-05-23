import Link from 'next/link';
import { cn } from '@/lib/utils';

interface PaginationProps {
  currentPage: number;
  pageCount: number;
  buildHref: (page: number) => string;
}

export function Pagination({ currentPage, pageCount, buildHref }: PaginationProps) {
  if (pageCount <= 1) return null;

  const pages = Array.from({ length: pageCount }, (_, i) => i + 1);

  return (
    <nav className="flex items-center justify-center gap-1 mt-8">
      {currentPage > 1 && (
        <Link
          href={buildHref(currentPage - 1)}
          className="px-3 py-2 text-sm rounded-lg border border-gray-300 hover:bg-gray-50 text-gray-700"
        >
          &larr; Prev
        </Link>
      )}
      {pages.map((page) => (
        <Link
          key={page}
          href={buildHref(page)}
          className={cn(
            'px-3 py-2 text-sm rounded-lg border',
            page === currentPage
              ? 'bg-blue-600 text-white border-blue-600'
              : 'border-gray-300 text-gray-700 hover:bg-gray-50'
          )}
        >
          {page}
        </Link>
      ))}
      {currentPage < pageCount && (
        <Link
          href={buildHref(currentPage + 1)}
          className="px-3 py-2 text-sm rounded-lg border border-gray-300 hover:bg-gray-50 text-gray-700"
        >
          Next &rarr;
        </Link>
      )}
    </nav>
  );
}
