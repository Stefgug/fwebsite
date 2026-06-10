'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';
import { SearchBar } from '@/components/ui/SearchBar';
import { CartIcon } from '@/components/cart/CartIcon';
import { WishlistIcon } from '@/components/wishlist/WishlistIcon';
import { cn } from '@/lib/utils';

const navLinks = [
  { href: '/products', label: 'Shop' },
  { href: '/blog', label: 'Blog' },
  { href: '/contact', label: 'Contact' },
];

interface NavbarProps {
  user?: { username: string; email: string } | null;
}

export function Navbar({ user }: NavbarProps) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  async function handleLogout() {
    await fetch('/api/auth/logout', { method: 'POST' });
    window.location.href = '/';
  }

  return (
    <header className="sticky top-0 z-50 bg-white border-b border-gray-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 gap-4">
          {/* Logo */}
          <Link href="/" className="flex-shrink-0 font-bold text-xl text-blue-600 tracking-tight">
            ShopGeneric
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-6">
            {navLinks.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className={cn(
                  'text-sm font-medium transition-colors hover:text-blue-600',
                  pathname.startsWith(href) ? 'text-blue-600' : 'text-gray-600'
                )}
              >
                {label}
              </Link>
            ))}
          </nav>

          {/* Search */}
          <div className="hidden md:block flex-1 max-w-xs">
            <SearchBar placeholder="Search..." />
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <WishlistIcon />
            <CartIcon />

            {user ? (
              <div className="hidden md:flex items-center gap-2">
                <Link href="/account" className="text-sm text-gray-700 hover:text-blue-600 font-medium">
                  {user.username}
                </Link>
                <button
                  onClick={handleLogout}
                  className="text-sm text-gray-500 hover:text-red-600 transition-colors"
                >
                  Logout
                </button>
              </div>
            ) : (
              <div className="hidden md:flex items-center gap-2">
                <Link href="/login" className="text-sm font-medium text-gray-700 hover:text-blue-600">
                  Sign In
                </Link>
                <Link
                  href="/register"
                  className="text-sm font-medium bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Sign up
                </Link>
              </div>
            )}

            {/* Mobile menu button */}
            <button
              className="md:hidden p-2 text-gray-600 hover:text-gray-900"
              onClick={() => setMobileOpen(!mobileOpen)}
              aria-label="Toggle menu"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {mobileOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileOpen && (
          <div className="md:hidden py-4 border-t border-gray-200 space-y-3">
            <SearchBar className="mb-3" />
            {navLinks.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                onClick={() => setMobileOpen(false)}
                className="block text-sm font-medium text-gray-700 hover:text-blue-600 py-1"
              >
                {label}
              </Link>
            ))}
            {user ? (
              <>
                <Link href="/account" onClick={() => setMobileOpen(false)} className="block text-sm text-gray-700 py-1">
                  My Account ({user.username})
                </Link>
                <button onClick={handleLogout} className="block text-sm text-red-600 py-1">
                  Logout
                </button>
              </>
            ) : (
              <>
                <Link href="/wishlist" onClick={() => setMobileOpen(false)} className="block text-sm font-medium text-gray-700 py-1">
                  Wishlist
                </Link>
                <Link href="/login" onClick={() => setMobileOpen(false)} className="block text-sm font-medium text-gray-700 py-1">
                  Sign In
                </Link>
                <Link href="/register" onClick={() => setMobileOpen(false)} className="block text-sm font-medium text-blue-600 py-1">
                  Sign up
                </Link>
              </>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
