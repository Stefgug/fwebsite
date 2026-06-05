import { beforeEach, describe, expect, test } from 'vitest';
import { useWishlistStore } from '@/store/wishlistStore';

const item = {
  productId: 1,
  documentId: 'p1',
  name: 'MacBook Pro 14',
  slug: 'macbook-pro-14',
  price: 1999,
  image: null,
};

describe('wishlistStore', () => {
  beforeEach(() => {
    localStorage.clear();
    useWishlistStore.setState({ items: [] });
  });

  test('addItem stores an entry with timestamp', () => {
    useWishlistStore.getState().addItem(item);

    const state = useWishlistStore.getState();
    expect(state.items).toHaveLength(1);
    expect(state.items[0].productId).toBe(1);
    expect(state.items[0].addedAt).toBeTypeOf('string');
  });

  test('addItem is idempotent for same product', () => {
    useWishlistStore.getState().addItem(item);
    useWishlistStore.getState().addItem(item);

    expect(useWishlistStore.getState().items).toHaveLength(1);
  });

  test('toggleItem adds then removes item', () => {
    useWishlistStore.getState().toggleItem(item);
    expect(useWishlistStore.getState().hasItem(1)).toBe(true);

    useWishlistStore.getState().toggleItem(item);
    expect(useWishlistStore.getState().hasItem(1)).toBe(false);
  });

  test('totalItems and clearWishlist work', () => {
    useWishlistStore.getState().addItem(item);
    expect(useWishlistStore.getState().totalItems()).toBe(1);

    useWishlistStore.getState().clearWishlist();
    expect(useWishlistStore.getState().totalItems()).toBe(0);
  });
});
