"""Local Jezero mission planner. Run with python3 atlas.py."""
import argparse
import json
import math
import webbrowser
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from string import Template
from planificacion import metrics, mission, recommend, map_slope_pieces, segments, slope_band, BANDS

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "datos"
terrain = json.loads((DATA / "terreno.json").read_text(encoding="utf-8"))
stations = {s["name"]: s for s in json.loads((DATA / "estaciones.json").read_text(encoding="utf-8"))}
routes = terrain["routes"]
names = ["A · Short traverse", "B · Delta traverse"]
template = Template((ROOT / "plantilla.html").read_text(encoding="utf-8"))


def path(points):
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in points)


def map_svg(active, layers, station_idx, zoom, config):
    width, height = terrain["width"], terrain["height"]
    station = terrain["stops"][station_idx]
    w, h = width / zoom, height / zoom
    left = min(max(0, station["x"] - w/2), width-w)
    top = min(max(0, station["y"] - h/2), height-h)
    base = "relief.webp" if "relieve" in layers else "orbit.webp"
    parts = [f'<svg viewBox="{left} {top} {w} {h}" aria-label="Map of the western Jezero delta"><image href="/datos/{base}" width="{width}" height="{height}"/>']
    if "geologia" in layers:
        parts.append(f'<image href="/datos/geology.svg" width="{width}" height="{height}"/>')
    for i in ([1-active, active] if "ambas" in layers else [active]):
        color = ["#ffd166", "#89f4cc"][i]
        dash = 'stroke-dasharray="8 4"' if i == 1 else ""
        line = path(routes[i]["points"])
        for stroke, weight, pattern in [("#17231d", 5, ""), (color, 3, dash)]:
            parts.append(f'<polyline points="{line}" fill="none" stroke="{stroke}" stroke-width="{weight}" vector-effect="non-scaling-stroke" {pattern}/>')
    if "pendientes" in layers:
        for points, angle in map_slope_pieces(routes[active], terrain["metersPerPixel"]):
            color, label = slope_band(angle)
            parts.append(f'<polyline points="{path(points)}" fill="none" stroke="{color}" stroke-width="4" vector-effect="non-scaling-stroke"><title>{angle:.1f}° · {label}</title></polyline>')
    x,y = terrain["start"]
    parts.append(f'<rect x="-5" y="-5" width="10" height="10" transform="translate({x} {y}) rotate(45)" fill="white" stroke="#202724"/>')
    for i,p in enumerate(terrain["stops"]):
        x,y = p["x"],p["y"]
        dx,dy = [(0,0),(8,-6),(-8,6)][i]
        radius=10/zoom
        dx,dy=dx/zoom,dy/zoom
        parts.append(f'<a href="?{query(active,layers,i,zoom,config)}#ficha" aria-label="Explore {escape(p["name"])}"><title>{escape(p["name"])}</title><line x1="{x}" y1="{y}" x2="{x+dx}" y2="{y+dy}" stroke="white"/><circle cx="{x+dx}" cy="{y+dy}" r="{radius}" fill="{"#faf4e7" if i==station_idx else "#392d25"}" stroke="white" stroke-width="{1.5/zoom}"/><text x="{x+dx}" y="{y+dy+4/zoom}" text-anchor="middle" fill="{"#392d25" if i==station_idx else "white"}" font-size="{12/zoom}" font-weight="bold">{i+1}</text></a>')
    parts.append(f'<text x="{left+12/zoom}" y="{top+22/zoom}" fill="white" stroke="#29312e" stroke-width=".8" paint-order="stroke" font-size="{16/zoom}">↑ N</text></svg>')
    scale = 100 if zoom <= 2 else 50
    scale_x,scale_y=left+18/zoom,top+h-20/zoom
    parts.insert(-1,f'<g stroke="white" stroke-width="{2/zoom}"><path d="M {scale_x} {scale_y-4/zoom} v {4/zoom} h {scale/terrain["metersPerPixel"]} v {-4/zoom}" fill="none"/><text x="{scale_x}" y="{scale_y-8/zoom}" fill="white" stroke="#332a23" stroke-width="{.5/zoom}" paint-order="stroke" font-size="{12/zoom}">{scale} m</text></g>')
    return "".join(parts)


def query(active, layers, station, zoom, config):
    return f"ruta={active}&amp;parada={station}&amp;zoom={zoom}"+ "".join(f"&amp;capa={l}" for l in sorted(layers)) + "".join(f"&amp;{k}={v}" for k,v in config.items())


def profile_svg(route):
    data = route["profile"]
    lo,hi = min(z for _,z in data),max(z for _,z in data)
    pts = [(10+480*d/data[-1][0],76-65*(z-lo)/(hi-lo or 1)) for d,z in data]
    lines = "".join(f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}" stroke="{slope_band(theta)[0]}" stroke-width="3"><title>{abs(theta):.1f}°</title></line>' for a,b,(_,_,theta) in zip(pts,pts[1:],segments(route)))
    return f'<svg viewBox="0 0 500 90" aria-label="Elevation profile"><polygon points="10,84 {path(pts)} 490,84" fill="#e7ded0"/>{lines}</svg><small>Start to return · elevation from {lo:.0f} to {hi:.0f} m · vertical scale exaggerated</small>'


def number(params, key, default, lower, upper):
    try:
        v = float(params.get(key,[default])[0])
        return v if math.isfinite(v) and lower <= v <= upper else default
    except (ValueError, TypeError):
        return default


def choice(params,key,allowed,default):
    raw=params.get(key,[str(default)])[0]
    return int(raw) if raw in {str(v) for v in allowed} else default


def render(params):
    active=choice(params,"ruta",[0,1],0)
    route=routes[active]
    idx=choice(params,"parada",range(len(terrain["stops"])),route["stops"][0])
    zoom=choice(params,"zoom",[1,2,4],1)
    layers=set(params.get("capa",["ambas"] if not params else [])) & {"relieve","geologia","ambas","pendientes"}
    station=stations[terrain["stops"][idx]["name"]]
    config={"speed":number(params,"speed",1,0.1,5),
            "minutes_per_stop":number(params,"minutes_per_stop",20,0,180),
            "autonomy":number(params,"autonomy",240,15,720),
            "reserve":number(params,"reserve",30,0,720)}
    priority=params.get("priority",["science"])[0]
    if priority not in {"science","terrain","time"}:priority="science"
    results=[mission(r,terrain["metersPerPixel"],**config) for r in routes]
    config["priority"]=priority
    selected=results[active]
    best=recommend(results,priority)
    why={"science":"the most science stations", "terrain":"the lowest sampled maximum slope", "time":"the shortest total duration"}
    if best is None:
        recommendation="Neither route fits the selected time budget. Revise the science time or mission parameters."
    else:
        recommendation=f"{names[best]} offers {why[priority]} among the routes that fit the selected time budget."
    priority_options="".join(f'<option value="{k}" {"selected" if k==priority else ""}>{v}</option>' for k,v in [("science","More science stations"),("terrain","Lower maximum slope"),("time","Shorter duration")])
    band_legend=" · ".join(f'<span style="color:{color}">●</span> {label}' for _,color,label in BANDS)
    band_legend += " · &lt;5° / 5–&lt;10° / 10–&lt;15° / ≥15°"
    options="".join(f'<option value="{i}" {"selected" if i==active else ""}>{name}</option>' for i,name in enumerate(names))
    checks="".join(f'<label><input type="checkbox" name="capa" value="{v}" {"checked" if v in layers else ""}> {label}</label>' for v,label in [("relieve","Elevation"),("geologia","Geology"),("ambas","Both routes"),("pendientes","Route slope")])
    stops=" · ".join(f'<a href="?{query(active,layers,i,zoom,config)}#ficha">{escape(terrain["stops"][i]["name"])}</a>' for i in route["stops"])
    table=""
    for i,r in enumerate(results):
        state="Within budget" if r["fits"] else "Over budget"
        state_class="ok" if r["fits"] else "over"
        table+=f'<tr><th>{names[i]}</th><td>{r["distance"]:.0f} m</td><td>{r["ascent"]:.1f} m</td><td>{r["max_slope"]:.1f}°</td><td>{r["stops"]}</td><td>{r["total"]:.0f} min</td><td>{r["remaining"]:+.0f} min</td><td><span class="status {state_class}">{state}</span></td></tr>'
    legend=''
    if "geologia" in layers:
        legend+=' '.join(f'<span style="color:{c}">■</span> {n}' for c,n in [('#669de6','Fan unit 2'),('#cf8cae','Jezero floor'),('#be9b30','Aeolian bedforms'),('#e99d60','Eroded upper unit')])
    if "relieve" in layers:
        legend+=' · Elevation: −2,552 m (teal) to −2,460 m (ochre).'
    sources=terrain["sources"]+[{"title":"Sun & Stack (2020) · USGS geologic map (1:75,000)","url":"https://doi.org/10.3133/sim3464"}]
    station_tabs="".join('<a class="site-tab'+(' selected' if i==idx else '')+'" href="?'+query(active,layers,i,zoom,config)+'#ficha"><span>0'+str(i+1)+'</span>'+escape(p['name'])+'</a>' for i,p in enumerate(terrain['stops']))
    source_science=station.get('scienceSource',station['source'])
    budget_status='Within time budget' if selected['fits'] else 'Over time budget'
    budget_class='ok' if selected['fits'] else 'over'
    ratio=min(100,100*selected['total']/config['autonomy'])
    return template.substitute(station_tabs=station_tabs,station_number=idx+1,tag=escape(station['tag']),question=escape(station['question']),equipment=escape(station['equipment']),outcome=escape(station['outcome']),science_source=escape(source_science),coordinates=f'{station["lat"]:.5f}° N / {station["lon"]:.5f}° E',budget_status=budget_status,budget_class=budget_class,ratio=f'{ratio:.1f}',recommended_name=names[best] if best is not None else 'No route fits',
        options=options,checks=checks,map=map_svg(active,layers,idx,zoom,config),legend=legend,
        name=names[active],stops=stops,profile=profile_svg(route),table=table,
        speed=config["speed"], minutes_per_stop=config["minutes_per_stop"],autonomy=config["autonomy"],reserve=config["reserve"],priority_options=priority_options,
        recommendation=escape(recommendation),bands=band_legend,walk=f'{selected["walk"]:.0f}',science=f'{selected["science"]:.0f}',total=f'{selected["total"]:.0f}',remaining=f'{selected["remaining"]:+.0f}',max_slope=f'{selected["max_slope"]:.1f}',distance=f'{selected["distance"]:.0f}',active=active,zoom=zoom,idx=idx,station=escape(station["name"]),
        photo=station["src"],alt=escape(station["alt"]),credit=escape(station["credit"]),camera=station["camera"],
        evidence=escape(station["evidence"]),task=escape(station["task"]),source=station["source"],note=escape(terrain["note"]),
        zooms=" · ".join(f'<a href="?{query(active,layers,idx,z,config)}">{z}×</a>' for z in [1,2,4]),
        sources="".join(f'<li><a href="{escape(s["url"])}">{escape(s["title"])}</a></li>' for s in sources))


class AtlasHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        address=urlsplit(self.path)
        if address.path=="/":
            content=render(parse_qs(address.query)).encode("utf-8")
            mime="text/html; charset=utf-8"
        else:
            files={"orbit.webp":"image/webp","relief.webp":"image/webp","geology.svg":"image/svg+xml"}
            files.update({s["src"]:"image/jpeg" for s in stations.values()})
            name=address.path.removeprefix("/datos/")
            if not address.path.startswith("/datos/") or name not in files:
                self.send_error(404)
                return
            content=(DATA / name).read_bytes()
            mime=files[name]
        self.send_response(200)
        self.send_header("Content-Type",mime)
        self.send_header("Content-Length",str(len(content)))
        self.end_headers()
        self.wfile.write(content)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port","--puerto",dest="port",type=int,default=0,help="Local port; defaults to an available port.")
    parser.add_argument("--no-browser","--sin-navegador",dest="no_browser",action="store_true")
    args=parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1",args.port),AtlasHandler) as server:
        url=f"http://127.0.0.1:{server.server_port}/"
        print(f"Open {url} in your browser. Press Ctrl+C to stop.",flush=True)
        if not args.no_browser:webbrowser.open(url)
        try:server.serve_forever()
        except KeyboardInterrupt:pass
