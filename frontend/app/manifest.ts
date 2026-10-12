import type {MetadataRoute} from 'next';

export default function manifest():MetadataRoute.Manifest{return {
 id:'/employee',name:'NEXA AI Work Assistant',short_name:'NEXA Work',lang:'zh-CN',
 description:'企业授权的员工工作空间：我的任务、工作辅助、客户跟进与工作汇报。',
 start_url:'/employee',scope:'/',display:'standalone',background_color:'#FAFBFC',theme_color:'#0B1F38',
 icons:[{src:'/app-icons/192',sizes:'192x192',type:'image/png',purpose:'any'},{src:'/app-icons/512',sizes:'512x512',type:'image/png',purpose:'any'}],
}}
