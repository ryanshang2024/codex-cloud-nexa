import './globals.css';
import '../components/enterprise.css';
import '../components/employee-landing.css';
import RegisterWorkApp from '../components/RegisterWorkApp';
import '@fontsource/noto-sans/400.css';
import '@fontsource/noto-sans/600.css';
import '@fontsource/noto-sans-sc/400.css';
import '@fontsource/noto-sans-sc/600.css';
export const metadata = {title:'NEXA · Enterprise AI Work Platform',description:'Enterprise-managed AI resources, assigned tasks and evidence-based sales collaboration',icons:{icon:'/app-icons/192',apple:'/app-icons/192'},appleWebApp:{capable:true,title:'NEXA Work',statusBarStyle:'default' as const}};
export const viewport={themeColor:'#0B1F38'};
export default function Layout({children}:{children:React.ReactNode}) {
 return <html lang="zh-CN"><body><RegisterWorkApp/>{children}</body></html>;
}
