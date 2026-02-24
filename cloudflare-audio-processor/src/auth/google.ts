/**
 * Google OAuth token verification with KV caching.
 *
 * Validates access tokens against Google's tokeninfo endpoint and caches
 * results in Cloudflare KV to avoid redundant API calls.
 */

import { AuthenticationError } from '../utils/errors.ts';

/** Cached token claims stored in KV. */
interface TokenClaims {
  readonly sub: string;
  readonly email: string;
}

/** Google tokeninfo response shape (partial -- only fields we use). */
interface GoogleTokenInfo {
  readonly sub?: string;
  readonly email?: string;
  readonly exp?: string;
  readonly error_description?: string;
}

/** KV cache TTL in seconds (1 hour). */
const CACHE_TTL_SECONDS = 3600;

/**
 * Validates a Google OAuth access token, using KV cache when available.
 *
 * Flow:
 * 1. Check KV cache for previously validated token
 * 2. If miss, call Google tokeninfo endpoint
 * 3. Verify required claims (sub, email) are present
 * 4. Cache valid result in KV with 1-hour TTL
 *
 * @param token - Google OAuth access token
 * @param cache - KV namespace for token caching
 * @returns User claims (sub and email)
 * @throws AuthenticationError if token is invalid or missing claims
 */
export async function validateGoogleToken(
  token: string,
  cache: KVNamespace,
): Promise<TokenClaims> {
  if (!token) {
    throw new AuthenticationError('Access token is required');
  }

  // Check KV cache first
  const cacheKey = `token:${token}`;
  const cached = await cache.get(cacheKey, 'json');

  if (cached) {
    return cached as TokenClaims;
  }

  // Cache miss -- validate with Google
  const claims = await fetchGoogleTokenInfo(token);

  // Cache valid result
  await cache.put(cacheKey, JSON.stringify(claims), {
    expirationTtl: CACHE_TTL_SECONDS,
  });

  return claims;
}

/**
 * Fetches and validates token claims from Google's tokeninfo endpoint.
 *
 * @param token - Google OAuth access token
 * @returns Validated claims
 * @throws AuthenticationError on invalid token or missing claims
 */
async function fetchGoogleTokenInfo(token: string): Promise<TokenClaims> {
  const url = `https://oauth2.googleapis.com/tokeninfo?access_token=${encodeURIComponent(token)}`;

  let response: Response;
  try {
    response = await fetch(url);
  } catch {
    throw new AuthenticationError('Failed to verify token with Google');
  }

  if (!response.ok) {
    throw new AuthenticationError('Invalid or expired access token');
  }

  const data = (await response.json()) as GoogleTokenInfo;

  if (!data.sub || !data.email) {
    throw new AuthenticationError('Token missing required claims (sub, email)');
  }

  return { sub: data.sub, email: data.email };
}
