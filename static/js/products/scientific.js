/* Series nativas; sin cálculos de tendencia, imputación ni puntajes. */
(() => {
  let chartLibrary;
  async function api(path, body, signal) {
    const response = await fetch(path, {signal, headers:{Accept:'application/json',...(body?{'Content-Type':'application/json'}:{})},...(body?{method:'POST',body:JSON.stringify(body)}:{})});
    const value = await response.json();
    if (!response.ok || value.status !== 'ok') throw new Error(value.error?.message || 'No se pudo consultar la fuente.');
    return value.data;
  }
  function chartReady() {
    if (window.Chart) return Promise.resolve();
    if (!chartLibrary) chartLibrary = new Promise((resolve,reject) => {const script=document.createElement('script');script.src='https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js';script.onload=resolve;script.onerror=()=>{chartLibrary=null;reject(new Error('No se pudo cargar el gráfico. Los datos siguen disponibles en la API.'));};document.head.append(script);});
    return chartLibrary;
  }
  const option=(value,label)=>{const item=document.createElement('option');item.value=value;item.textContent=label;return item;};
  const names={T2M:'Temperatura media',T2M_MAX:'Temperatura máxima mensual',T2M_MIN:'Temperatura mínima mensual',PRECTOTCORR:'Precipitación POWER',RH2M:'Humedad relativa atmosférica',WS2M:'Viento',SoilMoi0_10cm_inst:'Humedad del suelo 0–10 cm',SoilMoi10_40cm_inst:'Humedad del suelo 10–40 cm',SoilMoi40_100cm_inst:'Humedad del suelo 40–100 cm',SoilMoi100_200cm_inst:'Humedad del suelo 100–200 cm',Evap_tavg:'Flujo de evapotranspiración',NDVI:'NDVI',EVI:'EVI',precipitation:'Precipitación IMERG',wse:'Altura superficial del agua',width:'Ancho del río'};
  window.EarthLensScience={request:api}; // Contrato reutilizable al integrar la interfaz Time Machine del equipo.
  function init(root) {
    const form=root.querySelector('form'), status=root.querySelector('.science-status'), output=root.querySelector('.science-output');
    const source=form.elements.source, city=form.elements.city, other=form.elements.other, water=form.elements.water, cross=form.elements.cross;
    let ready=false,loading=false,variables=[],features=[],chart,controller,sequence=0,plots=[];
    function message(text,error=false){status.textContent=text;status.dataset.error=String(error);}
    function selection(){return variables.find(v=>`${v.provider}:${v.variable}`===source.value);}
    function update(){
      controller?.abort();sequence++;output.hidden=true;
      const swot=source.value.startsWith('swot:');
      root.querySelectorAll('[data-city-control]').forEach(n=>{n.hidden=swot;});root.querySelector('[data-water-control]').hidden=!swot;
      cross.closest('label').hidden=swot || !['gpm:precipitation','power:PRECTOTCORR'].includes(source.value);cross.checked=false;
      if(swot){form.elements.start.value=2024;form.elements.end.value=2024;return;}
      const scope=(selection()?.verification||[]).filter(v=>v.city_id===city.value).sort((a,b)=>(b.period.end_year-b.period.start_year)-(a.period.end_year-a.period.start_year))[0];
      if(scope){form.elements.start.value=scope.period.start_year;form.elements.end.value=scope.period.end_year;}
    }
    async function loadCatalog(){
      if(ready||loading)return;loading=true;message('Cargando fuentes verificadas…');
      try {
        const [catalog,cities,waterFeatures]=await Promise.all([api('/api/science/variables'),api('/api/cities'),api('/api/science/water-features')]);
        const unique=new Map();for(const row of catalog){const key=`${row.provider}:${row.variable}`;const old=unique.get(key);unique.set(key,old?{...old,verification:[...old.verification,...row.verification]}:row);}variables=[...unique.values()];features=waterFeatures;
        source.replaceChildren(...variables.map(v=>option(`${v.provider}:${v.variable}`,`${names[v.variable]||v.variable} · ${v.provider.toUpperCase()} · ${v.unit}`)));
        if(features.length){source.append(option('swot:wse','Altura superficial del agua · SWOT · m'),option('swot:width','Ancho de río · SWOT · m'));}
        city.replaceChildren(...cities.map(c=>option(c.id,`${c.name}, ${c.province}`)));other.replaceChildren(option('','Sin comparación'),...cities.map(c=>option(c.id,c.name)));
        water.replaceChildren(...features.map(f=>option(f.id,f.name)));
        const requested=new URLSearchParams(location.search).get('city_id');city.value=cities.some(c=>c.id===requested)?requested:'mendoza';
        if(variables.some(v=>v.provider==='gldas'&&v.variable==='SoilMoi0_10cm_inst'))source.value='gldas:SoilMoi0_10cm_inst';
        ready=true;update();message(`${variables.length} variables de ciudades verificadas${features.length?' y observaciones SWOT del catálogo hidrológico':''}. Elegí una consulta.`);
      }catch(error){message(error.message,true);}finally{loading=false;}
    }
    function draw(limit){
      if(!chart)return;
      const dates=[...new Set(plots.flatMap(p=>p.series.map(row=>row.date)))].sort().slice(0,limit);
      chart.options.scales.x.min=Date.parse(dates[0]);chart.options.scales.x.max=Date.parse(dates.at(-1));
      chart.data.labels=dates;chart.data.datasets=plots.map((p,index)=>{const values=new Map(p.series.map(r=>[r.date,r.value]));return {label:p.label,data:dates.map(d=>({x:Date.parse(d),y:values.has(d)?values.get(d):null,date:d})),borderColor:index?'#d06b13':'#167c80',pointRadius:dates.length>100?0:2,spanGaps:false};});chart.update('none');
      root.querySelector('output').textContent=dates.at(-1)||'';
    }
    root.querySelector('input[type=range]').addEventListener('input',event=>draw(Number(event.target.value)));
    source.addEventListener('change',update);city.addEventListener('change',update);other.addEventListener('change',()=>{controller?.abort();sequence++;output.hidden=true;});
    form.addEventListener('change',()=>{controller?.abort();sequence++;output.hidden=true;});
    form.addEventListener('submit',async event=>{
      event.preventDefault();if(!ready)return;controller?.abort();controller=new AbortController();const current=++sequence;output.hidden=true;message('Consultando la selección…');
      const start=Number(form.elements.start.value),end=Number(form.elements.end.value);
      if(start>end){message('El período está invertido.',true);return;}
      try {
        let result,rows,context;
        if(source.value.startsWith('swot:')) {
          result=await api('/api/science/water-data',{feature_id:water.value,start_time:`${start}-01-01T00:00:00Z`,end_time:`${end}-12-31T23:59:59Z`},controller.signal);
          const variable=source.value.split(':')[1],record=result.variables[variable];rows=record.series;
          plots=[{label:`${result.feature.name} · ${record.unit}`,unit:record.unit,series:rows}];
          context=`${result.product} · versión ${result.product_version} · ${record.unit} · pasos satelitales irregulares. Las banderas originales requieren revisión; no se consideran observaciones aceptadas automáticamente para análisis.`;
        } else {
          const selected=selection(),base={provider:selected.provider,city_id:city.value,variable:selected.variable};
          if(other.value||cross.checked){
            const second=cross.checked?{provider:base.provider==='gpm'?'power':'gpm',city_id:other.value||city.value,variable:base.provider==='gpm'?'PRECTOTCORR':'precipitation'}:{...base,city_id:other.value};
            result=await api('/api/science/compare',{selections:[base,second],start_year:start,end_year:end,...(cross.checked?{target_unit:'mm/day'}:{})},controller.signal);
            rows=result.plots[0].series;plots=result.plots.map((p,i)=>({label:`${p.city.name} · ${result.sources[i].provider} · ${p.display_unit}`,unit:p.display_unit,series:p.series}));context=result.comparison.warnings.join(' ');
          } else {
            result=(await api('/api/science/data',{provider:base.provider,city_id:base.city_id,variables:[base.variable],start_year:start,end_year:end},controller.signal))[0];rows=result.series;
            plots=[{label:`${result.location.name} · ${result.unit}`,unit:result.unit,series:rows}];
            context=`${result.product} · versión ${result.product_version??'no declarada en la respuesta'} · ${result.unit} · ${result.frequency}. ${result.coverage.valid_count}/${result.coverage.expected_count} valores disponibles. ${result.metadata.precision_note||''}`;
          }
        }
        await chartReady();if(current!==sequence)return;
        const frame=root.querySelector('.science-chart');let canvas=frame.querySelector('canvas');
        if(!canvas){canvas=document.createElement('canvas');canvas.setAttribute('aria-label','Serie temporal de la variable seleccionada');canvas.setAttribute('role','img');frame.append(canvas);}
        chart?.destroy();chart=new Chart(canvas,{type:'line',data:{labels:[],datasets:[]},options:{responsive:true,maintainAspectRatio:false,animation:false,plugins:{tooltip:{callbacks:{title:items=>items[0]?.raw.date||''}}},scales:{x:{type:'linear',ticks:{maxTicksLimit:5,callback:value=>new Date(value).toISOString().slice(0,10)}},y:{title:{display:true,text:plots[0].unit}}}}});
        root.querySelector('.science-context').textContent=context;
        root.querySelector('.science-metadata').textContent=JSON.stringify(result,null,2);
        const tbody=root.querySelector('tbody');tbody.replaceChildren(...rows.map(row=>{const tr=document.createElement('tr');const flag=row.quality?JSON.stringify(row.quality):'';for(const text of [row.date,row.value===null?'Sin dato':row.value,plots[0].label,flag+(row.uncertainty!=null?`; incertidumbre ${row.uncertainty}`:'')]){const td=document.createElement('td');td.textContent=String(text);tr.append(td);}return tr;}));
        const slider=root.querySelector('input[type=range]'),count=new Set(plots.flatMap(p=>p.series.map(r=>r.date))).size;slider.max=count;slider.value=count;output.hidden=false;draw(count);message('Datos disponibles. El deslizador recorre esta respuesta sin nuevas consultas; no se calcularon significancias ni puntajes.');
      }catch(error){if(current===sequence&&error.name!=='AbortError')message(error.message,true);}
    });
    root.addEventListener('toggle',()=>{if(root.open)loadCatalog();});if(root.open)loadCatalog();
  }
  function start(){document.querySelectorAll('[data-science-panel]').forEach(init);}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
