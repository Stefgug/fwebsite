import { notFound } from 'next/navigation';
import Image from 'next/image';
import { getProductBySlug } from '@/lib/strapi';
import { getStrapiImageUrl } from '@/lib/strapi';
import { formatPrice } from '@/lib/utils';
import { AddToCartButton } from '@/components/products/AddToCartButton';
import { Badge } from '@/components/ui/Badge';
import Link from 'next/link';

interface PageProps {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { slug } = await params;
  const product = await getProductBySlug(slug);
  if (!product) return { title: 'Product not found' };
  return { title: `${product.name} — ShopGeneric` };
}

export default async function ProductDetailPage({ params }: PageProps) {
  const { slug } = await params;
  const product = await getProductBySlug(slug);
  if (!product) notFound();

  const images = product.images ?? [];
  const firstImage = images[0];
  const mainImageUrl = firstImage
    ? getStrapiImageUrl(firstImage.formats?.large?.url ?? firstImage.url)
    : null;

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-gray-500 mb-8">
        <Link href="/" className="hover:text-blue-600">Home</Link>
        <span>/</span>
        <Link href="/products" className="hover:text-blue-600">Shop</Link>
        {product.category && (
          <>
            <span>/</span>
            <Link href={`/products?category=${product.category.slug}`} className="hover:text-blue-600">
              {product.category.name}
            </Link>
          </>
        )}
        <span>/</span>
        <span className="text-gray-900 font-medium">{product.name}</span>
      </nav>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
        {/* Images */}
        <div className="space-y-4">
          <div className="aspect-square bg-gray-100 rounded-2xl overflow-hidden relative">
            {mainImageUrl ? (
              <Image
                src={mainImageUrl}
                alt={firstImage?.alternativeText ?? product.name}
                fill
                className="object-cover"
                sizes="(max-width: 1024px) 100vw, 50vw"
                priority
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-gray-300">
                <svg className="w-24 h-24" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
            )}
          </div>
          {/* Thumbnails */}
          {images.length > 1 && (
            <div className="grid grid-cols-4 gap-2">
              {images.slice(0, 4).map((img) => (
                <div key={img.id} className="aspect-square bg-gray-100 rounded-lg overflow-hidden relative">
                  <Image
                    src={getStrapiImageUrl(img.formats?.thumbnail?.url ?? img.url)}
                    alt={img.alternativeText ?? product.name}
                    fill
                    className="object-cover"
                    sizes="25vw"
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Info */}
        <div className="space-y-6">
          {product.category && (
            <Link href={`/products?category=${product.category.slug}`}>
              <Badge variant="blue">{product.category.name}</Badge>
            </Link>
          )}

          <h1 className="text-3xl font-bold text-gray-900">{product.name}</h1>

          {product.sku && (
            <p className="text-sm text-gray-400">SKU: {product.sku}</p>
          )}

          {product.excerpt && (
            <p className="text-gray-600">{product.excerpt}</p>
          )}

          <div className="flex items-baseline gap-3">
            <span className="text-3xl font-bold text-gray-900">{formatPrice(product.price)}</span>
            {product.comparePrice && product.comparePrice > product.price && (
              <>
                <span className="text-xl text-gray-400 line-through">{formatPrice(product.comparePrice)}</span>
                <Badge variant="red">
                  -{Math.round((1 - product.price / product.comparePrice) * 100)}%
                </Badge>
              </>
            )}
          </div>

          <div className="border-t border-gray-200 pt-6">
            <AddToCartButton product={product} />
          </div>

          {/* Description */}
          {product.description && (
            <div className="border-t border-gray-200 pt-6">
              <h2 className="font-semibold text-gray-900 mb-3">Description</h2>
              <div className="text-sm text-gray-600 whitespace-pre-line leading-relaxed">
                {product.description}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
