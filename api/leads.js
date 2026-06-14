// /api/leads — KV-backed leads storage (Upstash Redis)
// GET  → returns all leads from KV
// POST → saves full leads array to KV
// Falls back gracefully when env vars are not set.

import { Redis } from '@upstash/redis';

const KEY = 'bright_ent_leads_v1';

function getRedis() {
  // Accept either the Upstash-native names or the Vercel Marketplace KV_* names
  // that the Upstash for Redis Vercel integration provisions.
  const url = process.env.UPSTASH_REDIS_REST_URL || process.env.KV_REST_API_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN || process.env.KV_REST_API_TOKEN;
  if (!url || !token) return null;
  return new Redis({ url, token });
}

export default async function handler(req) {
  if (req.method === 'GET') {
    const redis = getRedis();
    if (!redis) {
      return new Response(JSON.stringify({
        leads: [],
        source: 'none',
        kvAvailable: false,
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    try {
      const data = await redis.get(KEY);
      const leads = Array.isArray(data) ? data : [];
      return new Response(JSON.stringify({
        leads,
        source: leads.length ? 'kv' : 'empty',
        kvAvailable: true,
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    } catch (err) {
      console.error('KV GET error:', err);
      return new Response(JSON.stringify({
        leads: [],
        source: 'none',
        kvAvailable: false,
        error: 'kv_read_failed',
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }
  }

  if (req.method === 'POST') {
    const redis = getRedis();
    if (!redis) {
      return new Response(JSON.stringify({
        error: 'kv_not_configured',
        kvAvailable: false,
      }), {
        status: 503,
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

    const { leads } = body || {};
    if (!Array.isArray(leads)) {
      return new Response(JSON.stringify({ error: 'leads array required' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    try {
      await redis.set(KEY, leads);
      return new Response(JSON.stringify({
        ok: true,
        count: leads.length,
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    } catch (err) {
      console.error('KV POST error:', err);
      return new Response(JSON.stringify({ error: 'kv_write_failed' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      });
    }
  }

  return new Response(JSON.stringify({ error: 'method not allowed' }), {
    status: 405,
    headers: { 'Content-Type': 'application/json' },
  });
}

export const config = {
  runtime: 'edge',
};
