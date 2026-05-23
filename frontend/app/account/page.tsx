import { redirect } from 'next/navigation';
import { getCurrentUser } from '@/lib/auth';
import { formatPrice } from '@/lib/utils';

export const metadata = { title: 'My Account — ShopGeneric' };

const MOCK_ORDERS = [
  { id: 'ORD-8821', date: '2025-04-15', total: 249.98, status: 'Delivered', items: 2 },
  { id: 'ORD-7743', date: '2025-03-02', total: 89.99, status: 'Delivered', items: 1 },
  { id: 'ORD-6610', date: '2025-01-20', total: 174.97, status: 'Delivered', items: 3 },
];

export default async function AccountPage() {
  const user = await getCurrentUser();
  if (!user) redirect('/login?from=/account');

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-10">
      <h1 className="text-2xl font-bold text-gray-900 mb-8">My Account</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Profile */}
        <div className="bg-white rounded-2xl border border-gray-200 p-6 h-fit">
          <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <span className="text-2xl font-bold text-blue-600">
              {user.username.charAt(0).toUpperCase()}
            </span>
          </div>
          <h2 className="text-center font-semibold text-gray-900 mb-1">{user.username}</h2>
          <p className="text-center text-sm text-gray-500 mb-6">{user.email}</p>

          <div className="space-y-2 text-sm">
            <div className="flex justify-between py-2 border-b border-gray-100">
              <span className="text-gray-500">Member since</span>
              <span className="font-medium text-gray-900">Jan 2025</span>
            </div>
            <div className="flex justify-between py-2 border-b border-gray-100">
              <span className="text-gray-500">Total orders</span>
              <span className="font-medium text-gray-900">{MOCK_ORDERS.length}</span>
            </div>
            <div className="flex justify-between py-2">
              <span className="text-gray-500">Total spent</span>
              <span className="font-medium text-gray-900">
                {formatPrice(MOCK_ORDERS.reduce((s, o) => s + o.total, 0))}
              </span>
            </div>
          </div>
        </div>

        {/* Orders */}
        <div className="lg:col-span-2">
          <h2 className="font-semibold text-gray-900 mb-4">Order History</h2>
          <div className="space-y-3">
            {MOCK_ORDERS.map((order) => (
              <div key={order.id} className="bg-white rounded-xl border border-gray-200 p-5">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <p className="font-semibold text-gray-900 text-sm">{order.id}</p>
                    <p className="text-xs text-gray-500">
                      {new Date(order.date).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
                    </p>
                  </div>
                  <span className="text-xs font-medium bg-green-100 text-green-700 px-2.5 py-1 rounded-full">
                    {order.status}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-500">{order.items} item{order.items !== 1 ? 's' : ''}</span>
                  <span className="font-semibold text-gray-900">{formatPrice(order.total)}</span>
                </div>
              </div>
            ))}
          </div>

          <p className="text-xs text-gray-400 mt-4 text-center">
            Order history shown above is mock data for demonstration purposes.
          </p>
        </div>
      </div>
    </div>
  );
}
