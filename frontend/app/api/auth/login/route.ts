import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { strapiLogin } from '@/lib/strapi';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { jwt, user } = await strapiLogin(body);

    const cookieStore = await cookies();
    cookieStore.set('strapiToken', jwt, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 60 * 60 * 24 * 7,
      path: '/',
    });

    return NextResponse.json({ user });
  } catch (error) {
    return NextResponse.json(
      { message: error instanceof Error ? error.message : 'Login failed' },
      { status: 401 }
    );
  }
}
