import { ContactForm } from '@/components/contact/ContactForm';

export const metadata = { title: 'Contact Us — ShopGeneric' };

export default function ContactPage() {
  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-16">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-16">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 mb-3">Get in Touch</h1>
          <p className="text-gray-500 mb-8">
            Have a question about an order, a product, or need help? We are here for you.
            Fill in the form and we will get back to you within 24 hours.
          </p>

          <div className="space-y-5">
            {[
              { icon: '📧', label: 'Email', value: 'support@shopgeneric.com' },
              { icon: '📞', label: 'Phone', value: '+33 1 23 45 67 89' },
              { icon: '📍', label: 'Address', value: '123 Rue du Commerce, 75001 Paris, France' },
              { icon: '🕘', label: 'Hours', value: 'Mon–Fri, 9am–6pm CET' },
            ].map(({ icon, label, value }) => (
              <div key={label} className="flex items-start gap-3">
                <span className="text-xl flex-shrink-0 mt-0.5">{icon}</span>
                <div>
                  <p className="font-medium text-gray-900 text-sm">{label}</p>
                  <p className="text-gray-500 text-sm">{value}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-gray-200 p-8">
          <h2 className="font-semibold text-gray-900 mb-6">Send us a message</h2>
          <ContactForm />
        </div>
      </div>
    </div>
  );
}
