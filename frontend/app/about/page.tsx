import Link from 'next/link';
import { Button } from '@/components/ui/Button';

export const metadata = {
  title: 'About — ShopGeneric',
  description: 'Learn more about ShopGeneric, our mission, and the team behind the store.',
};

const stats = [
  { value: '50K+', label: 'Happy customers' },
  { value: '1,200+', label: 'Products in catalog' },
  { value: '24/7', label: 'Customer support' },
  { value: '4.8/5', label: 'Average rating' },
];

const values = [
  {
    title: 'Quality first',
    description:
      'Every product in our catalog is carefully selected and tested. We only ship what we would buy ourselves.',
  },
  {
    title: 'Fair pricing',
    description:
      'No hidden fees, no inflated markups. We negotiate directly with manufacturers to offer competitive prices.',
  },
  {
    title: 'Customer-first',
    description:
      '30-day returns, real human support, and a satisfaction guarantee on every order.',
  },
];

export default function AboutPage() {
  return (
    <div className="bg-white">
      {/* Hero */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
        <div className="max-w-3xl">
          <h1 className="text-4xl sm:text-5xl font-bold text-gray-900 tracking-tight mb-6">
            About ShopGeneric
          </h1>
          <p className="text-lg text-gray-600 leading-relaxed">
            We started ShopGeneric in 2018 with a simple idea: online shopping should
            be fast, transparent, and enjoyable. Today we serve thousands of customers
            across the world with a curated catalog of products we genuinely believe in.
          </p>
        </div>
      </section>

      {/* Stats */}
      <section
        aria-labelledby="stats-heading"
        className="bg-gray-50 border-y border-gray-200"
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <h2 id="stats-heading" className="sr-only">
            ShopGeneric in numbers
          </h2>
          <dl className="grid grid-cols-2 lg:grid-cols-4 gap-8">
            {stats.map((stat) => (
              <div key={stat.label} className="text-center">
                <dt className="text-sm font-medium text-gray-500 mb-2">{stat.label}</dt>
                <dd className="text-3xl sm:text-4xl font-bold text-blue-600">{stat.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      {/* Values */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="max-w-2xl mb-12">
          <h2 className="text-3xl font-bold text-gray-900 mb-4">Our values</h2>
          <p className="text-gray-600">
            Three principles that guide every decision we make at ShopGeneric.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {values.map((value) => (
            <article
              key={value.title}
              className="p-6 rounded-lg border border-gray-200 bg-white hover:border-blue-300 transition-colors"
            >
              <h3 className="text-lg font-semibold text-gray-900 mb-3">{value.title}</h3>
              <p className="text-sm text-gray-600 leading-relaxed">{value.description}</p>
            </article>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="bg-blue-600">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">Ready to start shopping?</h2>
          <p className="text-blue-100 mb-8 max-w-xl mx-auto">
            Browse our full catalog or reach out if you have any questions.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/products">
              <Button variant="secondary" size="lg">
                Browse Products
              </Button>
            </Link>
            <Link href="/contact">
              <Button variant="outline" size="lg">
                Contact Us
              </Button>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
