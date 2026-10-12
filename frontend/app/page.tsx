import type {Metadata} from 'next';
import EmployeeLanding from '../components/EmployeeLanding';

export const metadata:Metadata={
 title:'NEXA AI Work Assistant · 企业授权的员工工作空间',
 description:'从我的任务到工作助手、客户跟进与工作汇报。企业统一分配，员工高效执行，业务结果回到同一个平台。',
};
export default function Home(){return <EmployeeLanding/>}
