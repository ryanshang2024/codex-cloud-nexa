import {redirect} from 'next/navigation';
import {currentIdentity} from '../../lib/session';
import AdminWorkspace from '../../components/AdminWorkspace';
export default async function Admin(){const who=await currentIdentity();if(!who)redirect('/login');if(!who.permissions.includes('leads.read'))redirect('/employee');return <AdminWorkspace identity={who}/>}
