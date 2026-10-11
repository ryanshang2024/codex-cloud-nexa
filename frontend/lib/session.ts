import {cookies} from 'next/headers';
export async function currentIdentity(){
 const token=(await cookies()).get('nexa_session')?.value;
 if(!token)return null;
 try{const r=await fetch(`${process.env.NEXA_API_URL||'http://127.0.0.1:8000'}/api/identity`,{headers:{Authorization:`Bearer ${token}`},cache:'no-store',signal:AbortSignal.timeout(5000)});return r.ok?await r.json():null}
 catch{return null}
}
