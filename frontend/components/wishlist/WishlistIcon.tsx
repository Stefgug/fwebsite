'use client';

import Link from 'next/link';
import { useWishlistStore } from '@/store/wishlistStore';

export function WishlistIcon() {
  const totalItems = useWishlistStore((state) => state.totalItems());

  return (
    <Link
      href="/wishlist"
      className="relative p-2 text-gray-700 hover:text-pink-600 transition-colors"
      aria-label="Wishlist"
    >
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"
        />
      </svg>
      {totalItems > 0 && (
        <span className="absolute -top-1 -right-1 bg-pink-600 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center font-medium">
          {totalItems > 99 ? '99+' : totalItems}
        </span>
      )}
    </Link>
  );
}
