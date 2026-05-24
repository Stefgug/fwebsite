'use client';

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

export interface WishlistItem {
  productId: number;
  documentId: string;
  name: string;
  slug: string;
  price: number;
  image: string | null;
  addedAt: string;
}

interface WishlistState {
  items: WishlistItem[];
  addItem: (item: Omit<WishlistItem, 'addedAt'>) => void;
  removeItem: (productId: number) => void;
  toggleItem: (item: Omit<WishlistItem, 'addedAt'>) => void;
  clearWishlist: () => void;
  hasItem: (productId: number) => boolean;
  totalItems: () => number;
}

export const useWishlistStore = create<WishlistState>()(
  persist(
    (set, get) => ({
      items: [],

      addItem: (item) => {
        set((state) => {
          if (state.items.some((i) => i.productId === item.productId)) {
            return state;
          }
          return {
            items: [...state.items, { ...item, addedAt: new Date().toISOString() }],
          };
        });
      },

      removeItem: (productId) => {
        set((state) => ({
          items: state.items.filter((i) => i.productId !== productId),
        }));
      },

      toggleItem: (item) => {
        const exists = get().items.some((i) => i.productId === item.productId);
        if (exists) {
          get().removeItem(item.productId);
        } else {
          get().addItem(item);
        }
      },

      clearWishlist: () => set({ items: [] }),

      hasItem: (productId) => get().items.some((i) => i.productId === productId),

      totalItems: () => get().items.length,
    }),
    {
      name: 'fwebsite-wishlist',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ items: state.items }),
    }
  )
);
