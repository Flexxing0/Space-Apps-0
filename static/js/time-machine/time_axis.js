/* Viewport temporal independiente de la cobertura de cualquier proveedor. */
'use strict';
window.EarthLensTimeAxis=Object.freeze({
  parse(value){const time=Date.parse(value.length===10?value+'T12:00:00Z':/[zZ]|[+-]\d{2}:\d{2}$/.test(value)?value:value+'Z');if(!Number.isFinite(time))throw new Error('Fecha inválida');return time;},
  iso(time){return new Date(time).toISOString().slice(0,16);},
  view(value,scale){const time=this.parse(value),span={hourly:2*864e5,daily:28*864e5,monthly:6*365.25*864e5,yearly:40*365.25*864e5}[scale];return {start:time-span*.35,end:time+span*.65};},
  position(value,view){return (this.parse(value)-view.start)/(view.end-view.start);},
  at(value,view,scale){const point=new Date(view.start+(view.end-view.start)*Number(value)/10000);point.setUTCMinutes(0,0,0);if(scale!=='hourly')point.setUTCHours(12);if(scale==='monthly'||scale==='yearly')point.setUTCDate(1);if(scale==='yearly')point.setUTCMonth(0);return point.toISOString().slice(0,16);},
  move(value,scale,direction){const point=new Date(this.parse(value)),day=point.getUTCDate();if(scale==='yearly'||scale==='monthly'){point.setUTCDate(1);if(scale==='yearly')point.setUTCFullYear(point.getUTCFullYear()+direction);else point.setUTCMonth(point.getUTCMonth()+direction);const last=new Date(Date.UTC(point.getUTCFullYear(),point.getUTCMonth()+1,0)).getUTCDate();point.setUTCDate(Math.min(day,last));}else if(scale==='daily')point.setUTCDate(day+direction);else point.setUTCHours(point.getUTCHours()+direction);return point.toISOString().slice(0,16);},
  zoom(view,value,factor){const cursor=this.parse(value),span=Math.max(12*36e5,Math.min(120*365.25*864e5,(view.end-view.start)*factor));return {start:cursor-span*.5,end:cursor+span*.5};}
});
