'use client';

import { useState } from 'react';
import { useCartStore } from '@/store/cartStore';
import { Button } from '@/components/ui/Button';
import type { Product } from '@/types';
import { getStrapiImageUrl } from '@/lib/strapi';
import toast from 'react-hot-toast';

interface AddToCartButtonProps {
  product: Product;
}

export function AddToCartButton({ product }: AddToCartButtonProps) {
  const addItem = useCartStore((state) => state.addItem);
  const [quantity, setQuantity] = useState(1);

  if (product.stock === 0) {
    return (
      <Button disabled variant="outline" size="lg" className="w-full">
        Out of Stock
      </Button>
    );
  }

  function handleAdd() {
    const firstImage = product.images?.[0];
    const imageUrl = firstImage ? getStrapiImageUrl(firstImage.formats?.small?.url ?? firstImage.url) : null;

    addItem({
      productId: product.id,
      documentId: product.documentId,
      name: product.name,
      slug: product.slug,
      price: product.price,
      image: imageUrl,
      quantity,
    });
    toast.success(`${product.name} added to cart`);
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <label htmlFor="qty" className="text-sm font-medium text-gray-700">Qty</label>
        <select
          id="qty"
          value={quantity}
          onChange={(e) => setQuantity(Number(e.target.value))}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {Array.from({ length: Math.min(product.stock, 10) }, (_, i) => i + 1).map((n) => (
            <option key={n} value={n}>{n}</option>
          ))}
        </select>
        <span className="text-sm text-gray-500">{product.stock} in stock</span>
      </div>
      <Button onClick={handleAdd} size="lg" className="w-full">
        Add to Cart
      </Button>
    </div>
  );
}
