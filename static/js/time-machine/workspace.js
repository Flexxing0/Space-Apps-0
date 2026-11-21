/* EarthLens: un único estado geográfico y temporal para todo el mapa. */
'use strict';
document.addEventListener('DOMContentLoaded', async () => {
  const $=id=>document.getElementById(id);
  const params=new URLSearchParams(location.search), Time=window.EarthLensTimeAxis;
  const state={
    city_id:params.get('city_id')||document.body.dataset.city||'comodoro-rivadavia',
    variable:params.get('variable')||'T2M',provider:params.get('provider')||'power',
    date:params.get('date')||Time.iso(Date.now()),scale:params.get('scale')||'daily',
    start:params.get('start')||'2000-01-01',end:params.get('end')||'2024-12-31',
    mode:params.get('mode')||'date',panel:document.body.dataset.panel||null,selected:[]
  };
  let cities=[],catalog=[],record=null,frame=null,comparisonRecords=[],chart=null,radial=null,versionChart=null;
  let activeHistoryId=null,activeEventId=null,controller=null,seq=0,timer=null,loadTimer=null;
  let calendarDate=new Date(Time.parse(state.date)),user=null,csrf=null,events=[],notificationRows=[],notificationEventFilter=null;
  let incidents=[],allIncidents=[],drawing=false,vertices=[],polygon=null,view=Time.view(state.date,state.scale);
  const pointLayers=new Map(),pointFrames=new Map(),cache=new Map();
  const map=L.map('map',{zoomControl:true}).setView([-45.88,-67.52],8);
  const markers=L.layerGroup().addTo(map),eventMarkers=L.layerGroup().addTo(map),incidentMarkers=L.layerGroup().addTo(map);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
    maxZoom:18,attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map);
  const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const number=v=>v==null?'—':new Intl.NumberFormat('es-AR',{maximumFractionDigits:2}).format(v);
  const variableNames={T2M:'Temperatura',T2M_MAX:'Temperatura máxima',T2M_MIN:'Temperatura mínima',
    PRECTOTCORR:'Precipitación',RH2M:'Humedad relativa',WS2M:'Viento',
    temperature_2m:'Temperatura',relative_humidity_2m:'Humedad relativa',precipitation:'Precipitación',
    precipitation_probability:'Probabilidad de lluvia',wind_speed_10m:'Viento',wind_gusts_10m:'Ráfagas',
    cloud_cover:'Nubosidad',apparent_temperature:'Sensación térmica',visibility:'Visibilidad',wind_direction_10m:'Dirección del viento'};
  const labels={forecast:'PRONÓSTICO',historical_gridded_product:'HISTÓRICO',reanalysis:'HISTÓRICO · REANÁLISIS',
    climatology_reference:'CLIMATOLOGÍA',unavailable:'SIN DATOS'};

  function notice(message,error=false){$('notice').textContent=message;$('notice').title=message;$('notice').classList.toggle('error',error);}
  async function api(path,options={}){
    const response=await fetch(path,{credentials:'same-origin',...options,
      headers:{'Content-Type':'application/json',...(csrf?{'X-CSRF-Token':csrf}:{}),...(options.headers||{})}});
    const body=await response.json();
    if(!response.ok){const error=new Error(body.error?.message||'Solicitud no disponible');error.code=body.error?.code;throw error;}
    return body.data;
  }
  function safe(fn){return async(...args)=>{try{await fn(...args);}catch(error){if(error.name!=='AbortError')notice(error.message,true);}};}
  function queryContext(){
    const query=new URLSearchParams({city_id:state.city_id,variable:state.variable,provider:state.provider,
      date:state.date,scale:state.scale,start:state.start,end:state.end,mode:state.mode});
    history.replaceState(null,'','?'+query);
    document.body.dataset.date=state.date;document.body.dataset.city=state.city_id;
    document.body.dataset.variable=state.variable;
  }
  function panel(name){
    document.body.classList.toggle('inspector-open',!!name);
    if(state.panel!==name)$('inspector').scrollTop=0;
    if(!name){$('inspector').hidden=true;state.panel=null;return;}
    state.panel=name;$('inspector').hidden=false;
    const titles={data:'Datos de la selección',profile:'Perfil de ciudad',calendar:'Calendario',
      events:'Mi espacio · eventos privados',notifications:'Notificaciones',impact:'Impactos y evidencia'};
    $('drawer-title').textContent=titles[name]||'Información';
    document.querySelectorAll('.panel').forEach(p=>p.hidden=p.id!=='panel-'+name);
    document.querySelectorAll('button[data-panel]').forEach(b=>b.classList.toggle('active',b.dataset.panel===name));
    if(name==='profile')safe(profile)();
    if(name==='calendar')calendar();
    if(name==='events'||name==='notifications')safe(loadAccount)();
    if(name==='impact')safe(impact)();
    requestAnimationFrame(()=>{chart?.resize();radial?.resize();versionChart?.resize();});
  }
  document.querySelectorAll('button[data-panel]').forEach(b=>b.onclick=()=>{if(b.dataset.panel==='notifications')notificationEventFilter=null;panel(b.dataset.panel);});
  $('close-inspector').onclick=()=>panel(null);
  function tools(open){$('tools').hidden=!open;$('toggle-tools').setAttribute('aria-expanded',String(open));}
  $('toggle-tools').onclick=()=>tools($('tools').hidden);
  $('close-tools').onclick=()=>tools(false);
  document.addEventListener('keydown',event=>{if(event.key==='Escape'){panel(null);tools(false);}});

  function selectedCities(){
    const city=cities.find(c=>c.id===state.city_id);if(!city)return [];
    const type=$('territory').value;
    if(type==='province')return cities.filter(c=>c.province===city.province);
    if(type==='region')return cities.filter(c=>c.region===city.region);
    if(type==='multi'||type==='polygon')return cities.filter(c=>state.selected.includes(c.id));
    return [city];
  }
  function renderMap(){
    markers.clearLayers();pointLayers.clear();
    const selected=new Set(selectedCities().map(c=>c.id));
    for(const city of cities){
      const row=pointFrames.get(city.id),value=row?.focus?.value;
      const active=city.id===state.city_id;
      let marker;
      if(selected.has(city.id)&&row){
        marker=L.marker([city.latitude,city.longitude],{zIndexOffset:active?1000:10,
          icon:L.divIcon({className:'observation-marker',iconSize:[76,34],iconAnchor:[38,17],
            html:`<span class="point-value ${escape(row.kind)}${active?' selected':''}">${number(value)}${value!=null?' '+escape(row.focus.unit):''}</span>`})});
      }else marker=L.circleMarker([city.latitude,city.longitude],{radius:active?7:4,color:selected.has(city.id)?'#7ef0d5':'#a1aeb5',
        fillColor:selected.has(city.id)?'#256b60':'#718591',fillOpacity:.8,weight:active?2:1});
      marker.bindTooltip(escape(city.name)+(row?' · '+escape(labels[row.kind]||row.kind):' · ubicación GeoRef, sin consulta para esta fecha'));
      marker.on('click',()=>{
        if($('territory').value==='multi'){
          state.selected=state.selected.includes(city.id)?state.selected.filter(id=>id!==city.id):[...state.selected,city.id];
          state.mode='compare';$('mode').value='compare';renderMap();safe(load)();panel('data');
        }else{selectCity(city.id);panel('data');}
      });
      marker.addTo(markers);pointLayers.set(city.id,marker);
    }
    $('selection-label').textContent=selected.size+' ubicación(es) seleccionada(s) · puntos consultados, sin interpolación';
  }
  function selectCity(id,{fetchData=true}={}){
    const city=cities.find(c=>c.id===id);if(!city)return;
    state.city_id=id;$('city').value=id;$('search').value=city.name;
    $('location-name').textContent=city.name+' · '+city.province;
    $('event-city').textContent='Ubicación: '+city.name+' · centroide GeoRef, no sitio exacto.';
    map.flyTo([city.latitude,city.longitude],Math.max(map.getZoom(),7),{duration:.35});
    incidents=allIncidents.filter(i=>i.city_id===id);renderIncidents();renderMap();queryContext();
    if(fetchData)scheduleLoad(0);
    if(state.panel==='profile')safe(profile)();
  }
  function variables(){
    const previous=state.variable;
    let choices=catalog.filter(r=>r.provider===state.provider);
    if(['power','power-daily','forecast','era5'].includes(state.provider)){
      choices=catalog.filter(r=>r.provider==='power');
      choices.push(...['precipitation_probability','wind_gusts_10m','cloud_cover','apparent_temperature','visibility','wind_direction_10m'].map(variable=>({variable,name:variableNames[variable]})));
      if(!choices.some(r=>r.variable===previous)&&variableNames[previous])choices.push({variable:previous,name:variableNames[previous]});
    }
    choices=choices.filter((r,i,a)=>a.findIndex(x=>x.variable===r.variable)===i);
    $('variable').innerHTML=choices.map(r=>`<option value="${escape(r.variable)}">${escape(variableNames[r.variable]||r.name||r.variable)}</option>`).join('');
    state.variable=choices.some(r=>r.variable===previous)?previous:choices[0]?.variable;
    $('variable').value=state.variable||'';
  }

  function updateAxis(){
    const percent=Time.position(state.date,view);$('scrubber').value=Math.round(Math.max(0,Math.min(1,percent))*10000);
    $('scrubber').dataset.start=String(view.start);$('scrubber').dataset.end=String(view.end);
    $('scrubber').setAttribute('aria-valuetext',state.date+' UTC');
    $('date').value=state.date.length===10?state.date+'T12:00':state.date.slice(0,16);
    $('time-current').textContent=new Date(Time.parse(state.date)).toLocaleString('es-AR',{timeZone:'UTC',day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
    $('time-start').textContent=new Date(view.start).toISOString().slice(0,10);
    $('time-end').textContent=new Date(view.end).toISOString().slice(0,10);
    const now=(Date.now()-view.start)/(view.end-view.start),split=Math.max(0,Math.min(1,now));
    const today=new Date();today.setUTCHours(0,0,0,0);const horizon=(+today+16*864e5-view.start)/(view.end-view.start);
    const forecastEnd=Math.max(split,Math.max(0,Math.min(1,horizon)));
    $('axis-past').style.width=split*100+'%';$('axis-future').style.width=(forecastEnd-split)*100+'%';
    $('axis-climate').style.width=(1-forecastEnd)*100+'%';
    $('axis-now').hidden=now<0||now>1;$('axis-now').style.left=split*100+'%';
    const formatter=new Intl.DateTimeFormat('es-AR',view.end-view.start>730*864e5?{year:'numeric',timeZone:'UTC'}:
      view.end-view.start>60*864e5?{month:'short',year:'2-digit',timeZone:'UTC'}:{day:'numeric',month:'short',timeZone:'UTC'});
    $('axis-ticks').innerHTML=Array.from({length:7},(_,i)=>'<span>'+escape(formatter.format(view.start+(view.end-view.start)*i/6))+'</span>').join('');
    renderTimelineMarkers();
  }
  function updateTime(value,options={}){
    if(value)state.date=Time.iso(Time.parse(value));
    const position=Time.position(state.date,view);
    if(options.center||position<0||position>1)view=Time.view(state.date,state.scale);
    calendarDate=new Date(Time.parse(state.date));updateAxis();calendar();queryContext();
    if($('profile-date'))$('profile-date').value=state.date.slice(0,10);
    if(options.fetch!==false)scheduleLoad(options.delay??0);
  }
  function scheduleLoad(delay=100){
    clearTimeout(loadTimer);controller?.abort();seq++;
    pointFrames.clear();frame=null;record=null;activeValue();renderMap();
    document.body.dataset.frameReady='false';$('inspector').setAttribute('aria-busy','true');
    $('map-value').textContent='Consultando '+(variableNames[state.variable]||state.variable)+'…';
    loadTimer=setTimeout(()=>safe(load)(),delay);
  }
  function activeValue(){
    const value=frame?.focus?.value,unit=frame?.focus?.unit||'';
    $('value').textContent=number(value);$('value-unit').textContent=unit;
    $('map-value').textContent=number(value)+(value!=null?' '+unit:' · sin dato para esta fecha');
    const kind=frame?.kind||'unavailable';$('time-kind').className='kind-label '+kind;
    $('time-kind').textContent=kind==='forecast'&&Math.abs(Time.parse(state.date)-Date.now())<36e5?'AHORA · PRONÓSTICO':labels[kind]||kind;
    $('data-kind').textContent=labels[kind]||kind;$('data-title').textContent=variableNames[state.variable]||state.variable;
    if(kind==='climatology_reference')$('map-value').textContent=number(value)+' '+unit+' · referencia mensual';
  }
  function plot(rows){
    if(chart)chart.destroy();chart=null;
    const available=rows.filter(row=>row.series?.length);if(!available.length)return;
    const datasets=available.map((row,index)=>({
      label:(row.location?.name||state.city_id)+' · '+row.unit,
      data:row.series.map(p=>({x:Time.parse(p.date),y:p.value})),
      borderColor:index?'#e3b879':row.kind==='forecast'?'#c4a3ff':'#63d2b8',
      borderDash:row.kind==='forecast'?[6,4]:[],pointRadius:row.series.length>100?0:2,spanGaps:false,tension:0
    }));
    const positions=datasets.flatMap(d=>d.data.map(p=>p.x)),min=Math.min(...positions),max=Math.max(...positions);
    chart=new Chart($('chart'),{type:'line',data:{datasets},plugins:[{id:'temporalCursor',afterDatasetsDraw(chart){
      const pixel=chart.scales.x.getPixelForValue(Time.parse(state.date));
      if(pixel<chart.chartArea.left||pixel>chart.chartArea.right)return;
      const context=chart.ctx;context.save();context.strokeStyle='#f0ce91';context.setLineDash([3,3]);context.beginPath();
      context.moveTo(pixel,chart.chartArea.top);context.lineTo(pixel,chart.chartArea.bottom);context.stroke();context.restore();
    }}],options:{responsive:true,maintainAspectRatio:false,animation:false,parsing:false,
      scales:{x:{type:'linear',min,max:max===min?max+36e5:max,ticks:{color:'#9bb1bd',maxTicksLimit:4,callback:v=>new Date(v).toISOString().slice(0,record?.frequency==='hourly'?16:10)}},y:{ticks:{color:'#9bb1bd'}}},
      plugins:{legend:{labels:{color:'#9bb1bd',font:{size:10}}},tooltip:{callbacks:{title:items=>new Date(items[0].parsed.x).toISOString()}}}}});
  }
  async function obtain(id,signal){
    const selection={city_id:id,date:state.date,variable:state.variable,provider:state.provider,scale:state.scale,start:state.start,end:state.end,mode:state.mode};
    return api('/api/workspace/frame?'+new URLSearchParams(selection),{signal});
  }
  async function load(){
    clearTimeout(loadTimer);controller?.abort();controller=new AbortController();const signal=controller.signal,ticket=++seq;
    record=null;frame=null;comparisonRecords=[];pointFrames.clear();
    activeValue();renderMap();$('provenance').innerHTML='';$('comparison').innerHTML='';$('limits').textContent='';
    if(chart){chart.destroy();chart=null;}notice('Consultando ubicación y fecha…');
    try{
      const result=await obtain(state.city_id,signal);if(ticket!==seq)return;
      frame=result;record=result.record;pointFrames.set(state.city_id,result);
      document.body.dataset.frameDate=result.selection.date;document.body.dataset.frameVariable=result.selection.variable;
      document.body.dataset.frameKind=result.kind;document.body.dataset.frameReady='true';$('inspector').setAttribute('aria-busy','false');
      const rows=record?[record]:[],coverage=[];
      if(state.mode==='compare'){
        const selected=selectedCities().filter(c=>c.id!==state.city_id);
        for(const city of selected.slice(0,4)){
          try{
            const other=await obtain(city.id,signal);if(ticket!==seq)return;pointFrames.set(city.id,other);
            if(other.record&&record&&other.record.unit===record.unit&&other.record.product===record.product)rows.push(other.record);
            else coverage.push(city.name+': '+other.message);
          }catch(error){if(error.name==='AbortError')throw error;coverage.push(city.name+': '+error.message);}
        }
        if(selected.length>4)coverage.push('Gráfico limitado a cinco puntos; '+selectedCities().length+' ubicaciones seleccionadas. No se calcula una media regional.');
      }
      if(ticket!==seq)return;
      comparisonRecords=rows;activeValue();renderMap();plot(rows);queryContext();
      $('comparison').textContent=coverage.join(' ');
      const climate=result.climatology;
      const fields=record?[
        ['Fuente / producto',record.provider+' · '+record.product],['Frecuencia nativa',record.frequency],
        ['Resolución',JSON.stringify(record.spatial_resolution)],['Obtención UTC',record.fetched_at],
        ['Emisión',record.issued_at||'No informada por el endpoint; no se sustituye por la obtención'],
        ['Incertidumbre',record.uncertainty?.intervals?'Consultar intervalos del producto':'Sin intervalos provistos por esta fuente'],
        ['Muestra seleccionada',result.focus?.sample_date||'Sin muestra válida'],
        ['Cobertura de la extracción',record.series.length+' registros'],
        ['Acceso/licencia',record.license?.description||'Consultar procedencia del producto']
      ]:climate?[
        ['Fuente','NASA POWER · referencia mensual 2000–2024'],['Referencia',climate.count+' años para el mes '+climate.month],
        ['Unidad nativa',climate.unit],['Uso','Climatología mensual; no predice el tiempo del día seleccionado']
      ]:[];
      $('provenance').innerHTML=fields.map(([name,value])=>`<dt>${escape(name)}</dt><dd>${escape(value)}</dd>`).join('');
      $('limits').textContent=[result.message,...(record?.limitations||[])].join(' ');
      notice(result.message,result.status==='unavailable');
      if(state.mode==='trend'&&record?.product==='POWER_MONTHLY_AG'){
        try{
          const stats=await api('/api/workspace/trends?'+new URLSearchParams({city_id:state.city_id,variable:record.variable,start:state.start,end:state.end}),{signal});
          if(ticket!==seq)return;$('comparison').innerHTML='<p>Cambio por década: '+number(stats.statistics.change_per_decade)+' '+escape(record.unit)+'</p><p>p nominal: '+escape(stats.statistics.p_value)+'</p><p class="hint">Motor existente, provisional; sin ajuste de autocorrelación ni comparaciones múltiples. No demuestra causalidad.</p>';
        }catch(error){if(error.name==='AbortError')throw error;$('comparison').textContent=error.message;}
      }
      if(state.panel==='impact')await impact();
    }catch(error){
      if(ticket!==seq||error.name==='AbortError')return;
      frame={kind:'unavailable',focus:null,message:error.message};activeValue();pointFrames.set(state.city_id,frame);renderMap();
      notice(error.message,true);$('limits').textContent='El proveedor falló. No se presentan datos anteriores como actuales ni se inventa un pronóstico.';
    }
  }
  function range(){
    state.start=$('start').value;state.end=$('end').value;
    if(!state.start||!state.end||state.start>state.end){notice('Seleccioná un intervalo válido.',true);return;}
    state.mode='range';$('mode').value='range';
    const first=Time.parse(state.start),last=Time.parse(state.end)+864e5;
    view={start:first,end:last};state.date=Time.iso(first);$('range-controls').open=false;
    updateTime(state.date);panel('data');
  }
  function step(direction){updateTime(Time.move(state.date,state.scale,direction));}
  function stop(){clearInterval(timer);timer=null;$('play').textContent='▶';$('play').setAttribute('aria-label','Reproducir evolución temporal');}
  $('play').onclick=()=>{if(timer){stop();return;}$('play').textContent='Ⅱ';$('play').setAttribute('aria-label','Pausar evolución temporal');timer=setInterval(()=>step(+$('direction').value),+$('speed').value);};
  $('speed').onchange=()=>{if(timer){stop();$('play').click();}};
  $('step-back').onclick=()=>step(-1);$('step-next').onclick=()=>step(1);
  $('scrubber').oninput=()=>updateTime(Time.at($('scrubber').value,view,state.scale),{delay:140});
  $('scrubber').onchange=()=>scheduleLoad(0);
  $('date').onchange=()=>{stop();updateTime($('date').value,{center:true});};
  $('scale').onchange=()=>{state.scale=$('scale').value;view=Time.view(state.date,state.scale);updateTime();};
  $('zoom-in').onclick=()=>{view=Time.zoom(view,state.date,.5);updateAxis();};
  $('zoom-out').onclick=()=>{view=Time.zoom(view,state.date,2);updateAxis();};
  $('present').onclick=()=>{stop();state.mode='date';$('mode').value='date';state.scale='daily';$('scale').value='daily';updateTime(Time.iso(Date.now()),{center:true});};
  $('apply-range').onclick=range;
  $('city').onchange=()=>selectCity($('city').value);
  $('search').oninput=()=>{
    const query=$('search').value.trim().toLocaleLowerCase('es');
    const city=cities.find(c=>[c.name,c.name+', '+c.province,c.id].some(n=>n.toLocaleLowerCase('es')===query));
    if(city&&city.id!==state.city_id)selectCity(city.id);
  };
  $('source').onchange=()=>{state.provider=$('source').value;variables();scheduleLoad(0);};
  $('variable').onchange=()=>{state.variable=$('variable').value;queryContext();scheduleLoad(0);};
  $('mode').onchange=()=>{state.mode=$('mode').value;if(state.mode==='range')$('range-controls').open=true;safe(load)();panel('data');};
  $('advanced').onclick=event=>{event.preventDefault();state.mode='trend';$('mode').value='trend';state.scale='monthly';$('scale').value='monthly';updateTime(state.start,{center:true});panel('data');};
  $('incident-layer').onchange=()=>{$('incidents').hidden=!$('incident-layer').checked;renderEvents();};
  $('territory').onchange=()=>{
    state.selected=[state.city_id];const type=$('territory').value;
    $('territory-controls').textContent=type==='multi'?'Elegí ciudades en el mapa.':type==='polygon'?'Dibujá vértices y cerrá con doble clic.':'La provincia o región se selecciona a partir de la ciudad actual.';
    if(type==='province'||type==='region'){state.mode='compare';$('mode').value='compare';scheduleLoad(0);panel('data');}
    if(type==='polygon')$('draw').click();renderMap();
  };
  function inside(point,points){let yes=false;for(let i=0,j=points.length-1;i<points.length;j=i++){const a=points[i],b=points[j];if((a.lng>point.longitude)!==(b.lng>point.longitude)&&point.latitude<(b.lat-a.lat)*(point.longitude-a.lng)/(b.lng-a.lng)+a.lat)yes=!yes;}return yes;}
  $('draw').onclick=()=>{drawing=true;vertices=[];$('territory').value='polygon';map.doubleClickZoom.disable();notice('Marcá vértices; doble clic para cerrar. Se seleccionan centroides, no se valida territorio ni se promedian áreas.');};
  map.on('click',event=>{if(!drawing)return;vertices.push(event.latlng);if(polygon)map.removeLayer(polygon);polygon=L.polygon(vertices,{color:'#65d4bd',fillOpacity:.06}).addTo(map);});
  map.on('dblclick',()=>{if(!drawing||vertices.length<3)return;drawing=false;map.doubleClickZoom.enable();state.selected=cities.filter(c=>inside(c,vertices)).map(c=>c.id);state.mode='compare';$('mode').value='compare';renderMap();scheduleLoad(0);panel('data');});
  $('clear-draw').onclick=()=>{if(polygon)map.removeLayer(polygon);polygon=null;drawing=false;state.selected=[];renderMap();};

  function calendar(){
    const type=$('cal-view').value,first=new Date(calendarDate);
    first.setUTCDate(1);let count=type==='month'?new Date(Date.UTC(first.getUTCFullYear(),first.getUTCMonth()+1,0)).getUTCDate():type==='week'?7:1;
    if(type==='week')first.setUTCDate(calendarDate.getUTCDate()-((calendarDate.getUTCDay()+6)%7));
    if(type==='day')first.setUTCDate(calendarDate.getUTCDate());
    $('cal-title').textContent=calendarDate.toLocaleDateString('es-AR',{month:'long',year:'numeric',timeZone:'UTC'});
    $('calendar-jump').value=state.date.slice(0,10);$('calendar').classList.toggle('list',type==='list'||type==='day');
    if(type==='list'){
      $('calendar').innerHTML=events.filter(e=>e.status==='active').map(e=>`<button data-event="${e.id}">${escape(e.name)} · ${escape(e.start)}</button>`).join('')||'<p>Sin eventos guardados.</p>';
    }else{
      let html=type==='month'?['L','M','M','J','V','S','D'].map(d=>'<span class="hint">'+d+'</span>').join('')+'<span></span>'.repeat((first.getUTCDay()+6)%7):'';
      for(let i=0;i<count;i++){
        const day=new Date(first);day.setUTCDate(first.getUTCDate()+i);const iso=day.toISOString().slice(0,10);
        const associated=events.filter(e=>e.status==='active'&&e.start.slice(0,10)===iso);
        html+=`<button data-day="${iso}" class="${iso===state.date.slice(0,10)?'selected ':''}${associated.length?'has-event':''}">${day.getUTCDate()}${associated.map(e=>'<span class="day-caption">'+escape(e.name)+'</span>').join('')}</button>`;
      }
      $('calendar').innerHTML=html;
    }
    $('calendar').querySelectorAll('[data-day]').forEach(button=>button.onclick=()=>{
      updateTime(button.dataset.day,{center:true});
      const associated=events.find(e=>e.status==='active'&&e.start.slice(0,10)===button.dataset.day);
      if(associated)openEvent(associated.id);else prepareEvent();
    });
    $('calendar').querySelectorAll('[data-event]').forEach(button=>button.onclick=()=>openEvent(button.dataset.event));
  }
  $('cal-view').onchange=calendar;
  function moveCalendar(direction){const type=$('cal-view').value;if(type==='month'||type==='list'){calendarDate.setUTCDate(1);calendarDate.setUTCMonth(calendarDate.getUTCMonth()+direction);}else calendarDate.setUTCDate(calendarDate.getUTCDate()+direction*(type==='week'?7:1));calendar();}
  $('cal-prev').onclick=()=>moveCalendar(-1);$('cal-next').onclick=()=>moveCalendar(1);
  $('calendar-jump').onchange=()=>updateTime($('calendar-jump').value,{center:true});
  $('new-event').onclick=()=>{$('event-form').reset();prepareEvent();panel('events');};
  function investigate(incident){
    state.variable=incident.related_variable;state.provider='power';$('source').value='power';state.scale='daily';$('scale').value='daily';
    variables();selectCity(incident.city_id,{fetchData:false});updateTime(incident.start,{center:true});panel('data');
  }
  function renderIncidents(){
    $('incidents').innerHTML=incidents.map(i=>`<article class="card"><strong>${escape(i.name)}</strong><p>${escape(i.start)} / ${escape(i.end)}</p><p>${escape(i.description)}</p><a href="${escape(i.sources[0].url)}" target="_blank" rel="noopener">Fuente documentada</a> <button data-incident="${i.id}">Investigar</button></article>`).join('')||'<p class="hint">Sin acontecimientos documentados en el catálogo actual.</p>';
    $('incidents').querySelectorAll('[data-incident]').forEach(button=>button.onclick=()=>investigate(incidents.find(i=>i.id===button.dataset.incident)));
    renderEvents();
  }
  function renderTimelineMarkers(){
    const rows=[...events.filter(e=>e.status==='active').map(e=>({id:e.id,date:e.start,name:e.name,event:true})),
      ...($('incident-layer').checked?allIncidents:[]).map(i=>({id:i.id,date:i.start,name:i.name,event:false}))];
    $('time-markers').innerHTML=rows.filter(r=>Time.position(r.date,view)>=0&&Time.position(r.date,view)<=1).map(r=>
      `<button style="left:${Time.position(r.date,view)*100}%" class="${r.event?'event-mark':''}" data-${r.event?'event':'incident'}="${r.id}" title="${escape(r.name+' · '+r.date)}" aria-label="${escape(r.name+' · '+r.date)}">⚑</button>`).join('');
    $('time-markers').querySelectorAll('[data-event]').forEach(button=>button.onclick=()=>openEvent(button.dataset.event));
    $('time-markers').querySelectorAll('[data-incident]').forEach(button=>button.onclick=()=>investigate(allIncidents.find(i=>i.id===button.dataset.incident)));
  }
  function renderEvents(){
    eventMarkers.clearLayers();incidentMarkers.clearLayers();
    for(const event of events.filter(e=>e.status==='active')){
      const city=cities.find(c=>c.id===event.city_id);if(!city)continue;
      L.marker([city.latitude,city.longitude]).bindTooltip(escape(event.name)+' · '+escape(event.start)).on('click',()=>openEvent(event.id)).addTo(eventMarkers);
    }
    if($('incident-layer').checked)for(const incident of allIncidents){
      const city=cities.find(c=>c.id===incident.city_id);if(!city)continue;
      L.circleMarker([city.latitude,city.longitude],{radius:13,color:'#ddb06c',fill:false,weight:2,dashArray:'4 4'})
        .bindTooltip(escape(incident.name)+' · centroide, no extensión del impacto').on('click',()=>investigate(incident)).addTo(incidentMarkers);
    }
    renderTimelineMarkers();calendar();
  }
  async function openEvent(id){
    const event=events.find(e=>e.id===id)||await api('/api/events/'+id);activeEventId=id;
    document.body.classList.add('viewing-event');
    selectCity(event.city_id,{fetchData:false});state.scale='hourly';$('scale').value='hourly';updateTime(Time.iso(Time.parse(event.start)),{center:true});panel('events');
    // Reutiliza el mismo formulario CRUD, no una segunda página o calendario.
    const fields=$('event-form').elements;
    for(const key of ['id','name','description','activity','participants','transport','flexible_days','flexible_hours','location_label'])fields[key].value=event[key]??'';
    for(const key of ['start','end'])fields[key].value=event[key].slice(0,16);
    fields.outdoor.checked=event.outdoor;fields.notifications.checked=event.notifications;
    for(const key of ['min_temperature','max_temperature','max_probability','max_precipitation','max_wind','max_gust'])fields[key].value=event.preferences[key]??'';
    fields.require_official_alerts.checked=event.preferences.require_official_alerts!==false;
    $('event-form-title').textContent='Editar / reprogramar: '+event.name;
    $('event-editor').open=false;$('events-list').hidden=true;
    $('event-details').hidden=false;$('event-details').innerHTML='<button id="back-events">← Todos mis eventos</button><div class="event-details-head"><h2>'+escape(event.name)+'</h2><p>'+escape(event.city_id+' · '+event.start+' / '+event.end)+'</p><p class="hint">Centroide de ciudad; impacto espacial sin capas suficientes.</p></div>';
    $('back-events').onclick=()=>{activeEventId=null;document.body.classList.remove('viewing-event');$('events-list').hidden=false;$('event-details').hidden=true;$('assessment').innerHTML='';};
    try{await previewEvent();}catch(error){notice(error.message,true);}
    if(activeEventId!==id)return;
    const navigation=document.createElement('div');navigation.className='actions';
    navigation.innerHTML='<button id="event-history-open">Historial de cambios</button><button id="event-notifications-open">Notificaciones relacionadas</button>';
    $('event-details').append(navigation);
    $('event-history-open').onclick=()=>{const button=$('events-list').querySelector('[data-history="'+id+'"]');if(button)button.click();};
    $('event-notifications-open').onclick=()=>{notificationEventFilter=id;panel('notifications');};
  }

  async function profile(){const id=state.city_id,result=await api('/api/workspace/profiles/'+id);if(id!==state.city_id)return;$('profile-title').textContent=result.city.name;$('profile-content').innerHTML=`<p>${escape(result.city.province)} · ${escape(result.city.region)}</p><p class="hint">${result.city.latitude.toFixed(5)}, ${result.city.longitude.toFixed(5)} · centroide GeoRef. Metadatos generales: se muestran solo campos con fuente verificada.</p><h2>Climatología mensual · 2000–2024</h2><p class="hint">${escape(result.method)}</p>`+Object.entries(result.climatology).map(([code,row])=>row.months?`<details><summary>${escape(row.name)} · ${escape(row.unit)}</summary><table><tr><th>Mes</th><th>Media</th><th>Desvío</th><th>Años</th></tr>${row.months.map(m=>`<tr><td>${m.month}</td><td>${number(m.mean)}</td><td>${number(m.std_dev)}</td><td>${m.count}</td></tr>`).join('')}</table></details>`:'').join('')+`<p class="hint">${result.limitations.map(escape).join(' ')}</p><a class="button" href="/fingerprint?city_id=${id}">Fingerprint y tendencias ↗</a> <button id="profile-plan">Planificar actividad</button>`;$('profile-plan').onclick=()=>{prepareEvent();panel('events');};
    const general=document.createElement('div');const elevation=result.general.altitude;const image=result.general.image;
 general.innerHTML=(image?'<figure><img style="max-width:100%;height:auto;border-radius:8px" src="'+escape(image.image_url)+'" alt="'+escape(image.caption||image.title)+'" loading="lazy"><figcaption class="hint">'+escape(image.caption||image.title)+' / '+escape(image.author)+' / '+escape(image.license)+' <a target="_blank" rel="noopener" href="'+escape(image.source_url)+'">Fuente y licencia</a>. Imagen ilustrativa; no condiciones actuales.</figcaption></figure>':'<p class="hint">Sin fotografia geolocalizada con licencia verificada.</p>')+(elevation?'<p>Elevacion del centroide: '+number(elevation.value)+' m</p><p class="hint">Copernicus DEM GLO-90 / Open-Meteo, pixel de 90 m. '+escape(elevation.limitation)+' <a href="'+escape(elevation.source_url)+'" target="_blank" rel="noopener">Fuente</a> / <a href="'+escape(elevation.citation)+'" target="_blank" rel="noopener">Citar Copernicus</a></p>':'')+'<p class="hint">Poblacion: sin una fuente censal incorporada.</p>';
 $('profile-content').prepend(general);
 if(radial){radial.destroy();radial=null;}const extra=document.createElement('div');extra.innerHTML='<h2>Perfil climatológico estandarizado</h2><button id="radial-profile">Mostrar ejes Z y metodología</button><div id="radial-result"></div><h2>Fingerprint de tendencias</h2><button id="trend-profile">Ver seis indicadores originales</button><div id="trend-profile-result"></div>'+'<h2>Otras dimensiones verificadas</h2>'+result.native_variables.map(v=>'<p class="hint">'+escape(v.provider+' · '+v.variable+' · '+v.unit)+'</p>').join('')+'<h2>Earth Connections</h2><button id="connections">Explorar asociaciones</button><div id="connections-result"></div><h2>Earth Twins</h2><button id="twins">Buscar ciudades similares</button><div id="twins-result"></div>';$('profile-content').append(extra);
    $('radial-profile').onclick=safe(async()=>{const data=await api('/api/workspace/profiles/'+id+'/climatology-fingerprint');if(id!==state.city_id)return;$('radial-result').innerHTML='<div class="chart-wrap"><canvas id="climate-radial"></canvas></div><p class="hint">'+escape(data.method)+' '+data.limitations.map(escape).join(' ')+'</p>';const methodNote=$('radial-result').querySelector('p');if(methodNote){const detail=document.createElement('details');detail.innerHTML='<summary>Referencia, metodo y limites</summary>';methodNote.replaceWith(detail);detail.append(methodNote);}$('radial-profile').hidden=true;if(radial)radial.destroy();radial=new Chart($('climate-radial'),{type:'radar',data:{labels:data.axes.map(a=>a.variable),datasets:[{label:'Z climatológico · no salud ambiental',data:data.axes.map(a=>a.z_score),borderColor:'#65d4bd',backgroundColor:'#65d4bd22'}]},options:{responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{labels:{color:'#a7bbc8',font:{size:10}}},tooltip:{callbacks:{label:item=>{const a=data.axes[item.dataIndex];return 'Z '+number(a.z_score)+' ? original '+number(a.raw_mean)+' '+a.unit;}}}},scales:{r:{grid:{color:'#35465c'},angleLines:{color:'#35465c'},ticks:{display:true,color:'#b8c9d5',backdropColor:'transparent',font:{size:9}},pointLabels:{color:'#8fa9b9',font:{size:9}}}}}});});
    $('trend-profile').onclick=safe(async()=>{const data=await api('/api/fingerprint/'+id);if(id!==state.city_id)return;$('trend-profile-result').innerHTML=data.results.map(r=>'<article class="card"><strong>'+escape(r.variable)+'</strong><p>'+escape(r.scientific_status||r.status||'provisional')+'</p><p>Cambio por década: '+number(r.statistics?.change_per_decade)+' '+escape(r.unit)+'</p></article>').join('')+'<p class="hint">Motor original; sin corrección de autocorrelación ni comparaciones múltiples. Cero descubrimientos confirmados.</p>';});
    $('connections').onclick=safe(async()=>{const data=await api('/api/workspace/profiles/'+id+'/connections');if(id!==state.city_id)return;$('connections-result').innerHTML=data.pairs.map(p=>'<article class="card"><p>'+escape(p.x.variable+' / '+p.y.variable)+'</p><p>r descriptivo: '+number(p.pearson_r_descriptive)+' · '+p.n+' meses pareados</p><p class="hint">'+data.limitations.map(escape).join(' ')+'</p></article>').join('')||'Sin pares compatibles.';});
    $('twins').onclick=safe(async()=>{const data=await api('/api/workspace/profiles/'+id+'/twins');if(id!==state.city_id)return;$('twins-result').innerHTML='<p class="hint">'+escape(data.method)+'</p>'+data.rows.slice(0,5).map(r=>'<p>'+escape(cities.find(c=>c.id===r.city_id)?.name||r.city_id)+' ? distancia '+number(r.distance)+'</p>').join('')+'<p class="hint">'+data.limitations.map(escape).join(' ')+'</p>';});
    const context=document.createElement('section');context.innerHTML='<h2>Acontecimientos documentados</h2>'+ $('incidents').innerHTML + '<h2>Viajar en esta ciudad</h2><label>Fecha UTC<input id="profile-date" type="date" value="'+state.date.slice(0,10)+'"></label><button id="profile-forecast">Ver pronostico disponible</button><button id="profile-impacts">Vulnerabilidades y limites</button><p class="hint">Planificacion turistica: usar la climatologia mensual como referencia, revisar el pronostico operativo y configurar los criterios de cada actividad. Sin garantia de seguridad.</p>';
    $('profile-content').append(context);
    context.querySelectorAll('[data-incident]').forEach(button=>button.onclick=()=>investigate(incidents.find(i=>i.id===button.dataset.incident)));
    $('profile-date').onchange=()=>{updateTime($('profile-date').value,{center:true});panel('data');};
    $('profile-forecast').onclick=()=>{updateTime(Time.iso(Date.now()),{center:true});panel('data');};
    $('profile-impacts').onclick=()=>panel('impact');
    const photoFigure=general.querySelector('figure');
    if(photoFigure){photoFigure.style.margin='0 0 10px';const image=photoFigure.querySelector('img');image.style.height='150px';image.style.objectFit='contain';image.style.width='100%';}
    const geography=document.createElement('details');geography.innerHTML='<summary>Geografia y fuentes del punto</summary>';
    for(const child of [...general.children])if(child!==photoFigure)geography.append(child);
    general.append(geography);
    const radialSection=document.createElement('section');radialSection.className='profile-radial';radialSection.innerHTML='<h2>Earth Fingerprint climatologico</h2>';
    radialSection.append($('radial-profile'),$('radial-result'));$('profile-content').insertBefore(radialSection,general.nextSibling);
    $('radial-profile').click();

}

  function prepareEvent(){activeEventId=null;document.body.classList.remove('viewing-event');$('event-editor').open=true;$('events-list').hidden=false;$('event-details').hidden=true;$('assessment').innerHTML='';const f=$('event-form');f.elements.id.value='';f.elements.start.value=state.date.slice(0,10)+'T10:00';f.elements.end.value=state.date.slice(0,10)+'T12:00';$('event-form-title').textContent='Planificar actividad';}
  function eventPayload(){const f=$('event-form').elements,prefs={};for(const k of ['min_temperature','max_temperature','max_probability','max_precipitation','max_wind','max_gust'])if(f[k].value!=='')prefs[k]=Number(f[k].value);prefs.require_official_alerts=f.require_official_alerts.checked;return {name:f.name.value,description:f.description.value,activity:f.activity.value,city_id:state.city_id,location_label:f.location_label.value,start:f.start.value+':00-03:00',end:f.end.value+':00-03:00',participants:+f.participants.value,transport:f.transport.value,outdoor:f.outdoor.checked,flexible_days:+f.flexible_days.value,flexible_hours:+f.flexible_hours.value,preferences:prefs,notifications:f.notifications.checked};}
  async function loadAccount(){const me=await api('/api/session');user=me.user;csrf=me.csrf_token;$('auth').hidden=!!user;$('account').hidden=!user;$('events-list').hidden=!!activeEventId;if(!user){events=[];$('badge').textContent='';$('events-list').textContent='';$('event-form').reset();$('notifications-list').textContent='Iniciá sesión en Mi espacio.';return;}$('account-name').textContent=user.username;events=await api('/api/events');$('events-list').innerHTML=events.map(e=>`<article class="card"><strong>${escape(e.name)}</strong><p>${escape(e.start)} · ${escape(e.status)}</p><div class="actions"><button data-edit="${e.id}">Editar</button><button data-cancel="${e.id}">Cancelar</button><button data-delete="${e.id}">Eliminar</button><button data-history="${e.id}">Evaluaciones</button><a class="button" href="/api/events/${e.id}/report.pdf">PDF</a></div></article>`).join('')||'<p>Sin eventos guardados.</p>';$('events-list').querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>{const e=events.find(e=>e.id===b.dataset.edit);activeEventId=e.id;selectCity(e.city_id,{fetchData:false});updateTime(Time.iso(Time.parse(e.start)),{center:true});const f=$('event-form').elements;for(const k of ['id','name','description','activity','participants','transport','flexible_days','flexible_hours','location_label'])f[k].value=e[k]??'';for(const k of ['start','end'])f[k].value=e[k].slice(0,16);f.outdoor.checked=e.outdoor;f.notifications.checked=e.notifications;for(const k of ['min_temperature','max_temperature','max_probability','max_precipitation','max_wind','max_gust'])f[k].value=e.preferences[k]??'';f.require_official_alerts.checked=e.preferences.require_official_alerts!==false;$('event-editor').open=true;$('event-form-title').textContent='Editar / reprogramar evento';});$('events-list').querySelectorAll('[data-delete]').forEach(b=>b.onclick=safe(async()=>{if(confirm('¿Eliminar este evento y su historial?')){await api('/api/events/'+b.dataset.delete,{method:'DELETE'});await loadAccount();}}));$('events-list').querySelectorAll('[data-cancel]').forEach(b=>b.onclick=safe(async()=>{await api('/api/events/'+b.dataset.cancel,{method:'PATCH',body:JSON.stringify({status:'cancelled'})});await loadAccount();}));$('events-list').querySelectorAll('[data-history]').forEach(b=>b.onclick=safe(async()=>{const rows=await api('/api/events/'+b.dataset.history+'/history');activeHistoryId=b.dataset.history;$('assessment').innerHTML=rows.map(r=>assessmentHTML(r.assessment)).join('')||'Sin ejecuciones de monitoreo.';const controls=document.createElement('div');controls.innerHTML='<h2>Revisiones del pronostico</h2><label>Variable<select id="version-variable"><option value="temperature_2m">Temperatura</option><option value="precipitation">Precipitacion</option><option value="wind_speed_10m">Viento</option><option value="wind_gusts_10m">Rafagas</option></select></label><div class="chart-wrap"><canvas id="version-chart"></canvas></div><p id="version-note" class="hint"></p>';$('assessment').prepend(controls);
 async function drawVersions(){const selectedId=activeHistoryId;const data=await api('/api/events/'+selectedId+'/forecast-history?variable='+$('version-variable').value);if(selectedId!==activeHistoryId)return;if(versionChart)versionChart.destroy();versionChart=new Chart($('version-chart'),{type:'line',data:{datasets:[{label:data.variable+' ('+data.unit+')',data:data.versions.map(v=>({x:Date.parse(v.fetched_at),y:v.value})),borderColor:'#65d4bd',pointRadius:4,spanGaps:false}]},options:{responsive:true,maintainAspectRatio:false,animation:false,scales:{x:{type:'linear',ticks:{color:'#9bb1bd',maxTicksLimit:4,callback:v=>new Date(v).toISOString().slice(0,16)}}}}});$('version-note').textContent='Hora pronosticada: '+data.valid_time+'. '+data.limitations.join(' ');}
 $('version-variable').onchange=safe(drawVersions);await drawVersions();}));notificationRows=await api('/api/notifications');$('badge').textContent=notificationRows.filter(n=>!n.read_at).length||'';
 $('notifications-list').innerHTML=notificationRows.filter(n=>!notificationEventFilter||n.event_id===notificationEventFilter).map(n=>'<article class="card"><strong>'+escape(n.title)+'</strong><p>'+escape(n.message)+'</p><p>'+escape(n.created_at)+'</p>'+(n.body.changes||[]).map(c=>'<p>'+escape(c.criterion)+': '+number(c.previous_value)+' -> '+number(c.current_value)+' '+escape(c.unit)+'</p>').join('')+'<p class="hint">'+escape(n.body.potential_consequences||'No se infieren impactos territoriales sin evidencia.')+'</p><p>'+escape(n.body.recommendation||'Revisar el evento y las fuentes.')+'</p><p class="hint">Fuente: '+escape(n.body.assessment?.forecast?.provider||'No disponible')+' / '+escape(n.body.assessment?.forecast?.product||'')+' / '+escape(n.body.assessment?.forecast?.fetched_at||n.created_at)+'</p><div class="actions"><button data-notification-event="'+escape(n.event_id)+'">Ir al evento en el mapa</button><button data-read="'+n.id+'">'+(n.read_at?'Leida':'Marcar leida')+'</button></div></article>').join('')||'<p>Sin notificaciones.</p>';
 $('notifications-list').querySelectorAll('[data-read]').forEach(b=>b.onclick=safe(async()=>{await api('/api/notifications/'+b.dataset.read,{method:'PATCH',body:'{}'});await loadAccount();}));
 $('notifications-list').querySelectorAll('[data-notification-event]').forEach(b=>b.onclick=safe(()=>openEvent(b.dataset.notificationEvent)));
 renderEvents();}
  $('auth-form').onsubmit=safe(async e=>{e.preventDefault();const f=$('auth-form').elements;const me=await api('/api/session/'+(e.submitter.name==='register'?'register':'login'),{method:'POST',body:JSON.stringify({username:f.username.value,password:f.password.value})});csrf=me.csrf_token;f.password.value='';await loadAccount();notice('Sesión iniciada. Los eventos son privados.');});$('logout').onclick=safe(async()=>{await api('/api/session/logout',{method:'POST',body:'{}'});await loadAccount();renderEvents();});
  $('event-form').onsubmit=safe(async e=>{e.preventDefault();if(!user){notice('Iniciá sesión para guardar un evento.',true);return;}const id=$('event-form').elements.id.value;await api('/api/events'+(id?'/'+id:''),{method:id?'PATCH':'POST',body:JSON.stringify(eventPayload())});await loadAccount();renderEvents();notice('Evento guardado. El monitoreo se ejecuta mediante el comando independiente.');});
  function assessmentHTML(result){return `<article class="card assessment-${escape(result.status)}"><strong>${escape(result.label||result.status)}</strong><p>${escape(result.generated_at||'')}</p>${(result.reasons||[]).map(r=>`<p>${escape(r.message||r)}</p>`).join('')}<p class="hint">${(result.limitations||[]).map(escape).join(' ')}</p>${result.forecast?'<p class="hint">Fuente: '+escape(result.forecast.provider)+' · '+escape(result.forecast.product)+'<br>Obtención: '+escape(result.forecast.fetched_at)+'<br>Emisión: '+escape(result.forecast.issued_at||'No informada')+'<br>Incertidumbre: sin intervalos provistos por el endpoint.</p>':''}</article>`;}
  async function previewEvent(){
    if(!user){notice('Iniciá sesión para evaluar y guardar el evento.',true);return;}
    $('assessment').textContent='Consultando pronóstico del evento y alternativas…';
    const payload=eventPayload(),selected=activeEventId;
    const result=await api('/api/events/preview',{method:'POST',body:JSON.stringify(payload)});
    if(selected!==activeEventId||JSON.stringify(payload)!==JSON.stringify(eventPayload()))return;
    $('assessment').innerHTML=assessmentHTML(result.assessment)+'<h2>Fechas alternativas</h2>'+result.alternatives.map((a,i)=>`<article class="card"><p>${escape(a.start)} · ${escape(a.assessment.label)}</p><p>${escape(a.explanation)}</p><button data-reschedule="${i}">Usar esta fecha</button></article>`).join('');
    $('assessment').querySelectorAll('[data-reschedule]').forEach(button=>button.onclick=()=>{
      const alternative=result.alternatives[+button.dataset.reschedule];
      $('event-form').elements.start.value=alternative.start.slice(0,16);$('event-form').elements.end.value=alternative.end.slice(0,16);
      updateTime(Time.iso(Time.parse(alternative.start)),{center:true});
      notice('Fecha aplicada al formulario y al mapa. Guardá para confirmar la reprogramación.');
    });
  }
  $('preview-event').onclick=safe(previewEvent);
  async function impact(){
    const city=state.city_id,date=state.date,result=await api('/api/impact?city_id='+city);
    if(city!==state.city_id||date!==state.date)return;
    $('impact-content').innerHTML='<p>Fecha seleccionada: '+escape(date)+' UTC</p>'+`<p class="eyebrow">${escape(result.status)}</p><p>${escape(result.summary)}</p>`+
      (frame?.record?'<p>Condición disponible: '+escape(variableNames[state.variable]||state.variable)+' · '+number(frame.focus?.value)+' '+escape(frame.focus?.unit||'')+'</p>':'<p>Sin condición ambiental válida para la selección.</p>')+
      '<p class="hint">La condición meteorológica por sí sola no prueba inundación, polvo, estrés térmico ni transitabilidad de un camino. Sin capas/modelo y evidencia del sitio, no se estima ese impacto.</p>'+
      result.layers.map(layer=>`<details><summary>${escape(layer.name)}</summary><p>${escape(layer.status)}</p><a href="${escape(layer.source_url)}" target="_blank" rel="noopener">Fuente</a><p class="hint">${escape(layer.limitation)}</p></details>`).join('');
  }
  function download(format){if(!record){notice('Seleccioná una serie con datos.',true);return;}const records=comparisonRecords.length>1?comparisonRecords:[record];const content=format==='json'?JSON.stringify(records.length>1?{kind:'independent_comparable_series',records}:record,null,2):'city_id,date,value,unit,provider,product,frequency,latitude,longitude,fetched_at\n'+records.flatMap(r=>r.series.map(p=>[r.location.id,p.date,p.value??'',r.unit,r.provider,r.product,r.frequency,r.location.latitude,r.location.longitude,r.fetched_at].map(v=>'"'+String(v).replaceAll('"','""')+'"').join(','))).join('\n');const url=URL.createObjectURL(new Blob([content],{type:format==='json'?'application/json':'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='earthlens-'+state.city_id+'-'+state.variable+'.'+format;a.click();URL.revokeObjectURL(url);}
  $('export-json').onclick=()=>download('json');$('export-csv').onclick=()=>download('csv');
  $('report').onclick=()=>{
    if(!frame?.effective_query){notice('No hay una extracción verificable para exportar.',true);return;}
    const {kind,...selection}=frame.effective_query;const query=new URLSearchParams(selection);
    if(state.mode==='compare'){const second=selectedCities().find(c=>c.id!==state.city_id);if(second)query.set('city_b',second.id);}
    window.open('/api/workspace/report.pdf?'+query,'_blank','noopener');
  };
  $('theme').onclick=()=>document.body.classList.toggle('light');

  try{
    [cities,catalog,allIncidents]=await Promise.all([api('/api/cities'),api('/api/science/variables'),api('/api/workspace/incidents')]);
    $('city').innerHTML=cities.map(city=>`<option value="${city.id}">${escape(city.name)}</option>`).join('');
    $('city-suggestions').innerHTML=cities.map(city=>`<option value="${escape(city.name)}">${escape(city.province)}</option>`).join('');
    if(!cities.some(city=>city.id===state.city_id))state.city_id=cities[0].id;
    const initialPanel=state.panel;state.panel=null;
    $('source').value=state.provider;variables();$('scale').value=state.scale;$('mode').value=state.mode;
    $('start').value=state.start;$('end').value=state.end;
    selectCity(state.city_id,{fetchData:false});updateTime(state.date,{fetch:false});
    await loadAccount();prepareEvent();await load();if(initialPanel)panel(initialPanel);
    window.addEventListener('resize',()=>{map.invalidateSize();chart?.resize();});
  }catch(error){notice(error.message,true);}

});
