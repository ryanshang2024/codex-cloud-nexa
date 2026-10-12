import {redirect} from 'next/navigation';
import {currentIdentity} from '../../lib/session';
import Login from '../../components/Login';

export const metadata={title:'登录企业工作空间 · NEXA'};
export default async function SignIn(){
 const who=await currentIdentity();
 if(who)redirect(who.permissions.includes('leads.read')?'/admin':'/employee');
 return <Login/>;
}
