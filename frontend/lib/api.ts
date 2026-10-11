export async function api(path:string,method='GET',body?:unknown){
 const r=await fetch('/api/'+path,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),cache:'no-store'});
 const data=await r.json();
 if(!r.ok){
  const detail=typeof data.detail==='string'?data.detail:'';
  const text=r.status===401?'请使用企业为你创建的个人账号登录。':
   r.status===403?'这项功能或客户资料尚未获得授权，请联系企业管理员。':
   r.status===404?'记录不存在或已撤回，请刷新当前工作。':
   r.status===429?'AI 用量、预算或并发已达到上限。普通工作记录仍可使用；需要提额时请提交申请。':
   detail.includes('Model/pricing')?'企业尚未启用 AI 模型或核对计费配置。':
   detail.includes('Voice provider')?'语音服务尚未接入，请使用文字记录。':
   detail.includes('context changed')?'任务资料或权限已更新，请刷新后重新操作。':
   detail.includes('Contact basis')?'此客户的联系依据需要管理端审核。':
   detail.includes('qualified customers')?'请先在管理端完成客户资料核验与评分，再分配工作。':
   detail || (r.status===422?'请检查表单内容和必填项。':'操作未完成，请稍后重试。');
  throw new Error(text);
 }
 return data;
}
