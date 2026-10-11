export function workKind(kind:string){
 return ({follow_up:'客户跟进',reply_report_review:'回复核验',quote_review:'报价审核',project_review:'项目跟进',technical_review:'技术事项审核',partner_review:'合作资质审核'} as Record<string,string>)[kind]||'分配工作';
}
export function workStatus(status:string){return ({open:'待处理',done:'已完成',cancelled:'已取消'} as Record<string,string>)[status]||'待处理';}
