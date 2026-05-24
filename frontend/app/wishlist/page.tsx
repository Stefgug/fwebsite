'use client';

import Link from 'next/link';
import Image from 'next/image';
import { useWishlistStore } from '@/store/wishlistStore';
import { useCartStore } from '@/store/cartStore';
import { Button } from '@/components/ui/Button';

export default function WishlistPage() {
  const items = useWishlistStore((state) => state.items);
  const removeItem = useWishlistStore((state) => state.removeItem);
  const clearWishlist = useWishlistStore((state) => state.clearWishlist);
  const addToCart = useCartStore((state) => state.addItem);

  const handleMoveToCart = (productId: number) => {
    const item = items.find((i) => i.productId === productId);
    if (!item) return;
    addToCart({
      productId: item.productId,
      documentId: item.documentId,
      name: item.name,
      slug: item.slug,
      price: item.price,
      image: item.image,
      quantity: 1,
    });
    removeItem(productId);
  };

  if (items.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <h1 className="text-3xl font-bold text-gray-900 mb-4">My Wishlist</h1>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
          <svg
            className="w-16 h-16 text-gray-300 mx-auto mb-4"
            fill="none"
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
          <p className="text-gray-600 mb-6">Your wishlist is empty.</p>
          <Link href="/products">
            <Button>Browse Products</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold text-gray-900">
          My Wishlist <span className="text-gray-400 font-normal">({items.length})</span>
        </h1>
        <button
          onClick={clearWishlist}
          className="text-sm text-gray-500 hover:text-red-600 transition-colors"
        >
          Clear all
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {items.map((item) => (
          <div
            key={item.productId}
            className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow"
          >
            <Link href={`/products/${item.slug}`} className="block relative aspect-square bg-gray-100">
              {item.image ? (
                <Image src={item.image} alt={item.name} fill className="object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-gray-400">
                  <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                    />
                  </svg>
                </div>
              )}
            </Link>
            <div className="p-4">
              <Link
                href={`/products/${item.slug}`}
                className="block font-medium text-gray-900 hover:text-blue-600 transition-colors mb-2 line-clamp-2"
              >
                {item.name}
              </Link>
              <p className="text-lg font-semibold text-gray-900 mb-4">
                ${item.price.toFixed(2)}
              </p>
              <div className="flex gap-2">
                <Button
                  onClick={() => handleMoveToCart(item.productId)}
                  className="flex-1"
                  size="sm"
                >
                  Move to Cart
                </Button>
                <button
                  onClick={() => removeItem(item.productId)}
                  className="px-3 py-2 text-sm text-gray-500 hover:text-red-600 transition-colors"
                  aria-label="Remove from wishlist"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                    />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
