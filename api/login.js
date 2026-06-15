// /api/login — validates credentials and sets auth cookie
// Single admin user: admin/admin
// Uses Web Crypto API (edge-compatible)

const USERS = {
  admin: '8da193366e1554c08b2870c50f737b9587c3372b656151c4a96028af26f51334', // sha256("admin:admin")
};

async function sha256hex(str) {
  const buf = await crypto.subtle.digest(
    'SHA-256',
    new TextEncoder().encode(str)
  );
  return Array.from(new Uint8Array(buf))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

export default async function handler(req) {
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'method not allowed' }), {
      status: 405,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  let body;
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: 'invalid json' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const { username, password } = body;

  if (!username || !password) {
    return new Response(JSON.stringify({ error: 'missing credentials' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const user = username.toLowerCase();
  const expectedHash = USERS[user];
  if (!expectedHash) {
    return new Response(JSON.stringify({ error: 'invalid credentials' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const actualHash = await sha256hex(`${user}:${password}`);

  if (actualHash !== expectedHash) {
    return new Response(JSON.stringify({ error: 'invalid credentials' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  // Auth valid — set cookie: "hash|username"
  const cookieValue = `${actualHash}|${user}`;

  return new Response(JSON.stringify({ ok: true, username: user }), {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
      'Set-Cookie': `auth=${cookieValue}; HttpOnly; Secure; SameSite=Strict; Max-Age=31536000; Path=/`,
    },
  });
}

export const config = {
  runtime: 'edge',
};
