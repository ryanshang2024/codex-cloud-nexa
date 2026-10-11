import { NextRequest, NextResponse } from 'next/server';

async function proxy(request: NextRequest, context: {params: Promise<{path:string[]}>}) {
 const {path} = await context.params;
 if (path.some(p => p==='..' || !/^[a-zA-Z0-9_:-]+$/.test(p))) return new Response('Invalid path',{status:400});
 const origin=request.headers.get('origin');
 let workspaceOrigin:string;
 try {workspaceOrigin=new URL(process.env.NEXA_WORKSPACE_ORIGIN || 'http://127.0.0.1:3000').origin}
 catch {return Response.json({detail:'Workspace origin is not configured'},{status:503})}
 const allowedOrigins=process.env.NEXA_WORKSPACE_MODE==='local'?[workspaceOrigin,'http://localhost:3000']:[workspaceOrigin];
 if (origin && !allowedOrigins.includes(origin)) return Response.json({detail:'Cross-origin request rejected'},{status:403});
 if(path[0]==='webhooks')return Response.json({detail:'Service webhooks are not available through the employee BFF'},{status:403});
 const login=path.join('/')==='auth/login' && request.method==='POST';
 const logout=path.join('/')==='auth/logout' && request.method==='POST';
 const token=request.cookies.get('nexa_session')?.value;
 if(!login && !token)return Response.json({detail:'Sign in with your own enterprise identity'},{status:401});
 try {
   const response = await fetch(`${process.env.NEXA_API_URL || 'http://127.0.0.1:8000'}/api/${path.join('/')}${request.nextUrl.search}`, {
    method:request.method,headers:{...(token&&!login?{'Authorization':`Bearer ${token}`}:{ }),'Content-Type':'application/json'},
    body:['GET','HEAD'].includes(request.method)?undefined:await request.text(),cache:'no-store',signal:AbortSignal.timeout(30000)
   });
   const data=await response.arrayBuffer();
   if(login && response.ok){
    const result=JSON.parse(new TextDecoder().decode(data));
    const output=NextResponse.json({identity:result.identity,expires_at:result.expires_at},{headers:{'Cache-Control':'no-store'}});
    output.cookies.set('nexa_session',result.access_token,{httpOnly:true,sameSite:'lax',secure:process.env.NEXA_WORKSPACE_MODE!=='local',path:'/',maxAge:8*3600});
    return output;
   }
   if(logout){const output=NextResponse.json({signed_out:true});output.cookies.delete('nexa_session');return output}
   const headers:Record<string,string>={'Content-Type':response.headers.get('content-type') || 'application/json','Cache-Control':'no-store'};
   const disposition=response.headers.get('content-disposition');if(disposition)headers['Content-Disposition']=disposition;
   return new Response(data,{status:response.status,headers});
 } catch {return Response.json({detail:'Backend unavailable; check the API service'},{status:502});}
}
export const GET=proxy; export const POST=proxy; export const PATCH=proxy; export const PUT=proxy; export const DELETE=proxy;
