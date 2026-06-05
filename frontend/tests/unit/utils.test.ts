import { describe, expect, test } from 'vitest';
import { cn, formatPrice, truncate } from '@/lib/utils';

describe('utils', () => {
  test('formatPrice formats EUR in french locale', () => {
    expect(formatPrice(1999)).toBe('1 999,00 €');
  });

  test('cn joins truthy classes only', () => {
    expect(cn('a', undefined, false, 'b', null, 'c')).toBe('a b c');
  });

  test('truncate keeps short text unchanged', () => {
    expect(truncate('hello', 10)).toBe('hello');
  });

  test('truncate trims long text and appends ellipsis', () => {
    expect(truncate('hello world', 5)).toBe('hello…');
  });
});
