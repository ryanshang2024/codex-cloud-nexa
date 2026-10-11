import {redirect} from 'next/navigation';
import {currentIdentity} from '../lib/session';
import Login from '../components/Login';
export default async function Home(){
 const who=await currentIdentity();
 if(who)redirect(who.permissions.includes('leads.read')?'/admin':'/employee');
 return <Login/>;
}
