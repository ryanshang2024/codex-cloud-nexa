import {redirect} from 'next/navigation';
import {currentIdentity} from '../../lib/session';
import EmployeeWorkspace from '../../components/EmployeeWorkspace';
export default async function Employee(){const who=await currentIdentity();if(!who)redirect('/');return <EmployeeWorkspace identity={who}/>}
