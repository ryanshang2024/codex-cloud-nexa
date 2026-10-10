import './globals.css';
import '@fontsource/noto-sans/400.css';
import '@fontsource/noto-sans/600.css';
import '@fontsource/noto-sans-sc/400.css';
import '@fontsource/noto-sans-sc/600.css';
export const metadata = {title:'NEXA · Sales Intelligence',description:'Evidence-first HVAC sales workspace for Québec and Ontario'};
export default function Layout({children}:{children:React.ReactNode}) {
 return <html lang="zh-CN"><body>{children}</body></html>;
}
