import { createRemoteJWKSet, jwtVerify, SignJWT } from 'jose';
const googleKeys = createRemoteJWKSet(new URL('https://www.googleapis.com/oauth2/v3/certs'));
export const COOKIE = '__Secure-headline_session';
export function authReady(env) {
  return env.PUBLIC_HOST === 'headline.infinitas.top' && /^\d+-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com$/.test(env.GOOGLE_CLIENT_ID || '') &&
    typeof env.SESSION_SECRET === 'string' && env.SESSION_SECRET.length >= 32 && Boolean(env.ALLOWED_EMAIL && env.LOGIN_RATE_LIMITER);
}
export async function verifyGoogleCredential(token, env) {
  if (typeof token !== 'string' || token.length > 12000) throw new Error('Unauthorized');
  const {payload} = await jwtVerify(token, googleKeys, {issuer:['https://accounts.google.com','accounts.google.com'],
    audience:env.GOOGLE_CLIENT_ID, algorithms:['RS256'], requiredClaims:['exp','iat','sub','email']});
  if (payload.email_verified !== true || typeof payload.email !== 'string' || payload.email.toLowerCase() !== env.ALLOWED_EMAIL.toLowerCase() ||
      (payload.azp && payload.azp !== env.GOOGLE_CLIENT_ID)) throw new Error('Unauthorized');
  return payload;
}
export async function issueSession(identity, env) {
  return new SignJWT({email:identity.email.toLowerCase()}).setProtectedHeader({alg:'HS256',typ:'JWT'}).setSubject(identity.sub)
    .setIssuer('https://' + env.PUBLIC_HOST).setAudience('headline-translation').setIssuedAt().setExpirationTime('1h')
    .sign(new TextEncoder().encode(env.SESSION_SECRET));
}
export async function verifySession(request, env) {
  const token = request.headers.get('Cookie')?.split(';').map(c=>c.trim()).find(c=>c.startsWith(COOKIE+'='))?.slice(COOKIE.length+1);
  if (!token || token.length > 12000) throw new Error('Unauthorized');
  const {payload} = await jwtVerify(token,new TextEncoder().encode(env.SESSION_SECRET),{
    issuer:'https://' + env.PUBLIC_HOST,audience:'headline-translation',algorithms:['HS256'],requiredClaims:['exp','iat','sub','email']});
  if (payload.email !== env.ALLOWED_EMAIL.toLowerCase()) throw new Error('Unauthorized');
  return payload;
}
export const sessionCookie = token => `${COOKIE}=${token}; Path=/api/cloud; HttpOnly; Secure; SameSite=Strict; Max-Age=3600`;
export const clearCookie = () => `${COOKIE}=; Path=/api/cloud; HttpOnly; Secure; SameSite=Strict; Max-Age=0`;
