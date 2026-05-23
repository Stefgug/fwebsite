import { NextRequest, NextResponse } from 'next/server';
import { createContact } from '@/lib/strapi';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    await createContact(body);
    return NextResponse.json({ ok: true });
  } catch (error) {
    return NextResponse.json(
      { message: error instanceof Error ? error.message : 'Failed to send message' },
      { status: 500 }
    );
  }
}
