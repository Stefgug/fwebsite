import Link from 'next/link';

export function Footer() {
  return (
    <footer className="bg-gray-900 text-gray-300 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          <div className="col-span-1">
            <p className="font-bold text-xl text-white mb-2">ShopGeneric</p>
            <p className="text-sm text-gray-400">
              Your one-stop shop for electronics, clothing, books, and more.
            </p>
          </div>

          <div>
            <p className="font-semibold text-white mb-3 text-sm uppercase tracking-wider">Shop</p>
            <ul className="space-y-2 text-sm">
              <li><Link href="/products" className="hover:text-white transition-colors">All Products</Link></li>
              <li><Link href="/products?category=electronics" className="hover:text-white transition-colors">Electronics</Link></li>
              <li><Link href="/products?category=clothing" className="hover:text-white transition-colors">Clothing</Link></li>
              <li><Link href="/products?category=books" className="hover:text-white transition-colors">Books</Link></li>
            </ul>
          </div>

          <div>
            <p className="font-semibold text-white mb-3 text-sm uppercase tracking-wider">Company</p>
            <ul className="space-y-2 text-sm">
              <li><Link href="/blog" className="hover:text-white transition-colors">Blog</Link></li>
              <li><Link href="/contact" className="hover:text-white transition-colors">Contact</Link></li>
              <li><Link href="/account" className="hover:text-white transition-colors">My Account</Link></li>
            </ul>
          </div>

          <div>
            <p className="font-semibold text-white mb-3 text-sm uppercase tracking-wider">Support</p>
            <ul className="space-y-2 text-sm">
              <li><Link href="/contact" className="hover:text-white transition-colors">Help Center</Link></li>
              <li><span className="text-gray-500">Returns & Refunds</span></li>
              <li><span className="text-gray-500">Shipping Info</span></li>
            </ul>
          </div>
        </div>

        <div className="mt-8 pt-8 border-t border-gray-700 text-sm text-gray-500 text-center">
          © {new Date().getFullYear()} ShopGeneric. Generic test site — not a real store.
        </div>
      </div>
    </footer>
  );
}
