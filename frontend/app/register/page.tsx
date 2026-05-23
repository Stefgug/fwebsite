import { RegisterForm } from '@/components/auth/RegisterForm';

export const metadata = { title: 'Create Account — ShopGeneric' };

export default function RegisterPage() {
  return (
    <div className="min-h-[70vh] flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
          <h1 className="text-2xl font-bold text-gray-900 mb-1">Create your account</h1>
          <p className="text-gray-500 text-sm mb-6">Join ShopGeneric to start shopping</p>
          <RegisterForm />
        </div>
      </div>
    </div>
  );
}
