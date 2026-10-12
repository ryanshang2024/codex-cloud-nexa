import {ImageResponse} from 'next/og';
import {createElement} from 'react';
import {readFile} from 'node:fs/promises';
import {join} from 'node:path';

export async function GET(_request:Request,{params}:{params:Promise<{size:string}>}){
 const {size:value}=await params;
 if(!['192','512'].includes(value))return new Response('Unknown icon size',{status:404});
 const size=Number(value);const asset=await readFile(join(process.cwd(),'public','nexa-symbol.png'));
 const imageWidth=Math.round(size*.64);const imageHeight=Math.round(imageWidth*asset.readUInt32BE(20)/asset.readUInt32BE(16));
 return new ImageResponse(createElement('div',{style:{display:'flex',alignItems:'center',justifyContent:'center',width:'100%',height:'100%',background:'#FFFFFF',border:Math.round(size*.045)+'px solid #CFFADD',borderRadius:Math.round(size*.2)}},
  createElement('img',{src:'data:image/png;base64,'+asset.toString('base64'),width:imageWidth,height:imageHeight,alt:''})),
  {width:size,height:size,headers:{'Cache-Control':'public, max-age=86400'}});
}
