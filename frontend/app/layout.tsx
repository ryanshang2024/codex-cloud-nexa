import './globals.css';
import '../components/enterprise.css';
import '@fontsource/noto-sans/400.css';
import '@fontsource/noto-sans/600.css';
import '@fontsource/noto-sans-sc/400.css';
import '@fontsource/noto-sans-sc/600.css';
export const metadata = {title:'NEXA · Enterprise AI Work Platform',description:'Enterprise-managed AI resources, assigned tasks and evidence-based sales collaboration'};
export default function Layout({children}:{children:React.ReactNode}) {
 return <html lang="zh-CN"><body>{children}</body></html>;
}
