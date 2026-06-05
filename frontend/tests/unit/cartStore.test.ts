import { beforeEach, describe, expect, test } from 'vitest';
import { useCartStore } from '@/store/cartStore';

const item = {
  productId: 1,
  documentId: 'p1',
  name: 'MacBook Pro 14',
  slug: 'macbook-pro-14',
  price: 1999,
  image: null,
  quantity: 1,
};

describe('cartStore', () => {
  beforeEach(() => {
    localStorage.clear();
    useCartStore.setState({ items: [], isOpen: false });
  });

  test('adds an item and increments total values', () => {
    useCartStore.getState().addItem(item);

    expect(useCartStore.getState().items).toHaveLength(1);
    expect(useCartStore.getState().totalItems()).toBe(1);
    expect(useCartStore.getState().totalPrice()).toBe(1999);
  });

  test('adding same item merges quantity', () => {
    useCartStore.getState().addItem(item);
    useCartStore.getState().addItem({ ...item, quantity: 2 });

    expect(useCartStore.getState().items).toHaveLength(1);
    expect(useCartStore.getState().items[0].quantity).toBe(3);
  });

  test('updateQuantity removes item when quantity is <= 0', () => {
    useCartStore.getState().addItem(item);
    useCartStore.getState().updateQuantity(1, 0);

    expect(useCartStore.getState().items).toHaveLength(0);
  });

  test('setOpen and clearCart update state', () => {
    useCartStore.getState().addItem(item);
    useCartStore.getState().setOpen(true);

    expect(useCartStore.getState().isOpen).toBe(true);

    useCartStore.getState().clearCart();
    expect(useCartStore.getState().items).toHaveLength(0);
  });
});
