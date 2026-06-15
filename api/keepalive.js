// Supabase keepalive — prevents free-tier pause from inactivity.
// Called daily by Vercel cron (see vercel.json).
export default async function handler(_req, res) {
  const url = process.env.SUPABASE_URL || "https://bccwauzfxxolgpdefdqy.supabase.co";
  const key = process.env.SUPABASE_ANON_KEY || "sb_publishable_tnf9vqJXcIpl6rT0o-pw8g_UYCYr0_h";
  try {
    const r = await fetch(`${url}/rest/v1/prospects?select=id&limit=1`, {
      headers: { apikey: key, Authorization: `Bearer ${key}` },
    });
    res.json({ ok: r.ok, status: r.status, ts: new Date().toISOString() });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message, ts: new Date().toISOString() });
  }
}
