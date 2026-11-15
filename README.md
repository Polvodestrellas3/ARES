# ARES — Walking Jezero
Educational Mars surface-traverse planner for the 2026 NASA Space Apps Challenge.

## Run locally
Extract the ZIP, open a terminal inside `ARES-Jezero`, and run `python3 atlas.py` (Python 3.9+, no external packages). On Windows use `py atlas.py`. The app opens in your browser. Press Ctrl+C to stop. Optional: `python3 atlas.py --port 8000 --no-browser`.

## Try the planner
- Select the delta traverse (Route B), enable Route slope and apply mission settings.
- Compare science, terrain and duration priorities.
- Change autonomy from 240 to 120 minutes and inspect the recommendation.
- Open the numbered field sites or the station tabs to read the science notes.

## Edit and collaborate
- `atlas.py`: local server, route and map rendering, UI integration.
- `planificacion.py`: numerical calculations and route recommendation.
- `plantilla.html`: editable HTML and CSS interface.
- `datos/terreno.json`: original map, route coordinates and sampled profiles. New routes require new elevation profiles.
- `datos/estaciones.json`: site descriptions, scientific context, images and references.
- `test_planificacion.py`: regression tests. Run `python3 -m unittest -v test_planificacion.py`.

Share the extracted folder in a Git repository so each collaborator can edit their own module. The numerical module can also be imported into Google Colab; the web server is intended for local execution.

## Science and limitations
The map assets and numerical data are inherited from the previous atlas. The science descriptions cite NASA resources inside the app; the original map provenance has not been independently revalidated. Field activities, reserve and mobility assumptions are proposed by the team, not NASA flight specifications. Slope estimates are averaged over approximately 10 m; surface obstacles, atmosphere, radiation and life support are not modeled. The route recommendation compares time feasibility and a selected priority, not actual astronaut safety.
