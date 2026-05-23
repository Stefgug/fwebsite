import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { strapiRegister } from '@/lib/strapi';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { jwt, user } = await strapiRegister(body);

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
      { message: error instanceof Error ? error.message : 'Registration failed' },
      { status: 400 }
    );
  }
}
