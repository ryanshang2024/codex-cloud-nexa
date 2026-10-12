import {createHash,timingSafeEqual} from 'node:crypto';
import {NextRequest,NextResponse} from 'next/server';

const loopback=new Set(['127.0.0.1','localhost','[::1]']);

function unavailable() {
 return NextResponse.json({detail:'Workspace access is not configured'},{status:503,
  headers:{'Cache-Control':'no-store','X-Robots-Tag':'noindex, nofollow'}});
}

// Optional private-demo perimeter; every API still requires its own user session.
export function proxy(request:NextRequest) {
 const mode=process.env.NEXA_WORKSPACE_MODE || 'private_demo';
 let host:string;
 try {host=new URL('https://'+request.headers.get('host')).host} catch {return unavailable()}
 if(mode==='local') {
  try {if(loopback.has(new URL('http://'+request.headers.get('host')).hostname))return NextResponse.next()} catch {}
  return unavailable();
 }
 if(mode!=='private_demo' && mode!=='saas')return unavailable();
 let origin:URL;
 try {origin=new URL(process.env.NEXA_WORKSPACE_ORIGIN || '')} catch {return unavailable()}
 const user=process.env.NEXA_DEMO_AUTH_USERNAME;
 const password=process.env.NEXA_DEMO_AUTH_PASSWORD;
 if(origin.protocol!=='https:' || loopback.has(origin.hostname) || origin.username || origin.password
    || origin.pathname!=='/' || origin.search || origin.hash)return unavailable();
 if(host!==origin.host)return NextResponse.json({detail:'Workspace hostname rejected'},{status:400,headers:{'Cache-Control':'no-store'}});
 if(mode==='saas')return NextResponse.next();
 // Public product content/install assets contain no identity or customer data.
 const path=request.nextUrl.pathname;
 const publicPage=['/','/work-assistant','/manifest.webmanifest','/work-assistant-sw.js','/nexa-logo.png','/nexa-symbol.png','/nexa-hero-forest.mp4'].includes(path);
 if(publicPage||/^\/app-icons\/(192|512)$/.test(path)||path.startsWith('/_next/static/'))return NextResponse.next();
 if(!user || user.includes(':') || !password)return unavailable();
 const authorization=request.headers.get('authorization') || '';
 const expected=createHash('sha256').update(user+':'+password).digest();
 let authenticated=false;
 if(/^Basic [A-Za-z0-9+/]+={0,2}$/.test(authorization)) {
  const encoded=authorization.slice(6);
  const decoded=Buffer.from(encoded,'base64');
  if(decoded.toString('base64')===encoded)authenticated=timingSafeEqual(expected,createHash('sha256').update(decoded).digest());
 }
 if(!authenticated)return NextResponse.json({detail:'Sign in to the NEXA demo'},{status:401,
  headers:{'WWW-Authenticate':'Basic realm="NEXA Demo", charset="UTF-8"','Cache-Control':'no-store',
   'X-Robots-Tag':'noindex, nofollow'}});
 const response=NextResponse.next();
 response.headers.set('Cache-Control','private, no-store');
 response.headers.set('X-Robots-Tag','noindex, nofollow');
 return response;
}

export const config={matcher:'/:path*'};
