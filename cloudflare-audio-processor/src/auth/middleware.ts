/**
 * OAuth token validation middleware for Hono routes.
 *
 * Extracts Bearer token from Authorization header, validates via Google OAuth,
 * and sets user_id and email on the Hono context for downstream handlers.
 */

import type { Context, Next } from 'hono';
import type { Env } from '../env.d.ts';
import { validateGoogleToken } from './google.ts';
import { AuthenticationError } from '../utils/errors.ts';

/**
 * Hono middleware that enforces Google OAuth authentication.
 *
 * Expects: `Authorization: Bearer <token>` header.
 * Sets: `c.set("user_id", sub)` and `c.set("email", email)` on success.
 * Returns: 401 JSON on any authentication failure.
 */
export async function authMiddleware(
  c: Context<{ Bindings: Env; Variables: { user_id: string; email: string } }>,
  next: Next,
): Promise<Response | void> {
  const authHeader = c.req.header('Authorization');

  if (!authHeader) {
    return c.json({ error: 'Missing Authorization header' }, 401);
  }

  const parts = authHeader.split(' ');

  if (parts.length !== 2 || parts[0] !== 'Bearer') {
    return c.json({ error: 'Invalid Authorization header format' }, 401);
  }

  const token = parts[1];

  try {
    const claims = await validateGoogleToken(token, c.env.TOKEN_CACHE);
    c.set('user_id', claims.sub);
    c.set('email', claims.email);
  } catch (error) {
    if (error instanceof AuthenticationError) {
      return c.json({ error: error.message }, 401);
    }
    return c.json({ error: 'Authentication failed' }, 401);
  }

  await next();
}
