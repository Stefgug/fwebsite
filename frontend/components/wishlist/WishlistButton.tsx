'use client';

import { useWishlistStore, type WishlistItem } from '@/store/wishlistStore';
import { cn } from '@/lib/utils';

interface WishlistButtonProps {
  product: Omit<WishlistItem, 'addedAt'>;
  className?: string;
  variant?: 'icon' | 'full';
}

export function WishlistButton({ product, className, variant = 'icon' }: WishlistButtonProps) {
  const hasItem = useWishlistStore((state) => state.hasItem(product.productId));
  const toggleItem = useWishlistStore((state) => state.toggleItem);

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    toggleItem(product);
  };

  if (variant === 'full') {
    return (
      <button
        onClick={handleClick}
        className={cn(
          'inline-flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors',
          hasItem
            ? 'bg-pink-50 border-pink-200 text-pink-700 hover:bg-pink-100'
            : 'bg-white border-gray-200 text-gray-700 hover:border-pink-300 hover:text-pink-600',
          className
        )}
        aria-label={hasItem ? 'Remove from wishlist' : 'Add to wishlist'}
      >
        <svg
          className="w-5 h-5"
          fill={hasItem ? 'currentColor' : 'none'}
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"
          />
        </svg>
        <span className="text-sm font-medium">
          {hasItem ? 'In your wishlist' : 'Add to wishlist'}
        </span>
      </button>
    );
  }

  return (
    <button
      onClick={handleClick}
      className={cn(
        'p-2 rounded-full transition-colors',
        hasItem
          ? 'bg-pink-100 text-pink-600 hover:bg-pink-200'
          : 'bg-white/80 text-gray-600 hover:bg-pink-50 hover:text-pink-600',
        className
      )}
      aria-label={hasItem ? 'Remove from wishlist' : 'Add to wishlist'}
    >
      <svg
        className="w-5 h-5"
        fill={hasItem ? 'currentColor' : 'none'}
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"
        />
      </svg>
    </button>
  );
}
