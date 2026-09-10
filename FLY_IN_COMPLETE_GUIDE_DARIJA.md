# Fly-in — Guide Complet b Darija (Moroccan) باش تفهم المشروع وتدافع عليه فـ Evaluation

> هاد الملف معمّر باش يكون **study guide + architecture guide + code walkthrough + evaluation prep + push checklist**.
> الهدف ماشي غير تحفظ code، ولكن تفهم علاش كل حاجة موجودة وكيفاش كتخدم من input حتى output.

---

## 0. شنو هو Fly-in باختصار؟

`Fly-in` هو project ديال routing/simulation ديال drones فوق graph. عندنا:

- `start_hub`: البلاصة اللي كيبداو منها جميع drones.
- `end_hub`: الهدف النهائي.
- `hub`: zones وسطانية.
- `connection`: edges ثنائية الاتجاه بين zones.
- zones عندها أنواع مختلفة: `normal`, `priority`, `restricted`, `blocked`.
- كل zone تقدر يكون عندها `max_drones`.
- كل connection تقدر يكون عندها `max_link_capacity`.
- simulation كتخدم **turn by turn**.
- الهدف: نوصلو جميع drones للـ end بأقل عدد ممكن من turns مع احترام capacities والقواعد.

المشروع ديالك مقسوم بشكل واضح:

```text
                    ┌──────────────┐
input map file ───▶ │   parser.py  │
                    └──────┬───────┘
                           │ creates
                           ▼
                ┌──────────────────────┐
                │ zones / connections  │  ← classes.py
                └─────────┬────────────┘
                          │
                          ▼
                ┌──────────────────────┐
                │   simulation.py      │
                │ graph + pathfinding  │
                │ assignment + turns   │
                └─────────┬────────────┘
                          │ list of moves
                          ▼
                ┌──────────────────────┐
                │     render.py        │
                │ terminal + colors    │
                └─────────┬────────────┘
                          ▼
                       stdout
```

`main.py` هو orchestration layer: كيشد argument، كيبني parser، من بعد simulation، ومن بعد renderer.

---

# 1. Requirements ديال subject اللي خاصك تكون حافظهم

## Language / quality

- Python 3.10+.
- OOP mandatory.
- Type hints mandatory.
- `mypy` mandatory.
- `flake8` mandatory.
- Exceptions خاصها تكون handled بشكل واضح.
- Files خاصها تتحل بـ context manager (`with open(...)`).
- ممنوع graph libraries بحال `networkx` و `graphlib`.
- README خاصو يكون بالإنجليزية.
- جميع files خاصهم يكونو فـ root ديال repository حسب subject.

## Map syntax

```text
nb_drones: 5
start_hub: hub 0 0 [color=green]
end_hub: goal 10 10 [color=yellow]
hub: roof1 3 4 [zone=restricted color=red]
connection: hub-roof1 [max_link_capacity=2]
```

أهم القواعد:

- أول meaningful declaration خاصها تكون `nb_drones`.
- العدد positive integer.
- start واحد فقط.
- end واحد فقط.
- zone names unique.
- coordinates unique فimplementation ديالك.
- zone name ما يكونش فيه space ولا `-`.
- connection خاصها تربط zones سبق تعريفهم.
- `a-b` و `b-a` duplicate.
- metadata بين `[...]`.
- capacities خاصهم positive integers.

## Zone types

| Type | Meaning | Cost فالكود ديالك | الحركة |
|---|---|---:|---|
| `normal` | zone عادية | `1` | 1 turn |
| `priority` | preferred zone | `0.9` routing weight | فعليا movement كتوقع فـ 1 turn |
| `restricted` | zone حساسة | `2` | كتحتاج جوج turns |
| `blocked` | ممنوع الدخول | `inf` | ما كتدخلش للpath |

مهم فـ evaluation: **subject كيقول priority movement cost = 1 turn ولكن preferred فـ pathfinding**. انت مثلتي preference بوزن `0.9`. هادشي خاصك تشرح أنه **routing weight** ماشي literal simulation duration. والأكثر أمانا تقنيا هو تفصل `movement_turn_cost=1` على `routing_weight=0.9`.

---

# 2. Architecture ديال المشروع

## `classes.py` — Domain Model

فيه 4 classes:

### `zones`
كتخزن:
- الاسم
- coordinates
- النوع
- max capacity
- current capacity
- metadata
- routing cost

### `connection`
كتربط جوج zones وكتخزن:
- endpoints
- `max_link_capacity`
- `drones_in`: شحال من drone استعمل link فهاد turn

### `Path`
object مساعد فمرحلة assignment:
- id
- list ديال zones
- cost
- bottleneck capacity
- عدد drones اللي assignina لهاد path

### `drone`
كيخزن state ديال drone:
- id
- current zone
- assigned path
- index ديال next step
- target zone
- واش حاليا وسط connection نحو restricted zone

وعندو `movement()` اللي فيه core movement rules.

---

# 3. Theory: Graphs اللي خاصك تعرف

## 3.1 Graph شنو هو؟

Graph = `G = (V, E)`

- `V`: vertices/nodes = zones
- `E`: edges = connections

المشروع عندو **undirected graph** حيث connection bidirectional.

مثال:

```text
start ---- A ---- end
   \
    B ---- C ---- end
```

Adjacency list:

```python
{
    "start": [("A", costA), ("B", costB)],
    "A": [("start", costStart), ("end", costEnd)],
    ...
}
```

علاش adjacency list؟
- memory efficient: `O(V + E)`
- traversal ديال neighbors سريع
- أحسن من adjacency matrix فـ sparse graphs.

## 3.2 Weighted graph

ماشي كل movement عندو نفس preference/cost:

- normal = 1
- restricted = 2
- blocked = infinity
- priority = 0.9 كـ routing preference فimplementation ديالك

إذن graph weighted.

---

# 4. Dijkstra, Reverse Dijkstra, و A*

## 4.1 Dijkstra

Dijkstra كيحسب shortest path فـ graph weights ديالو non-negative.

الفكرة:

```text
dist[start] = 0
others = infinity

كل مرة:
1. خرج node عندو أصغر distance
2. جرّب relax neighbors
3. إلا لقيتي distance أحسن، update
```

Relaxation:

```text
new_distance = current_distance + edge_or_destination_cost
if new_distance < old_distance:
    update
```

Complexity باستعمال heap:

```text
O((V + E) log V)
```

## 4.2 شنو داير `distance_to_end()`؟

انت ما كتديرش Dijkstra من start فقط. كتدير Dijkstra **بالعكس من end** باش تحسب:

```text
h(x) = أرخص cost من x حتى end
```

هاد `h` غادي تستعملها heuristic.

حيت movement `u -> v` cost ديالو مرتبط بالzone اللي غادي ندخلو ليها `v`, ملي كنخدمو reverse من `v` لـ `u`, كنزيدو cost ديال `v`.

هاد التفصيل مهم جدا فevaluation.

## 4.3 A*

من بعد كتستعمل:

```text
f(n) = g(n) + h(n)
```

- `g(n)`: cost من start حتى current node.
- `h(n)`: estimated remaining cost حتى end.
- `f(n)`: total estimated cost.

حيت `h` عندك محسوبة بـ exact reverse Dijkstra، فهي heuristic قوية جدا ومفروض تكون admissible فهاد model لأن weights non-negative.

## 4.4 علاش method سميتها `dijkstra()` وهي أقرب لـ A*؟

هاد نقطة evaluator يقدر يشدك فيها.

الجواب:

> "الاسم historical عندي، ولكن implementation الفعلية كتدير best-first/A* enumeration ديال simple paths. كنحسب exact heuristic بـ reverse Dijkstra، ومن بعد priority queue كتترتب بـ `g + h`."

الأفضل قبل final push: rename method لـ `find_candidate_paths()` أو `astar_k_paths()` إلا عندك الوقت وما غاديش تكسر tests.

---

# 5. K candidate paths

فـ constructor:

```python
self.dijkstra(self.start_hub.name, 4)
```

يعني كتجمع غير حتى لـ 4 candidate paths.

المزية:
- search محدود.
- memory أقل.
- assignment ساهل.

العيب:
- map ممكن يكون فيها أكثر من 4 paths مفيدين.
- performance benchmarks ممكن يحتاجو distribution أوسع.
- hard/challenger maps يقدرو يربحو من dynamic `k`.

فevaluation قول:

> "اخترت k=4 كtrade-off بين search cost وroute diversity. تحسين ممكن هو نخلي k dynamic حسب عدد drones، degree ديال start، أو graph size."

---

# 6. Simple paths و cycle prevention

داخل search:

```python
if zone1 in path:
    continue
```

هادشي كيمنع cycle.

مثلا بلا هاد الشرط:

```text
A -> B -> A -> B -> A ...
```

priority queue تقدر تكبر بزاف وحتى search يولي غير عملي.

الثمن:
- `zone1 in path` على list = `O(length_of_path)`.
- optimization محتمل: نخزن visited set مع path، ولكن غادي يزيد memory.

---

# 7. Capacity theory

عندنا جوج أنواع ديال capacity.

## Zone capacity

```text
target.capacity < target.max_drones
```

إلا target عامرة، drone كيستنى.

## Link capacity

```text
con.drones_in < con.max_link_capacity
```

كل turn كتreset:

```python
con.drones_in = 0
```

يعني capacity ديال connection **per turn**.

## Bottleneck capacity

Path throughput محدود بأضعف عنصر:

```text
capacity(path) = min(all relevant zone/link capacities)
```

بحال pipe:
- link 1 capacity = 5
- zone capacity = 2
- link 2 capacity = 7

الthroughput الواقعي ما يقدرش يفوت 2.

فالكود هاد الحساب كاين فـ `min_cost()`، ولكن الاسم misleading: راه كيحسب **minimum/bottleneck capacity** ماشي monetary/graph cost.

الأفضل: rename لـ `compute_path_bottlenecks()`.

---

# 8. Load balancing: كيفاش كتوزع drones على paths

كل path عندها:

```python
estimate = path.cost + path.exist_drones / path.capacity
```

المعنى:

- path قصيرة = attractive.
- path فيها drones بزاف = penalty.
- path capacity كبيرة = queue penalty كيكون أقل.

مثال:

```text
Path A: cost=4, capacity=1, existing=3
estimate = 4 + 3/1 = 7

Path B: cost=5, capacity=3, existing=1
estimate = 5 + 1/3 = 5.33
```

رغم B أطول شوية، يقدر يكون أحسن overall لأن throughput ديالو أقوى.

هادشي heuristic load balancing، ماشي mathematical proof ديال global optimum.

---

# 9. Discrete-event / turn simulation

Simulation كتخدم turns:

```text
Turn 1
Turn 2
Turn 3
...
```

كل drone يقدر يتحرك maximum مرة وحدة فturn.

`moved` set كيضمن هاد القاعدة:

```python
if d.id in moved:
    continue
```

ولكن loop `while progress` كيعطي فرصة للدrones اللي كانوا blocked فبداية turn يتحركو من بعد ما drone آخر خرج وحرر capacity فـ **نفس turn**.

هادشي مطابق لفكرة subject:
> drone اللي كيخرج من zone كيحرر capacity لنفس turn.

---

# 10. Restricted zone — جوج turns بالتفصيل

هاد الجزء من أهم أجزاء المشروع.

إلا drone باغي يدخل `restricted`:

### Turn T

1. نشوفو capacity ديال destination.
2. نشوفو capacity ديال connection.
3. نحجزو destination:
   ```python
   self.target_zone.capacity += 1
   ```
4. نحيدو occupancy من source:
   ```python
   self.zone.capacity -= 1
   ```
5. نخليو:
   ```python
   self.in_connection = True
   ```
6. output:
   ```text
   D1-source-target
   ```

### Turn T+1

drone خاصو يوصل mandatory:

```python
if self.in_connection:
    self.zone = self.target_zone
    self.in_connection = False
    self.index_path += 1
```

علاش reservation من turn الأول ذكية؟

حيت subject كيقول drone ما يقدرش يبقى عالق وسط connection كيستنى destination تفرغ. إذن خاصك تضمن space قبل ما يدخل transit.

---

# 11. Deadlock

Deadlock فهاد context:

- كاين drones مازال ما وصلوش.
- ولكن حتى واحد ما قدر يتحرك.
- simulation غادي تبقى infinite loop إلا ما كشفناش هاد الحالة.

الكود:

```python
if not moves:
    raise Invalid_graph(
        f"deadlock at turn {self.nb_turn + 1}: no drone can move"
    )
```

هاد defensive programming مهم.

---

# 12. Parser architecture

Parser ديالك ماشي غير `split`. عندو responsibilities متعددة:

1. file reading.
2. ignore comments / empty lines.
3. syntax classification.
4. validate first `nb_drones`.
5. enforce unique start/end.
6. parse coordinates.
7. enforce unique coordinates.
8. parse metadata.
9. validate zone type.
10. validate capacities.
11. enforce unique names.
12. validate connections.
13. reject unknown references.
14. reject duplicate undirected edges.
15. build actual domain objects.

Flow:

```text
line
 │
 ├─ strip
 ├─ ignore comment/empty
 ├─ remove inline comment
 ├─ split first ":"
 ├─ detect record type
 ├─ validate
 ├─ parse metadata
 └─ create zone/connection object
```

---

# 13. Metadata parsing

Zone metadata defaults:

```python
data["zone"] = "normal"
data["color"] = "none"
data["max_drones"] = 1
```

start/end كيتعاملو بشكل خاص وكتعطيهم capacity ديال total drone count.

بعدها كل token بحال:

```text
zone=restricted
color=red
max_drones=3
```

كيتقسم على `=`.

مهم: tag order ما كيهمش لأنك كتloop على parts.

---

# 14. Duplicate connection detection

Subject كيعتبر:

```text
A-B
B-A
```

نفس edge.

الكود:

```python
modified = tuple(sorted((a, b)))
```

الاثنين كيعطيو:

```python
("A", "B")
```

من بعد `set` كيكشف duplicate.

Complexity:
- `sorted` على جوج strings عملياً constant صغير.
- loop على E connections = تقريبا `O(E)`.

---

# 15. Custom exceptions

عندك:

- `Invalid_Syntax`: parser errors + line number.
- `Invalid_Argument`: CLI misuse.
- `Invalid_graph`: graph/path/simulation failure.

المزية:
- separation of concerns.
- error messages واضحة.
- easier debugging.
- evaluator يقدر يعرف source ديال الخطأ بسرعة.

ANSI code:

```text
\033[91m
```

كيبدل لون الخطأ للأحمر فterminal.

---

# 16. Terminal rendering

`TerminalRender` responsibility ماشي pathfinding وماشي parsing.

هو فقط:
- ياخذ moves.
- يformatihom.
- يلون zones.
- يطبع كل turn.

هاد separation مهم فOOP/SOLID.

## `isatty()`

```python
self.use_color = sys.stdout.isatty()
```

إلا output ماشي terminal، مثلا:

```bash
python3 main.py map.txt > output.txt
```

ما كنطبعوش ANSI codes، باش file يبقى clean.

## True color ANSI

```text
\033[38;2;R;G;Bm
```

كتعطي RGB foreground color.

---

# 17. Main flow

`main.py` صغير عمدا:

```text
CLI arg
  ↓
parser
  ↓
simulation
  ↓
TerminalRender.run()
```

هاد pattern مزيان لأن business logic ماشي مخلوط مع startup code.

Exit codes:

- normal completion: Python implicit `0`.
- `KeyboardInterrupt`: `130`.
- any handled runtime exception: `1`.

---

# 18. Makefile

Targets الحاليين:

```text
make install
make run
make debug
make clean
make lint
make lint-strict
```

`MAP ?= ...` كيعني تقدر تبدل map:

```bash
make run MAP=maps/easy/test.txt
```

`uv` كيعطي reproducible env وتشغيل dependency tools.

قبل push تأكد أن repo فيه فعلا:
- `pyproject.toml`
- lock file إذا كتستعملو
- dependencies `flake8`, `mypy`
لأن Makefile بوحدو ما يكفيش إلا `uv sync` ما عندوش project config.

---

# 19. Complexity analysis اللي خاصك تحفظ

خلي:

- `V` = number of zones
- `E` = number of connections
- `D` = number of drones
- `K` = number of candidate paths (عندك 4)
- `L` = average path length
- `T` = number of simulation turns

## Parser

تقريبا:

```text
O(number_of_lines + duplicate-check overhead)
```

ولكن `validate_connection()` كيعيد scan لجميع connections كل مرة، لذلك worst-case ديال duplicate checking يقدر يوصل:

```text
O(E²)
```

تحسين:
- خزن canonical connection pairs فـ set persistent.
- كل edge check يكون average `O(1)`.

## create_adjs

```text
O(V + E)
```

## reverse Dijkstra

```text
O((V + E) log V)
```

## K-path A* enumeration

ما عندهاش bound بسيط بحال shortest-path Dijkstra حيث كتenumerate simple paths. Worst-case number of simple paths exponential فdense/cyclic graph.

ولكن:
- `K=4`
- heuristic قوية
- blocked/cycles pruning

كيخففو search عملياً.

## path assignment

```text
O(D * K)
```

ومادام K=4 فهي تقريبا linear فعدد drones.

## simulation

تقريبا:

```text
O(T * D * passes)
```

`while progress` يقدر يدير عدة passes فturn، worst-case تقريبا `O(T * D²)` فسيناريوهات معينة.

---

# 20. نقاط قوية فimplementation ديالك

1. separation واضح بين parsing / model / simulation / rendering.
2. custom exceptions.
3. type hints موجودة بكثرة.
4. docstrings موجودة.
5. context manager فالfile reading.
6. graph libs ما مستعملينش.
7. adjacency list مناسبة.
8. reverse shortest-distance heuristic فكرة قوية.
9. blocked pruning.
10. cycle prevention.
11. multiple candidate paths.
12. path load balancing.
13. zone + link capacity support.
14. two-turn restricted state.
15. same-turn capacity release logic.
16. deadlock detection.
17. terminal colors.
18. no colors ملي stdout redirected.
19. deterministic output ordering by drone id.
20. Makefile فيه mandatory rules.

---

# 21. نقاط خاصك تصلح/تكون واعي بها قبل push

## 21.1 `priority` = 0.9

Subject كيقول priority movement cost = 1 turn، but preferred.

الكود كيخلط routing preference مع cost.

الأفضل conceptually:

```python
movement_cost = 1
routing_weight = 0.9
```

ولا تخلي heuristic tie-break يفضل priority بلا ما تبدل actual turn cost.

## 21.2 Method `dijkstra()` هي فعليا A*-style candidate path search

Rename أحسن، أو على الأقل شرحها بوضوح فREADME/evaluation.

## 21.3 `min_cost()` اسم غير دقيق

راه كيحسب bottleneck capacity.

Rename:
```python
compute_path_capacity()
```

## 21.4 Fixed `k=4`

قد يحد optimization.

تحسين:
```text
k = min(reasonable_limit, function_of_graph_and_drones)
```

## 21.5 `validate_connection()` يقدر يكون O(E²)

دير persistent set:
```python
self.__seen_connections: set[tuple[str, str]] = set()
```

ومن بعد كل connection:
```python
key = tuple(sorted((a, b)))
if key in self.__seen_connections:
    error
self.__seen_connections.add(key)
```

## 21.6 Color list محدودة فrenderer

Subject كيقول color metadata ممكن تكون أي single-word string وما كايناش fixed allowed list.
Parser ديالك كيقبلها، مزيان.
Renderer كيcolori غير colors المعروفة فdictionary؛ unknown color كيبقى plain text.

خاصك تقدر تشرح:
> parsing accepts any color; rendering provides visual feedback for supported terminal color mappings and safely falls back to no color for unknown names.

## 21.7 Extra summary output

```text
Total turns: ...
Drones delivered: ...
```

subject كيشجع optional secondary metrics، ولكن evaluator/script صارم يقدر يتوقع غير movement lines.

الأكثر أمانا:
- يا إما دير summary optional flag.
- يا إما stderr.
- يا إما تأكد evaluation كيقبل extra output.

## 21.8 Start/end capacity

Subject كيقول ما عندهمش capacity limit.
انت كتخلي `max_drones = total number of drones`.
عمليا هادي كافية لأن ما يمكنش يكون أكثر من total fleet، ولكن semantic value ماشي infinity.

إلا بغيتي exact model:
```python
max_drones = float("inf")
```
لكن غادي تحتاج تراجع types.

## 21.9 Path cost كيجمع cost ديال start zone

```python
for zone in path:
    cost += self.zones[zone].cost
```

actual movement cost كيبدأ من destination بعد start، ماشي start نفسها.

حيت start constant فكل paths، ranking غالبا ما كتتبدلش. ولكن أنظف:

```python
for zone in path[1:]:
    ...
```

## 21.10 Tests و README ما عطيتينيهمش

قبل push:
- `README.md` mandatory.
- tests مشي graded حسب subject ولكن strongly recommended.
- `.gitignore` recommended.
- تأكد project config ديال `uv` موجود.

---

# 22. Test plan قبل push

خاصك تجرب على الأقل هاد categories:

### Parser success
- minimal valid map.
- metadata reordered.
- inline comments.
- empty/comment lines.
- connection default capacity.

### Parser errors
- no nb_drones.
- nb_drones = 0.
- nb_drones negative.
- duplicate start.
- duplicate end.
- duplicate zone name.
- duplicate coordinates.
- invalid x/y.
- dash in name.
- invalid zone type.
- unknown metadata key.
- max_drones string.
- max_drones 0.
- connection to unknown zone.
- duplicate `a-b` then `b-a`.
- malformed metadata.
- connection before start/end.

### Simulation
- direct start-end.
- one intermediate normal.
- restricted destination.
- blocked shortcut + valid alternate path.
- two parallel paths.
- zone capacity >1.
- link capacity >1.
- bottleneck path.
- overlapping paths.
- same-turn evacuation/refill.
- deadlock case.
- multiple drones.
- many drones.

### Output
- IDs begin at D1.
- one line per turn.
- waiting drones omitted.
- restricted transit label correct.
- final arrivals correct.
- redirected output has no ANSI codes.

---

# 23. Example mental simulation

خد:

```text
nb_drones: 2
start_hub: S 0 0
end_hub: E 2 0
hub: R 1 0 [zone=restricted max_drones=1]
connection: S-R
connection: R-E
```

### Initial

```text
S.capacity = 2
R.capacity = 0
E.capacity = 0
```

### Turn 1

D1 tries S → R:
- R free.
- connection free.
- S.capacity = 1
- R.capacity = 1 **reservation**
- D1.in_connection = True
- output `D1-S-R`

D2 tries:
- R.capacity == max => waits.

### Turn 2

D1 MUST arrive at R:
- zone becomes R
- in_connection False
- path index increments
- output `D1-R`

من بعد فـ same turn D1 ما يتحركش مرة ثانية لأن `moved` set.

D2 مازال ما يقدرش يحجز R حتى R تفرغ فturn آخر.

هاد النوع ديال walkthrough evaluator يقدر يطلبو منك.

---

# 24. أسئلة Evaluation محتملة + أجوبة بالدارجة

## Q: علاش استعملتي adjacency list؟
**A:** حيت graph غالبا sparse، adjacency list كتستهلك `O(V+E)` memory وكتخليني نوصل neighbors مباشرة بلا matrix `O(V²)`.

## Q: واش algorithm ديالك Dijkstra؟
**A:** عندي reverse Dijkstra فـ `distance_to_end()` كيحسب exact remaining cost. من بعد candidate path search كتستعمل priority `g+h`, يعني أقرب لـ A*. اسم method `dijkstra()` historical وممكن يتسمى أحسن `astar_k_paths`.

## Q: علاش reverse Dijkstra؟
**A:** باش نحسب heuristic من كل node للـ end مرة وحدة ونستعملها أثناء forward search، بدل ما نتخبط فكل اتجاه.

## Q: علاش blocked cost infinity وزدتي skip؟
**A:** infinity كيمثل أنه غير قابل للعبور فmodel، والـ explicit `skip` كيمنع حتى إدخالو للqueue، يعني pruning أسرع وواضح.

## Q: شنو هو bottleneck؟
**A:** أصغر capacity فpath، وهو اللي كيحدد throughput الأعلى ديال route.

## Q: علاش كتreserve restricted destination من أول turn؟
**A:** subject كيمنع drone يبقى وسط connection ينتظر. خاص destination تكون مضمونة قبل transit.

## Q: كيفاش كتضمن drone ما يتحركش جوج مرات فturn؟
**A:** `moved: set[int]`; مباشرة ملي يتحرك كنضيف ID، وأي pass آخر كيتجاهلو.

## Q: علاش عندك `while progress`؟
**A:** باش drone كان blocked يقدر يتحرك من بعد drone آخر خرج من zone وحرر capacity فـ نفس turn، كما كيطلب subject.

## Q: كيف كتكتاشف deadlock؟
**A:** إلا مازال ما ساليناش وما وقع حتى move فturn كامل، كنرمي `Invalid_graph` بدل infinite loop.

## Q: كيفاش كتوزع drones؟
**A:** heuristic `path.cost + existing_drones / capacity`; كتوازن بين route length والcongestion/throughput.

## Q: واش هاد distribution optimal mathematically؟
**A:** لا، heuristic practical. Global optimum ديال multi-agent routing/capacity scheduling أصعب. التحسين ممكن يكون min-cost flow/time-expanded graph، ولكن subject كيمنع graph libs ومحتاج implementation يدوي.

## Q: علاش `connection_dict` فيه direction بجوج؟
**A:** graph bidirectional، وبالتالي lookup `O(1)` سواء move A→B ولا B→A.

## Q: علاش `isatty()`؟
**A:** باش ANSI colors ما يلوثوش output ملي كنديرو redirect ولا pipe.

---

# 25. كيفاش تشرح المشروع فـ 60 ثانية

> "Fly-in هو object-oriented drone routing simulator. كنparse map file فيه zones, metadata, capacities, and bidirectional connections. كنحول graph لـ adjacency list، كنحسب reverse shortest-distance heuristic من end باستعمال Dijkstra، ومن بعد كنستعمل A*-style best-first search باش نجيب حتى أربعة candidate simple paths مع منع blocked zones وcycles. كنحسب bottleneck capacity لكل path وكنوزع drones heuristically حسب path cost وcongestion. فالsimulation كنحترم zone capacity وlink capacity turn by turn، وعندي special two-turn state للrestricted zones مع reservation باش drone ما يبقاش عالق وسط link. Renderer كيخرج movements بالformat المطلوب وكيضيف terminal colors بطريقة ما كتفسدش redirected output."

حاول تقولها بلا حفظ حرفي؛ فهم flow.

---

# 26. README.md mandatory — template بالإنجليزية

> **مهم:** subject كيطلب README بالإنجليزية، لذلك هاد section بالإنجليزية عمدا.

```md
*This project has been created as part of the 42 curriculum by <YOUR_LOGIN>.*

# Fly-in

## Description

Fly-in is an object-oriented Python simulation that routes a fleet of drones from a start hub to an end hub through a weighted, capacity-constrained graph.

The program parses a map file, builds the graph, discovers candidate routes, distributes drones across those routes, simulates movement turn by turn, and prints a visual terminal representation of drone movements.

The main objective is to deliver all drones in as few simulation turns as possible while respecting:

- zone capacities;
- connection capacities;
- blocked zones;
- two-turn restricted-zone movements;
- simultaneous movement rules;
- path conflicts and deadlock constraints.

## Instructions

### Requirements

- Python 3.10+
- uv
- flake8
- mypy

### Install

```bash
make install
```

### Run

```bash
make run MAP=path/to/map.txt
```

### Debug

```bash
make debug MAP=path/to/map.txt
```

### Lint

```bash
make lint
```

### Strict type checking

```bash
make lint-strict
```

### Clean

```bash
make clean
```

## Architecture

- `main.py`: CLI entry point and application orchestration.
- `parser.py`: input parsing and validation.
- `classes.py`: domain models for zones, connections, paths, and drones.
- `simulation.py`: graph construction, pathfinding, path assignment, and turn simulation.
- `render.py`: terminal output and colors.
- `errors.py`: custom exceptions.

## Algorithm Choices and Implementation Strategy

The graph is stored as an adjacency list.

A reverse Dijkstra pass is computed from the end hub to obtain the cheapest remaining cost from every reachable zone.

These values are then used as an A*-style heuristic while enumerating a limited number of simple candidate paths from the start hub to the end hub. Blocked zones and cycles are excluded.

For every candidate path, the simulator computes a bottleneck capacity based on zone/link constraints.

Drones are distributed over candidate paths using an estimated arrival score that combines path cost with current path load:

`estimated_cost = path_cost + assigned_drones / path_capacity`

The simulation then advances in discrete turns. Every turn resets per-link usage, completes mandatory restricted-zone transit first, and repeatedly attempts legal movements so that capacity freed by outgoing drones can be reused during the same turn.

## Visual Representation

Drone movements are printed turn by turn.

Example:

```text
D1-roof1 D2-corridorA
D1-roof2 D2-tunnelB
D1-goal D2-goal
```

Zone colors are rendered with ANSI true-color codes when stdout is an interactive terminal. ANSI codes are disabled automatically when output is redirected to a file or pipe.

## Resources

Classic resources used to understand and implement the project:

- Python documentation — data model, exceptions, typing, file handling.
- Python `heapq` documentation — priority queues.
- Dijkstra's shortest-path algorithm.
- A* search and admissible heuristics.
- Graph adjacency lists.
- Capacity-constrained routing and bottleneck concepts.
- PEP 257 — docstrings.
- mypy documentation.
- flake8 documentation.

### AI Usage

AI was used as a learning and review assistant for:
- discussing algorithmic ideas;
- reviewing edge cases;
- improving explanations and documentation;
- identifying possible code-quality improvements.

All implementation decisions and generated suggestions were reviewed and must be fully understood by the project author before evaluation.
```

بدل `<YOUR_LOGIN>` بالlogin الحقيقي ديالك.

---

# 27. Structure مقترحة للrepo قبل push

```text
.
├── README.md
├── Makefile
├── main.py
├── parser.py
├── classes.py
├── simulation.py
├── render.py
├── errors.py
├── pyproject.toml          # if uv project
├── uv.lock                 # if used
├── .gitignore
└── maps/                   # إلا subject/evaluation كيسمح تبقى عندك
```

subject كيقول files evaluated خاصهم يكونو داخل repository وكيأكد placement at root للمشروع الأساسي.

---

# 28. `.gitignore` مقترح

```gitignore
__pycache__/
*.py[cod]
.venv/
.mypy_cache/
.pytest_cache/
.ruff_cache/
.coverage
htmlcov/
.DS_Store
```

---

# 29. Commands قبل push

```bash
python3 --version
python3 -m py_compile classes.py errors.py main.py parser.py render.py simulation.py

make clean
make install
make lint
make lint-strict
```

من بعد run على maps:

```bash
make run MAP=maps/easy/your_map.txt
make run MAP=maps/medium/your_map.txt
make run MAP=maps/hard/your_map.txt
```

redirect test:

```bash
make run MAP=maps/easy/your_map.txt > out.txt
cat -v out.txt
```

خاص ANSI escape sequences ما يبانوش.

Git:

```bash
git status
git diff
git add README.md Makefile main.py parser.py classes.py simulation.py render.py errors.py .gitignore
git commit -m "Complete Fly-in routing simulation"
git push
```

قبل `git add .` ديما شوف `git status` باش ما تطلعش caches/secrets بالخطأ.

---

# 30. Final push checklist

- [ ] Python 3.10+.
- [ ] `python -m py_compile` كيدوز.
- [ ] `flake8` كيدوز.
- [ ] `mypy` mandatory flags كيدوز.
- [ ] README first line exactly بالشكل المطلوب ومائل.
- [ ] README بالإنجليزية.
- [ ] README فيه Description.
- [ ] README فيه Instructions.
- [ ] README فيه Resources.
- [ ] README فيه AI usage.
- [ ] README فيه detailed algorithm strategy.
- [ ] README فيه visual representation documentation.
- [ ] Makefile targets كاملين.
- [ ] `uv sync` خدام من clean clone.
- [ ] ما كاين حتى graph library ممنوعة.
- [ ] parser كيرفض invalid maps بmessage + line.
- [ ] duplicate reverse edge مرفوض.
- [ ] blocked zones ما كيدخلوش route.
- [ ] restricted zone فعلا 2 turns.
- [ ] zone capacity respected.
- [ ] link capacity respected.
- [ ] waiting drone omitted from output.
- [ ] each drone moves max once/turn.
- [ ] end condition صحيحة.
- [ ] no infinite loop on deadlock.
- [ ] output ordering deterministic.
- [ ] redirect output بلا ANSI.
- [ ] جربتي easy/medium/hard.
- [ ] فاهم كل line وماشي غير حافظها.

---

# 31. حاجة مهمة على current code quality

أنا قدرت نتحقق من أن source files الحاليين **كيcompileو syntax-wise** باستعمال `python3 -m py_compile`.

لكن فالenvironment اللي تستعمل لخلق هاد guide، `flake8` و `mypy` ما كانوش installed، لذلك **ما نقدرش نقول لك أنهم pass** بلا ما تدير `make install`/`make lint` فrepo ديالك.

ما تدفعش final submission وانت ما جربتيش mandatory lint locally.

---

# 32. Mental model واحد يحفظ لك المشروع كامل

فكر فالمشروع هكذا:

```text
PARSER
"واش input صحيح؟"
        ↓
DOMAIN OBJECTS
"شنو عندنا؟ zones, links, drones"
        ↓
GRAPH
"شكون مربوط بشكون وبأي cost؟"
        ↓
PATHFINDING
"شنو أحسن routes الممكنة؟"
        ↓
ASSIGNMENT
"كل drone نعطيه أي route؟"
        ↓
SIMULATION
"فهاد turn شكون يقدر يتحرك قانونيا؟"
        ↓
RENDER
"كيفاش نعرض هاد moves بالformat المطلوب؟"
```

إلا فهمتي هاد pipeline، أي سؤال evaluator غالبا تقدر تربطو بواحد layer.

---


## Appendix — شرح line by line ديال `main.py`

- **L1** — `from parser import parser`  
  **الشرح:** Kayimporti objects mn module `parser` باش had file يقدر يستعمل classes/functions dyalo.
- **L2** — `from errors import Invalid_Argument`  
  **الشرح:** Kayimporti objects mn module `errors` باش had file يقدر يستعمل classes/functions dyalo.
- **L3** — `from render import TerminalRender`  
  **الشرح:** Kayimporti objects mn module `render` باش had file يقدر يستعمل classes/functions dyalo.
- **L4** — `from simulation import simulation`  
  **الشرح:** Kayimporti objects mn module `simulation` باش had file يقدر يستعمل classes/functions dyalo.
- **L5** — `import sys`  
  **الشرح:** Kayimporti standard module `sys` li محتاجو had file.
- **L6** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L7** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L8** — `if __name__ == "__main__":`  
  **الشرح:** Python entry-point guard: had bloc kayخدم غير ila `main.py` تشغّل مباشرة، ماشي ila تـimporta.
- **L9** — `    args = sys.argv`  
  **الشرح:** Kayجيب arguments ديال command line؛ `argv[0]` اسم script و`argv[1]` map path.
- **L10** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L11** — `    try:`  
  **الشرح:** `try`: كيجرب code ممكن يرمي exception باش نتحكمو فالفشل بدل crash عشوائي.
- **L12** — `        if len(args) != 2:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L13** — `            raise Invalid_Argument(f"Argument should be 2 not {len(args)}")`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L14** — `        p = parser(args[1])`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L15** — `        s = simulation(p)`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L16** — `        TerminalRender(s).run()`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L17** — `    except KeyboardInterrupt:`  
  **الشرح:** `except`: كيلتقط exception محدد/عام وكيقرر كيفاش البرنامج يتصرف.
- **L18** — `        print("\nInterrupted", file=sys.stderr)`  
  **الشرح:** Kayطبع output؛ فهاد المشروع output مهم حيث كل turn خاصو يبان كسطر.
- **L19** — `        sys.exit(130)`  
  **الشرح:** Kayسالي process بexit code محدد؛ 0 نجاح، 1 خطأ عام، 130 interruption بـ Ctrl+C.
- **L20** — `    except Exception as e:`  
  **الشرح:** `except`: كيلتقط exception محدد/عام وكيقرر كيفاش البرنامج يتصرف.
- **L21** — `        print(e, file=sys.stderr)`  
  **الشرح:** Kayطبع output؛ فهاد المشروع output مهم حيث كل turn خاصو يبان كسطر.
- **L22** — `        sys.exit(1)`  
  **الشرح:** Kayسالي process بexit code محدد؛ 0 نجاح، 1 خطأ عام، 130 interruption بـ Ctrl+C.

## Appendix — شرح line by line ديال `errors.py`

- **L1** — `class Invalid_Syntax(Exception):`  
  **الشرح:** Ta3rif class `Invalid_Syntax`: had class كتجمع data + behavior مرتبطين بنفس concept.
- **L2** — `    """Raised when the input file does not match the expected syntax.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L3** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L4** — `    Attributes:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L5** — `        message: The human-readable error message.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L6** — `        index: The line number where the error occurred.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L7** — `    """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L8** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L9** — `    def __init__(self, message: str, index: int):`  
  **الشرح:** Constructor: kayتستدعى ملي كنصايبو object جديد وكيهيّأ state الداخلي ديالو.
- **L10** — `        """Create a syntax error annotated with the offending line index.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L11** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L12** — `        Args:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L13** — `            message: The error message.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L14** — `            index: The line number where the error occurred.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L15** — `        """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L16** — `        self.message = message`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.message` باش يبقى متاح لباقي methods.
- **L17** — `        self.index = index`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.index` باش يبقى متاح لباقي methods.
- **L18** — `        super().__init__(`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L19** — `            f"\033[91mError Invalid_Syntax in [line {index}]: \033[0m"`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L20** — `            + message`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L21** — `            )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L22** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L23** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L24** — `class Invalid_Argument(Exception):`  
  **الشرح:** Ta3rif class `Invalid_Argument`: had class كتجمع data + behavior مرتبطين بنفس concept.
- **L25** — `    """Raised when the CLI arguments are invalid.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L26** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L27** — `    Attributes:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L28** — `        message: The human-readable error message.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L29** — `    """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L30** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L31** — `    def __init__(self, message: str):`  
  **الشرح:** Constructor: kayتستدعى ملي كنصايبو object جديد وكيهيّأ state الداخلي ديالو.
- **L32** — `        """Create an argument error with a human-readable message.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L33** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L34** — `        Args:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L35** — `            message: The error message.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L36** — `        """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L37** — `        self.message = message`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.message` باش يبقى متاح لباقي methods.
- **L38** — `        super().__init__("\033[91mError Invalid Argument: \033[0m" + message)`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L39** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L40** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L41** — `class Invalid_graph(Exception):`  
  **الشرح:** Ta3rif class `Invalid_graph`: had class كتجمع data + behavior مرتبطين بنفس concept.
- **L42** — `    """Raised when no valid graph paths can be built.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L43** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L44** — `    Attributes:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L45** — `        message: The human-readable error message.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L46** — `    """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L47** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L48** — `    def __init__(self, message: str):`  
  **الشرح:** Constructor: kayتستدعى ملي كنصايبو object جديد وكيهيّأ state الداخلي ديالو.
- **L49** — `        """Create a graph error with a human-readable message.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L50** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L51** — `        Args:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L52** — `            message: The error message.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L53** — `        """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L54** — `        self.message = message`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.message` باش يبقى متاح لباقي methods.
- **L55** — `        super().__init__("\033[91mError Invalid graph: \033[0m" + message)`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.

## Appendix — شرح line by line ديال `classes.py`

- **L1** — `from typing import Any, Union, Optional`  
  **الشرح:** Kayimporti type hints bach types dyal parameters/returns/containers ykounou واضحين l-mypy.
- **L2** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L3** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L4** — `class zones:`  
  **الشرح:** Ta3rif class `zones`: had class كتجمع data + behavior مرتبطين بنفس concept.
- **L5** — `    def __init__(`  
  **الشرح:** Constructor: kayتستدعى ملي كنصايبو object جديد وكيهيّأ state الداخلي ديالو.
- **L6** — `            self,`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L7** — `            name: str,`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L8** — `            x: int, y: int,`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L9** — `            metadata: Union[Any, dict[str, Any]],`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L10** — `            capacity: int = 0`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L11** — `            ):`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L12** — `        """Initialize a zone from parsed metadata.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L13** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L14** — `        Args:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L15** — `            name: The zone name.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L16** — `            x: The x coordinate.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L17** — `            y: The y coordinate.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L18** — `            metadata: Parsed zone metadata.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L19** — `            capacity: Initial number of drones (or reservations) in the zone.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L20** — `        """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L21** — `        self.name = name`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.name` باش يبقى متاح لباقي methods.
- **L22** — `        self.x = x`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.x` باش يبقى متاح لباقي methods.
- **L23** — `        self.y = y`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.y` باش يبقى متاح لباقي methods.
- **L24** — `        self.type = metadata['zone']`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.type` باش يبقى متاح لباقي methods.
- **L25** — `        self.max_drones = metadata['max_drones']`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.max_drones` باش يبقى متاح لباقي methods.
- **L26** — `        self.capacity = capacity`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.capacity` باش يبقى متاح لباقي methods.
- **L27** — `        self.metadata = metadata`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.metadata` باش يبقى متاح لباقي methods.
- **L28** — `        self.cost: Any`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L29** — `        if self.type == 'normal':`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L30** — `            self.cost = 1`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.cost` باش يبقى متاح لباقي methods.
- **L31** — `        elif self.type == 'priority':`  
  **الشرح:** `elif`: branch إضافي كيتجرب غير إلا الشروط اللي قبل منو ما تحققوش.
- **L32** — `            self.cost = 0.9`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.cost` باش يبقى متاح لباقي methods.
- **L33** — `        elif self.type == 'blocked':`  
  **الشرح:** `elif`: branch إضافي كيتجرب غير إلا الشروط اللي قبل منو ما تحققوش.
- **L34** — `            self.cost = float("inf")`  
  **الشرح:** `infinity`: قيمة sentinel كتعبّر على cost غير قابل للوصول/blocked أو أفضل cost مازال ما تحددش.
- **L35** — `        elif self.type == 'restricted':`  
  **الشرح:** `elif`: branch إضافي كيتجرب غير إلا الشروط اللي قبل منو ما تحققوش.
- **L36** — `            self.cost = 2`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.cost` باش يبقى متاح لباقي methods.
- **L37** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L38** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L39** — `class connection:`  
  **الشرح:** Ta3rif class `connection`: had class كتجمع data + behavior مرتبطين بنفس concept.
- **L40** — `    def __init__(`  
  **الشرح:** Constructor: kayتستدعى ملي كنصايبو object جديد وكيهيّأ state الداخلي ديالو.
- **L41** — `            self,`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L42** — `            connection1: zones,`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L43** — `            connection2: zones,`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L44** — `            metadata: Any`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L45** — `            ):`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L46** — `        """Initialize a connection between two zones.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L47** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L48** — `        Args:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L49** — `            connection1: The first zone.`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L50** — `            connection2: The second zone.`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L51** — `            metadata: Parsed connection metadata.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L52** — `        """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L53** — `        self.connection1 = connection1`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.connection1` باش يبقى متاح لباقي methods.
- **L54** — `        self.connection2 = connection2`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.connection2` باش يبقى متاح لباقي methods.
- **L55** — `        self.max_link_capacity = metadata['max_link_capacity']`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.max_link_capacity` باش يبقى متاح لباقي methods.
- **L56** — `        # number of drones using this connection during the CURRENT turn`  
  **الشرح:** Comment: kayشرح l'intention dyal had الجزء; ma kayتنفذش runtime.
- **L57** — `        # (reset to 0 by the simulation at the start of every turn)`  
  **الشرح:** Comment: kayشرح l'intention dyal had الجزء; ma kayتنفذش runtime.
- **L58** — `        self.drones_in = 0`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.drones_in` باش يبقى متاح لباقي methods.
- **L59** — `        self.metadata = metadata`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.metadata` باش يبقى متاح لباقي methods.
- **L60** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L61** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L62** — `class Path:`  
  **الشرح:** Ta3rif class `Path`: had class كتجمع data + behavior مرتبطين بنفس concept.
- **L63** — `    def __init__(`  
  **الشرح:** Constructor: kayتستدعى ملي كنصايبو object جديد وكيهيّأ state الداخلي ديالو.
- **L64** — `            self,`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L65** — `            id: int,`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L66** — `            path: list[str],`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L67** — `            cost: Any,`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L68** — `            capacity: int`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L69** — `            ):`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L70** — `        """Initialize a path record used to assign drones to routes.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L71** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L72** — `        Args:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L73** — `            id: The path identifier.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L74** — `            path: The ordered list of zone names.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L75** — `            cost: The traversal cost for the path.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L76** — `            capacity: The bottleneck capacity of the path.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L77** — `        """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L78** — `        self.id = id`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.id` باش يبقى متاح لباقي methods.
- **L79** — `        self.path = path`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.path` باش يبقى متاح لباقي methods.
- **L80** — `        self.cost = cost`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.cost` باش يبقى متاح لباقي methods.
- **L81** — `        self.capacity = capacity`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.capacity` باش يبقى متاح لباقي methods.
- **L82** — `        self.exist_drones = 0`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.exist_drones` باش يبقى متاح لباقي methods.
- **L83** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L84** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L85** — `class drone:`  
  **الشرح:** Ta3rif class `drone`: had class كتجمع data + behavior مرتبطين بنفس concept.
- **L86** — `    def __init__(self, id: int, zone: zones, path: Union[Path, None] = None):`  
  **الشرح:** Constructor: kayتستدعى ملي كنصايبو object جديد وكيهيّأ state الداخلي ديالو.
- **L87** — `        """Initialize a drone at a starting zone.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L88** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L89** — `        Args:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L90** — `            id: The drone identifier.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L91** — `            zone: The starting zone.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L92** — `            path: The assigned path, if any.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L93** — `        """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L94** — `        self.id = id`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.id` باش يبقى متاح لباقي methods.
- **L95** — `        self.zone = zone`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.zone` باش يبقى متاح لباقي methods.
- **L96** — `        self.path = path`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.path` باش يبقى متاح لباقي methods.
- **L97** — `        self.index_path = 1`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.index_path` باش يبقى متاح لباقي methods.
- **L98** — `        self.target_zone: zones = zone`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.target_zone: zones` باش يبقى متاح لباقي methods.
- **L99** — `        self.in_connection = False`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.in_connection` باش يبقى متاح لباقي methods.
- **L100** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L101** — `    def movement(self, con: connection) -> Optional[str]:`  
  **الشرح:** Ta3rif method/function `movement`؛ كل مرة كتتستدعى كتنفذ responsibility محددة.
- **L102** — `        """Try to advance the drone one step toward its target zone.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L103** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L104** — `        Args:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L105** — `            con: The connection between the current zone and the target.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L106** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L107** — `        Returns:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L108** — `            The label to print for this move ("zone" or "zone1-zone2"`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L109** — `            while flying toward a restricted zone), or None if the`  
  **الشرح:** Loop `while`: كيبقى يعاود التنفيذ مادام الشرط True.
- **L110** — `            drone had to wait this turn.`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L111** — `        """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L112** — `        if self.in_connection:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L113** — `            # 2nd turn of a restricted move: the drone MUST arrive.`  
  **الشرح:** Comment: kayشرح l'intention dyal had الجزء; ma kayتنفذش runtime.
- **L114** — `            # The target capacity was already reserved on the 1st turn,`  
  **الشرح:** Comment: kayشرح l'intention dyal had الجزء; ma kayتنفذش runtime.
- **L115** — `            # so the reservation simply becomes the real occupancy.`  
  **الشرح:** Comment: kayشرح l'intention dyal had الجزء; ma kayتنفذش runtime.
- **L116** — `            con.drones_in += 1`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L117** — `            self.zone = self.target_zone`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.zone` باش يبقى متاح لباقي methods.
- **L118** — `            self.in_connection = False`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.in_connection` باش يبقى متاح لباقي methods.
- **L119** — `            self.index_path += 1`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.index_path +` باش يبقى متاح لباقي methods.
- **L120** — `            return self.zone.name`  
  **الشرح:** `return`: كيسالي function ويرجع النتيجة للcaller.
- **L121** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L122** — `        if (`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L123** — `            self.target_zone.capacity >= self.target_zone.max_drones`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.target_zone.capacity >` باش يبقى متاح لباقي methods.
- **L124** — `            or con.drones_in >= con.max_link_capacity`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L125** — `        ):`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L126** — `            return None`  
  **الشرح:** `return`: كيسالي function ويرجع النتيجة للcaller.
- **L127** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L128** — `        con.drones_in += 1`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L129** — `        self.zone.capacity -= 1`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.zone.capacity -` باش يبقى متاح لباقي methods.
- **L130** — `        self.target_zone.capacity += 1`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.target_zone.capacity +` باش يبقى متاح لباقي methods.
- **L131** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L132** — `        if self.target_zone.type == "restricted":`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L133** — `            # 1st turn: the drone leaves its zone and flies on the link`  
  **الشرح:** Comment: kayشرح l'intention dyal had الجزء; ma kayتنفذش runtime.
- **L134** — `            self.in_connection = True`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.in_connection` باش يبقى متاح لباقي methods.
- **L135** — `            return f"{self.zone.name}-{self.target_zone.name}"`  
  **الشرح:** `return`: كيسالي function ويرجع النتيجة للcaller.
- **L136** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L137** — `        self.zone = self.target_zone`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.zone` باش يبقى متاح لباقي methods.
- **L138** — `        self.index_path += 1`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.index_path +` باش يبقى متاح لباقي methods.
- **L139** — `        return self.zone.name`  
  **الشرح:** `return`: كيسالي function ويرجع النتيجة للcaller.

## Appendix — شرح line by line ديال `parser.py`

- **L1** — `from errors import Invalid_Syntax`  
  **الشرح:** Kayimporti objects mn module `errors` باش had file يقدر يستعمل classes/functions dyalo.
- **L2** — `from classes import zones, connection`  
  **الشرح:** Kayimporti objects mn module `classes` باش had file يقدر يستعمل classes/functions dyalo.
- **L3** — `from typing import Tuple, Union, Any`  
  **الشرح:** Kayimporti type hints bach types dyal parameters/returns/containers ykounou واضحين l-mypy.
- **L4** — `from io import TextIOWrapper`  
  **الشرح:** Kayimporti objects mn module `io` باش had file يقدر يستعمل classes/functions dyalo.
- **L5** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L6** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L7** — `class parser:`  
  **الشرح:** Ta3rif class `parser`: had class كتجمع data + behavior مرتبطين بنفس concept.
- **L8** — `    """Parse the input file into hubs, connections, and settings.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L9** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L10** — `    Attributes:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L11** — `        path_file: The input file path.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L12** — `        start_hub: The parsed start hub.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L13** — `        end_hub: The parsed end hub.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L14** — `        hub: The list of parsed intermediate hubs.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L15** — `        connection: The list of parsed connections.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L16** — `    """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L17** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L18** — `    def __init__(self, path_file: str) -> None:`  
  **الشرح:** Constructor: kayتستدعى ملي كنصايبو object جديد وكيهيّأ state الداخلي ديالو.
- **L19** — `        """Initialize parser state and immediately read the input file.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L20** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L21** — `        Args:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L22** — `            path_file: The path to the input file.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L23** — `        """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L24** — `        self.path_file = path_file`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.path_file` باش يبقى متاح لباقي methods.
- **L25** — `        self.__first_line: Any = None`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.__first_line: Any` باش يبقى متاح لباقي methods.
- **L26** — `        self.start_hub: zones`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L27** — `        self.end_hub: zones`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L28** — `        self.__unique_names: set[str] = set()`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.__unique_names: set[str]` باش يبقى متاح لباقي methods.
- **L29** — `        self.hub: list[zones] = []`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.hub: list[zones]` باش يبقى متاح لباقي methods.
- **L30** — `        self.__zone_types: list[str] = [`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.__zone_types: list[str]` باش يبقى متاح لباقي methods.
- **L31** — `            "normal", "blocked", "restricted", "priority"`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L32** — `            ]`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L33** — `        self.__connection_link: list[Tuple[str, str]] = []`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.__connection_link: list[Tuple[str, str]]` باش يبقى متاح لباقي methods.
- **L34** — `        self.connection: list[connection] = []`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.connection: list[connection]` باش يبقى متاح لباقي methods.
- **L35** — `        self.__states: list[str] = ["start_hub", "end_hub"]`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.__states: list[str]` باش يبقى متاح لباقي methods.
- **L36** — `        self.__known_types = [`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.__known_types` باش يبقى متاح لباقي methods.
- **L37** — `            "start_hub", "hub", "end_hub", "nb_drones", "connection"`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L38** — `            ]`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L39** — `        self._cor_zones: set[Tuple[int, int]] = set()`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self._cor_zones: set[Tuple[int, int]]` باش يبقى متاح لباقي methods.
- **L40** — `        self.read_file()`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L41** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L42** — `    def read_file(self) -> None:`  
  **الشرح:** Ta3rif method/function `read_file`؛ كل مرة كتتستدعى كتنفذ responsibility محددة.
- **L43** — `        """Open the input file and validate its content line by line."""`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L44** — `        with open(self.path_file) as file:`  
  **الشرح:** Context manager: كيفتح file وكيضمن الإغلاق التلقائي حتى إلا وقع exception.
- **L45** — `            self.validate_file(file)`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L46** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L47** — `    def validate_file(self, file: TextIOWrapper) -> None:`  
  **الشرح:** Ta3rif method/function `validate_file`؛ كل مرة كتتستدعى كتنفذ responsibility محددة.
- **L48** — `        """Validate each line and construct the domain objects from it.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L49** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L50** — `        Args:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L51** — `            file: The open file object being parsed.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L52** — `        """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L53** — `        metadata: Union[str, dict[Any, Any], list[str]]`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L54** — `        index = 0`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L55** — `        for index, line in enumerate(file, 1):`  
  **الشرح:** Loop `for`: كيدوز على العناصر واحد بواحد باش يطبق نفس المنطق عليهم.
- **L56** — `            line = line.strip()`  
  **الشرح:** Kayحيد whitespace من البداية والنهاية قبل parsing باش spaces ما يفسدوش syntax.
- **L57** — `            if line.startswith("#") or line == "":`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L58** — `                continue`  
  **الشرح:** `continue`: كيتجاوز بقية هاد iteration ويمشي مباشرة للي بعدها.
- **L59** — `            line = line.split("#", 1)[0]`  
  **الشرح:** Kayقسم string لأجزاء باش parser يقدر يفسر syntax ديال input.
- **L60** — `            p = line.split(":", 1)`  
  **الشرح:** Kayقسم string لأجزاء باش parser يقدر يفسر syntax ديال input.
- **L61** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L62** — `            if p[0] not in self.__known_types:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L63** — `                raise Invalid_Syntax(`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L64** — `                    f"invalid zone_type: {line}", index`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L65** — `                    )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L66** — `            if len(p) != 2:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L67** — `                raise Invalid_Syntax(`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L68** — `                    f"missing ':' after {p[0]}", index`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L69** — `                    )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L70** — `            if (`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L71** — `                p[0] == "nb_drones" and self.__first_line and`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `p[0]` باش يبقى متاح لباقي methods.
- **L72** — `                "nb_drones" not in self.__states`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L73** — `                    ):`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L74** — `                raise Invalid_Syntax(`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L75** — `                    "nb_drones should be in the first line", index`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L76** — `                    )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L77** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L78** — `            elif p[0] == "nb_drones" and self.__first_line is None:`  
  **الشرح:** `elif`: branch إضافي كيتجرب غير إلا الشروط اللي قبل منو ما تحققوش.
- **L79** — `                try:`  
  **الشرح:** `try`: كيجرب code ممكن يرمي exception باش نتحكمو فالفشل بدل crash عشوائي.
- **L80** — `                    value = int(p[1])`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L81** — `                    if value <= 0:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L82** — `                        raise ValueError()`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L83** — `                except Exception:`  
  **الشرح:** `except`: كيلتقط exception محدد/عام وكيقرر كيفاش البرنامج يتصرف.
- **L84** — `                    raise Invalid_Syntax(`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L85** — `                        "nb_drones need to be a positiv integer", index`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L86** — `                    )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L87** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L88** — `                self._nb_drones = int(p[1])`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self._nb_drones` باش يبقى متاح لباقي methods.
- **L89** — `                self.__first_line = 1`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.__first_line` باش يبقى متاح لباقي methods.
- **L90** — `            elif self.__first_line is None:`  
  **الشرح:** `elif`: branch إضافي كيتجرب غير إلا الشروط اللي قبل منو ما تحققوش.
- **L91** — `                raise Invalid_Syntax(`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L92** — `                    "nb_drones should be in the first line", index`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L93** — `                    )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L94** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L95** — `            if (`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L96** — `                p[0].lower() == "start_hub" and`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L97** — `                "start_hub" not in self.__states`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L98** — `                    ):`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L99** — `                raise Invalid_Syntax("cant be there multuple start_hub", index)`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L100** — `            elif p[0].lower() == "start_hub" and "start_hub" in self.__states:`  
  **الشرح:** `elif`: branch إضافي كيتجرب غير إلا الشروط اللي قبل منو ما تحققوش.
- **L101** — `                d = p[1].strip().split(None, 3)`  
  **الشرح:** Kayقسم string لأجزاء باش parser يقدر يفسر syntax ديال input.
- **L102** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L103** — `                if len(d) < 3:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L104** — `                    raise Invalid_Syntax(`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L105** — `                        "zones should have only 3 or 4 argument", index`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L106** — `                    )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L107** — `                name = str(d[0])`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L108** — `                try:`  
  **الشرح:** `try`: كيجرب code ممكن يرمي exception باش نتحكمو فالفشل بدل crash عشوائي.
- **L109** — `                    x = int(d[1])`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L110** — `                    y = int(d[2])`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L111** — `                except Exception:`  
  **الشرح:** `except`: كيلتقط exception محدد/عام وكيقرر كيفاش البرنامج يتصرف.
- **L112** — `                    raise Invalid_Syntax("x and y should be integers", index)`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L113** — `                if (x, y) in self._cor_zones:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L114** — `                    raise Invalid_Syntax("x and y already exists", index)`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L115** — `                self._cor_zones.add((x, y))`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L116** — `                if len(d) == 4:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L117** — `                    metadata = d[3]`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L118** — `                else:`  
  **الشرح:** `else`: الحالة المتبقية ملي حتى شرط سابق ما تحقق.
- **L119** — `                    metadata = "[zone=normal color=none max_drones="`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L120** — `                    metadata += f"{self._nb_drones}]"`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `metadata +` باش يبقى متاح لباقي methods.
- **L121** — `                metadata = self.validate_zones_data(`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `metadata` باش يبقى متاح لباقي methods.
- **L122** — `                    name, x, y, metadata, index, "start_hub"`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L123** — `                )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L124** — `                self.start_hub = zones(`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.start_hub` باش يبقى متاح لباقي methods.
- **L125** — `                    name, x, y, metadata, capacity=self._nb_drones`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `name, x, y, metadata, capacity` باش يبقى متاح لباقي methods.
- **L126** — `                    )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L127** — `                self.__states.remove("start_hub")`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L128** — `            if p[0].lower() == "end_hub" and "end_hub" not in self.__states:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L129** — `                raise Invalid_Syntax("cant be there multuple end_hub", index)`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L130** — `            elif p[0].lower() == "end_hub" and "end_hub" in self.__states:`  
  **الشرح:** `elif`: branch إضافي كيتجرب غير إلا الشروط اللي قبل منو ما تحققوش.
- **L131** — `                d = p[1].strip().split(None, 3)`  
  **الشرح:** Kayقسم string لأجزاء باش parser يقدر يفسر syntax ديال input.
- **L132** — `                if len(d) < 3 or len(d) > 4:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L133** — `                    raise Invalid_Syntax(`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L134** — `                        "zones should have only 3 or 4 argument", index`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L135** — `                    )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L136** — `                name = str(d[0])`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L137** — `                try:`  
  **الشرح:** `try`: كيجرب code ممكن يرمي exception باش نتحكمو فالفشل بدل crash عشوائي.
- **L138** — `                    x = int(d[1])`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L139** — `                    y = int(d[2])`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L140** — `                except Exception:`  
  **الشرح:** `except`: كيلتقط exception محدد/عام وكيقرر كيفاش البرنامج يتصرف.
- **L141** — `                    raise Invalid_Syntax("x and y should be integers", index)`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L142** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L143** — `                if (x, y) in self._cor_zones:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L144** — `                    raise Invalid_Syntax("x and y already exists", index)`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L145** — `                self._cor_zones.add((x, y))`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L146** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L147** — `                if len(d) == 4:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L148** — `                    metadata = d[3]`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L149** — `                else:`  
  **الشرح:** `else`: الحالة المتبقية ملي حتى شرط سابق ما تحقق.
- **L150** — `                    metadata = "[zone=normal color=none max_drones=1]"`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L151** — `                metadata = self.validate_zones_data(`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `metadata` باش يبقى متاح لباقي methods.
- **L152** — `                    name, x, y, metadata, index, "end_hub"`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L153** — `                )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L154** — `                self.end_hub = zones(name, x, y, metadata)`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.end_hub` باش يبقى متاح لباقي methods.
- **L155** — `                self.__states.remove("end_hub")`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L156** — `            elif p[0] == "hub":`  
  **الشرح:** `elif`: branch إضافي كيتجرب غير إلا الشروط اللي قبل منو ما تحققوش.
- **L157** — `                d = p[1].strip().split(None, 3)`  
  **الشرح:** Kayقسم string لأجزاء باش parser يقدر يفسر syntax ديال input.
- **L158** — `                if len(d) < 3:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L159** — `                    raise Invalid_Syntax(`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L160** — `                        "zones should have only 3 or 4 argument", index`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L161** — `                    )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L162** — `                name = str(d[0])`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L163** — `                try:`  
  **الشرح:** `try`: كيجرب code ممكن يرمي exception باش نتحكمو فالفشل بدل crash عشوائي.
- **L164** — `                    x = int(d[1])`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L165** — `                    y = int(d[2])`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L166** — `                except Exception:`  
  **الشرح:** `except`: كيلتقط exception محدد/عام وكيقرر كيفاش البرنامج يتصرف.
- **L167** — `                    raise Invalid_Syntax("x and y should be integers", index)`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L168** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L169** — `                if (x, y) in self._cor_zones:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L170** — `                    raise Invalid_Syntax("x and y already exists", index)`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L171** — `                self._cor_zones.add((x, y))`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L172** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L173** — `                if len(d) == 4:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L174** — `                    metadata = d[3]`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L175** — `                else:`  
  **الشرح:** `else`: الحالة المتبقية ملي حتى شرط سابق ما تحقق.
- **L176** — `                    metadata = "[zone=normal color=none max_drones=1]"`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L177** — `                metadata = self.validate_zones_data(`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `metadata` باش يبقى متاح لباقي methods.
- **L178** — `                    name, x, y, metadata, index, "hub"`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L179** — `                    )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L180** — `                self.hub.append(zones(name, x, y, metadata))`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L181** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L182** — `            elif p[0] == ("connection"):`  
  **الشرح:** `elif`: branch إضافي كيتجرب غير إلا الشروط اللي قبل منو ما تحققوش.
- **L183** — `                if self.__states != []:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L184** — `                    raise Invalid_Syntax("missing start_hub or end_hub", index)`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L185** — `                d = p[1].strip().split("-")`  
  **الشرح:** Kayقسم string لأجزاء باش parser يقدر يفسر syntax ديال input.
- **L186** — `                if len(d) != 2:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L187** — `                    raise Invalid_Syntax(`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L188** — `                        'connection should be on this format "hub1-hub2"',`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L189** — `                        index`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L190** — `                    )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L191** — `                metadata = d[1].split()`  
  **الشرح:** Kayقسم string لأجزاء باش parser يقدر يفسر syntax ديال input.
- **L192** — `                if len(metadata) != 2:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L193** — `                    metadata = "[max_link_capacity=1]"`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L194** — `                else:`  
  **الشرح:** `else`: الحالة المتبقية ملي حتى شرط سابق ما تحقق.
- **L195** — `                    d[1], metadata = d[1].split()`  
  **الشرح:** Kayقسم string لأجزاء باش parser يقدر يفسر syntax ديال input.
- **L196** — `                if (`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L197** — `                    d[1] not in self.__unique_names or`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L198** — `                    d[0] not in self.__unique_names`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L199** — `                        ):`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L200** — `                    raise Invalid_Syntax(`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L201** — `                        f"unkown zone_name : ({d[0]}, {d[1]})", index`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L202** — `                        )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L203** — `                self.__connection_link.append((d[0], d[1]))`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L204** — `                self.validate_connection(index)`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L205** — `                metadata = self.validate_metadata(`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `metadata` باش يبقى متاح لباقي methods.
- **L206** — `                    metadata, "connection", index, None`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L207** — `                    )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L208** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L209** — `                # find the object of the first connection`  
  **الشرح:** Comment: kayشرح l'intention dyal had الجزء; ma kayتنفذش runtime.
- **L210** — `                if d[0] == self.end_hub.name:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L211** — `                    connection1 = self.end_hub`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `connection1` باش يبقى متاح لباقي methods.
- **L212** — `                elif d[0] == self.start_hub.name:`  
  **الشرح:** `elif`: branch إضافي كيتجرب غير إلا الشروط اللي قبل منو ما تحققوش.
- **L213** — `                    connection1 = self.start_hub`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `connection1` باش يبقى متاح لباقي methods.
- **L214** — `                else:`  
  **الشرح:** `else`: الحالة المتبقية ملي حتى شرط سابق ما تحقق.
- **L215** — `                    connection1 = [i for i in self.hub if i.name == d[0]][0]`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `connection1` باش يبقى متاح لباقي methods.
- **L216** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L217** — `                # find the object of the second connection`  
  **الشرح:** Comment: kayشرح l'intention dyal had الجزء; ma kayتنفذش runtime.
- **L218** — `                if d[1] == self.start_hub.name:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L219** — `                    connection2 = self.start_hub`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `connection2` باش يبقى متاح لباقي methods.
- **L220** — `                elif d[1] == self.end_hub.name:`  
  **الشرح:** `elif`: branch إضافي كيتجرب غير إلا الشروط اللي قبل منو ما تحققوش.
- **L221** — `                    connection2 = self.end_hub`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `connection2` باش يبقى متاح لباقي methods.
- **L222** — `                else:`  
  **الشرح:** `else`: الحالة المتبقية ملي حتى شرط سابق ما تحقق.
- **L223** — `                    connection2 = [i for i in self.hub if i.name == d[1]][0]`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `connection2` باش يبقى متاح لباقي methods.
- **L224** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L225** — `                self.connection.append(`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L226** — `                    connection(connection1, connection2, metadata)`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L227** — `                    )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L228** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L229** — `        if self.__first_line is None:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L230** — `            raise Invalid_Syntax("missing nb_drones (empty file?)", index)`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L231** — `        if self.__states != []:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L232** — `            raise Invalid_Syntax(`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L233** — `                f"missing {' and '.join(self.__states)}", index`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L234** — `                )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L235** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L236** — `    def validate_zones_data(self,`  
  **الشرح:** Ta3rif method/function `validate_zones_data`؛ كل مرة كتتستدعى كتنفذ responsibility محددة.
- **L237** — `                            name: str,`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L238** — `                            x: int,`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L239** — `                            y: int,`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L240** — `                            metadata: str,`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L241** — `                            index: int,`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L242** — `                            zone_type: str`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L243** — `                            ) -> Any:`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L244** — `        """Validate zone naming rules and normalize zone metadata.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L245** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L246** — `        Args:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L247** — `            name: The zone name.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L248** — `            x: The x coordinate.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L249** — `            y: The y coordinate.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L250** — `            zone_type: The zone role being validated.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L251** — `            metadata: The raw metadata string.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L252** — `            index: The current line number.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L253** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L254** — `        Returns:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L255** — `            A normalized metadata dictionary.`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L256** — `        """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L257** — `        if len([i for i in name if i == "-" or i == " "]) != 0:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L258** — `            raise Invalid_Syntax(`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L259** — `                f"name of {zone_type} cant have a space or dashes", index`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L260** — `            )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L261** — `        if name in self.__unique_names:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L262** — `            raise Invalid_Syntax("name of zones should be uniq", index)`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L263** — `        else:`  
  **الشرح:** `else`: الحالة المتبقية ملي حتى شرط سابق ما تحقق.
- **L264** — `            self.__unique_names.add(name)`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L265** — `        return self.validate_metadata(metadata, "zones", index, zone_type)`  
  **الشرح:** `return`: كيسالي function ويرجع النتيجة للcaller.
- **L266** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L267** — `    def validate_metadata(`  
  **الشرح:** Ta3rif method/function `validate_metadata`؛ كل مرة كتتستدعى كتنفذ responsibility محددة.
- **L268** — `            self,`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L269** — `            metadata: str,`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L270** — `            type_metadata: str,`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L271** — `            index: int,`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L272** — `            zone_type: Union[str, None]`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L273** — `            ) -> dict[Any, Any]:`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L274** — `        """Parse and validate metadata blocks for zones and connections.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L275** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L276** — `        Args:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L277** — `            metadata: The raw metadata string.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L278** — `            type_metadata: The metadata category to parse.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L279** — `            index: The current line number.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L280** — `            zone_type: The zone role when parsing zone metadata.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L281** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L282** — `        Returns:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L283** — `            A normalized metadata dictionary.`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L284** — `        """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L285** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L286** — `        data: dict[Any, Any] = {}`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L287** — `        if type_metadata == "zones":`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L288** — `            allowed_metadata = ["zone", "color", "max_drones"]`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L289** — `            data["zone"] = "normal"`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L290** — `            data["color"] = "none"`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L291** — `            if zone_type == "start_hub" or zone_type == "end_hub":`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L292** — `                data["max_drones"] = self._nb_drones`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `data["max_drones"]` باش يبقى متاح لباقي methods.
- **L293** — `            else:`  
  **الشرح:** `else`: الحالة المتبقية ملي حتى شرط سابق ما تحقق.
- **L294** — `                data["max_drones"] = 1`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L295** — `            if metadata[0] == "[" and metadata[-1] == "]":`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L296** — `                p = metadata[1:-1]`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L297** — `                parts = p.split()`  
  **الشرح:** Kayقسم string لأجزاء باش parser يقدر يفسر syntax ديال input.
- **L298** — `                for i in parts:`  
  **الشرح:** Loop `for`: كيدوز على العناصر واحد بواحد باش يطبق نفس المنطق عليهم.
- **L299** — `                    sp = i.split("=")`  
  **الشرح:** Kayقسم string لأجزاء باش parser يقدر يفسر syntax ديال input.
- **L300** — `                    if len(sp) != 2:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L301** — `                        raise Invalid_Syntax(`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L302** — `                            "metadata should be like this [color=red]",`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L303** — `                            index`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L304** — `                        )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L305** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L306** — `                    if sp[0] not in allowed_metadata:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L307** — `                        raise Invalid_Syntax(`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L308** — `                            "Unknown metada type in zones", index`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L309** — `                            )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L310** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L311** — `                    if sp[0] == "zone":`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L312** — `                        if sp[1] not in self.__zone_types:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L313** — `                            raise Invalid_Syntax(`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L314** — `                                "invalid zone type in metadata", index`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L315** — `                                )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L316** — `                        data[sp[0]] = sp[1]`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L317** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L318** — `                    elif sp[0] == "color":`  
  **الشرح:** `elif`: branch إضافي كيتجرب غير إلا الشروط اللي قبل منو ما تحققوش.
- **L319** — `                        data[sp[0]] = sp[1]`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L320** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L321** — `                    elif sp[0] == "max_drones":`  
  **الشرح:** `elif`: branch إضافي كيتجرب غير إلا الشروط اللي قبل منو ما تحققوش.
- **L322** — `                        try:`  
  **الشرح:** `try`: كيجرب code ممكن يرمي exception باش نتحكمو فالفشل بدل crash عشوائي.
- **L323** — `                            if (`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L324** — `                                zone_type != "end_hub"`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L325** — `                                and zone_type != "start_hub"`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L326** — `                                    ):`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L327** — `                                data[sp[0]] = int(sp[1])`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L328** — `                        except Exception:`  
  **الشرح:** `except`: كيلتقط exception محدد/عام وكيقرر كيفاش البرنامج يتصرف.
- **L329** — `                            raise Invalid_Syntax(`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L330** — `                                "max_drones should be integer not string",`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L331** — `                                index`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L332** — `                            )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L333** — `                        if data[sp[0]] <= 0:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L334** — `                            raise Invalid_Syntax(`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L335** — `                                "max_drones should be positiv integer",`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L336** — `                                index`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L337** — `                                )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L338** — `            else:`  
  **الشرح:** `else`: الحالة المتبقية ملي حتى شرط سابق ما تحقق.
- **L339** — `                raise Invalid_Syntax("Invalid syntax of metadata", index)`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L340** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L341** — `        elif type_metadata == "connection":`  
  **الشرح:** `elif`: branch إضافي كيتجرب غير إلا الشروط اللي قبل منو ما تحققوش.
- **L342** — `            message = "syntax in metada should be like"`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L343** — `            message += "this [max_link_capacity=5]"`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L344** — `            allowed_metadata = ["max_link_capacity"]`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L345** — `            data["max_link_capacity"] = 1`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L346** — `            if metadata[0] == "[" and metadata[-1] == "]":`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L347** — `                p = metadata[1:-1:]`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L348** — `                parts = p.split("=")`  
  **الشرح:** Kayقسم string لأجزاء باش parser يقدر يفسر syntax ديال input.
- **L349** — `                if len(parts) != 2:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L350** — `                    raise Invalid_Syntax(`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L351** — `                        message,`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L352** — `                        index,`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L353** — `                    )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L354** — `                if parts[0] not in allowed_metadata:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L355** — `                    raise Invalid_Syntax(`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L356** — `                        "Unkown metadata type in connection", index`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L357** — `                        )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L358** — `                try:`  
  **الشرح:** `try`: كيجرب code ممكن يرمي exception باش نتحكمو فالفشل بدل crash عشوائي.
- **L359** — `                    data[parts[0]] = int(parts[1])`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L360** — `                except Exception:`  
  **الشرح:** `except`: كيلتقط exception محدد/عام وكيقرر كيفاش البرنامج يتصرف.
- **L361** — `                    raise Invalid_Syntax(`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L362** — `                        "max_link_capacity should be integer not string", index`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L363** — `                    )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L364** — `                if data[parts[0]] <= 0:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L365** — `                    raise Invalid_Syntax(`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L366** — `                        "max_link capacity should be positiv integer",`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L367** — `                        index`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L368** — `                        )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L369** — `            else:`  
  **الشرح:** `else`: الحالة المتبقية ملي حتى شرط سابق ما تحقق.
- **L370** — `                raise Invalid_Syntax(message, index)`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L371** — `        return data`  
  **الشرح:** `return`: كيسالي function ويرجع النتيجة للcaller.
- **L372** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L373** — `    def validate_connection(self, index: int) -> None:`  
  **الشرح:** Ta3rif method/function `validate_connection`؛ كل مرة كتتستدعى كتنفذ responsibility محددة.
- **L374** — `        """Reject duplicate connections regardless of endpoint order.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L375** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L376** — `        Args:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L377** — `            index: The current line number.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L378** — `        """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L379** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L380** — `        vis = set()`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L381** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L382** — `        for a, b in self.__connection_link:`  
  **الشرح:** Loop `for`: كيدوز على العناصر واحد بواحد باش يطبق نفس المنطق عليهم.
- **L383** — `            modified = tuple(sorted((a, b)))`  
  **الشرح:** Kayرتب endpoint names باش `a-b` و`b-a` يعطيو نفس canonical pair لاكتشاف duplicate edge.
- **L384** — `            if modified in vis:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L385** — `                raise Invalid_Syntax(`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L386** — `                    f"the connection ({a}, {b}) are duplicable", index`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L387** — `                    )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L388** — `            else:`  
  **الشرح:** `else`: الحالة المتبقية ملي حتى شرط سابق ما تحقق.
- **L389** — `                vis.add(modified)`  
  **الشرح:** Kayضيف عنصر لـ set؛ set مفيد للتحقق من uniqueness بسرعة.

## Appendix — شرح line by line ديال `simulation.py`

- **L1** — `from parser import parser`  
  **الشرح:** Kayimporti objects mn module `parser` باش had file يقدر يستعمل classes/functions dyalo.
- **L2** — `from classes import drone, Path, connection`  
  **الشرح:** Kayimporti objects mn module `classes` باش had file يقدر يستعمل classes/functions dyalo.
- **L3** — `from errors import Invalid_graph`  
  **الشرح:** Kayimporti objects mn module `errors` باش had file يقدر يستعمل classes/functions dyalo.
- **L4** — `from typing import Union, Any, Optional`  
  **الشرح:** Kayimporti type hints bach types dyal parameters/returns/containers ykounou واضحين l-mypy.
- **L5** — `import heapq`  
  **الشرح:** Kayimporti standard module `heapq` li محتاجو had file.
- **L6** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L7** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L8** — `class simulation:`  
  **الشرح:** Ta3rif class `simulation`: had class كتجمع data + behavior مرتبطين بنفس concept.
- **L9** — `    """Build paths through the parsed graph and drive drone movement.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L10** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L11** — `    Attributes:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L12** — `        zones: A mapping of zone names to zone objects.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L13** — `        start_hub: The parsed start hub.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L14** — `        end_hub: The parsed end hub.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L15** — `        connection_list: The parsed connections.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L16** — `        nb_drones: The number of drones in the simulation.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L17** — `        drones: The drone objects controlled by the simulation.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L18** — `    """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L19** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L20** — `    def __init__(self, data_parsing: parser):`  
  **الشرح:** Constructor: kayتستدعى ملي كنصايبو object جديد وكيهيّأ state الداخلي ديالو.
- **L21** — `        """Initialize the simulation graph, paths, and drone fleet.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L22** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L23** — `        Args:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L24** — `            data_parsing: The parsed input data.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L25** — `        """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L26** — `        self.zones = {i.name: i for i in data_parsing.hub}`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.zones` باش يبقى متاح لباقي methods.
- **L27** — `        self.zones.update({data_parsing.end_hub.name: data_parsing.end_hub})`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L28** — `        self.zones.update(`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L29** — `            {data_parsing.start_hub.name: data_parsing.start_hub}`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L30** — `            )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L31** — `        self.start_hub = data_parsing.start_hub`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.start_hub` باش يبقى متاح لباقي methods.
- **L32** — `        self.end_hub = data_parsing.end_hub`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.end_hub` باش يبقى متاح لباقي methods.
- **L33** — `        self.connection_list = data_parsing.connection`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.connection_list` باش يبقى متاح لباقي methods.
- **L34** — `        self.nb_drones = data_parsing._nb_drones`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.nb_drones` باش يبقى متاح لباقي methods.
- **L35** — `        # drone ids start at 1 to match the subject output (D1, D2, ...)`  
  **الشرح:** Comment: kayشرح l'intention dyal had الجزء; ma kayتنفذش runtime.
- **L36** — `        self.drones = [`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.drones` باش يبقى متاح لباقي methods.
- **L37** — `            drone(i, self.start_hub) for i in range(1, self.nb_drones + 1)`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L38** — `        ]`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L39** — `        self.nb_turn = 0`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.nb_turn` باش يبقى متاح لباقي methods.
- **L40** — `        self.create_adjs()`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L41** — `        self.dijkstra(self.start_hub.name, 4)`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L42** — `        self.min_cost()`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L43** — `        self.assign_path_to_drone()`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L44** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L45** — `    def create_adjs(self) -> None:`  
  **الشرح:** Ta3rif method/function `create_adjs`؛ كل مرة كتتستدعى كتنفذ responsibility محددة.
- **L46** — `        """Build adjacency lists and a connection lookup table.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L47** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L48** — `        Connections are bidirectional, so both directions are added.`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L49** — `        """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L50** — `        self.adjs: dict[`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L51** — `            str,`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L52** — `            list[tuple[str, Union[int, float]]]`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L53** — `            ] = {i: [] for i in self.zones.keys()}`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `]` باش يبقى متاح لباقي methods.
- **L54** — `        self.connection_dict: dict[tuple[str, str], connection] = {}`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.connection_dict: dict[tuple[str, str], connection]` باش يبقى متاح لباقي methods.
- **L55** — `        for i in self.connection_list:`  
  **الشرح:** Loop `for`: كيدوز على العناصر واحد بواحد باش يطبق نفس المنطق عليهم.
- **L56** — `            a = i.connection1`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L57** — `            b = i.connection2`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L58** — `            self.adjs[a.name].append((b.name, b.cost))`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L59** — `            self.adjs[b.name].append((a.name, a.cost))`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L60** — `            self.connection_dict[(a.name, b.name)] = i`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.connection_dict[(a.name, b.name)]` باش يبقى متاح لباقي methods.
- **L61** — `            self.connection_dict[(b.name, a.name)] = i`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.connection_dict[(b.name, a.name)]` باش يبقى متاح لباقي methods.
- **L62** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L63** — `    def distance_to_end(self) -> dict[str, float]:`  
  **الشرح:** Ta3rif method/function `distance_to_end`؛ كل مرة كتتستدعى كتنفذ responsibility محددة.
- **L64** — `        """Compute the cheapest cost from every zone to the end hub.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L65** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L66** — `        A normal Dijkstra started from the end hub. Moving u -> v costs`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L67** — `        the cost of v (the zone we enter), so going backward from v we`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L68** — `        add \`\`zones[v].cost\`\`.`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L69** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L70** — `        Returns:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L71** — `            A mapping zone name -> minimal remaining cost (inf if the end`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L72** — `            hub cannot be reached from that zone).`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L73** — `        """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L74** — `        dist: dict[str, float] = {name: float("inf") for name in self.zones}`  
  **الشرح:** `infinity`: قيمة sentinel كتعبّر على cost غير قابل للوصول/blocked أو أفضل cost مازال ما تحددش.
- **L75** — `        dist[self.end_hub.name] = 0`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `dist[self.end_hub.name]` باش يبقى متاح لباقي methods.
- **L76** — `        queue: list[tuple[float, str]] = [(0, self.end_hub.name)]`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `queue: list[tuple[float, str]]` باش يبقى متاح لباقي methods.
- **L77** — `        while queue:`  
  **الشرح:** Loop `while`: كيبقى يعاود التنفيذ مادام الشرط True.
- **L78** — `            d, v = heapq.heappop(queue)`  
  **الشرح:** Kayخرج أصغر عنصر من min-heap، يعني أفضل candidate حسب priority الحالية.
- **L79** — `            if d > dist[v]:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L80** — `                continue`  
  **الشرح:** `continue`: كيتجاوز بقية هاد iteration ويمشي مباشرة للي بعدها.
- **L81** — `            for u, _ in self.adjs[v]:`  
  **الشرح:** Loop `for`: كيدوز على العناصر واحد بواحد باش يطبق نفس المنطق عليهم.
- **L82** — `                if self.zones[u].type == 'blocked':`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L83** — `                    continue`  
  **الشرح:** `continue`: كيتجاوز بقية هاد iteration ويمشي مباشرة للي بعدها.
- **L84** — `                new_d = d + self.zones[v].cost`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `new_d` باش يبقى متاح لباقي methods.
- **L85** — `                if new_d < dist[u]:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L86** — `                    dist[u] = new_d`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L87** — `                    heapq.heappush(queue, (new_d, u))`  
  **الشرح:** Kayضيف عنصر للـ min-heap priority queue مع الحفاظ على ترتيب الأولوية O(log n).
- **L88** — `        return dist`  
  **الشرح:** `return`: كيسالي function ويرجع النتيجة للcaller.
- **L89** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L90** — `    def dijkstra(self, start_zone: str, k: int) -> None:`  
  **الشرح:** Ta3rif method/function `dijkstra`؛ كل مرة كتتستدعى كتنفذ responsibility محددة.
- **L91** — `        """Enumerate up to k simple paths from the start hub to the end hub.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L92** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L93** — `        Best-first search (A*): partial paths are ordered by`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L94** — `        \`\`cost so far + cheapest remaining cost\`\`, so the search goes`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L95** — `        straight toward the end hub instead of exploring every direction.`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L96** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L97** — `        Args:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L98** — `            start_zone: The starting zone name.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L99** — `            k: The maximum number of candidate paths to collect.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L100** — `        """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L101** — `        h = self.distance_to_end()`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `h` باش يبقى متاح لباقي methods.
- **L102** — `        self.paths: list[list[str]] = []`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.paths: list[list[str]]` باش يبقى متاح لباقي methods.
- **L103** — `        if h[start_zone] == float("inf"):`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L104** — `            raise Invalid_graph("no paths exist in the graph")`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L105** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L106** — `        # (estimated total, -length, cost so far, zone, path)`  
  **الشرح:** Comment: kayشرح l'intention dyal had الجزء; ma kayتنفذش runtime.
- **L107** — `        # -length: on equal estimates, extend the longest path first`  
  **الشرح:** Comment: kayشرح l'intention dyal had الجزء; ma kayتنفذش runtime.
- **L108** — `        priority_queue: list[Any] = [`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L109** — `            (h[start_zone], -1, 0, start_zone, [start_zone])`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L110** — `            ]`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L111** — `        while priority_queue:`  
  **الشرح:** Loop `while`: كيبقى يعاود التنفيذ مادام الشرط True.
- **L112** — `            _, _, c, zone, path = heapq.heappop(priority_queue)`  
  **الشرح:** Kayخرج أصغر عنصر من min-heap، يعني أفضل candidate حسب priority الحالية.
- **L113** — `            if zone == self.end_hub.name:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L114** — `                self.paths.append(path)`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L115** — `                if len(self.paths) == k:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L116** — `                    return`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L117** — `                continue`  
  **الشرح:** `continue`: كيتجاوز بقية هاد iteration ويمشي مباشرة للي بعدها.
- **L118** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L119** — `            for zone1, c1 in self.adjs[zone]:`  
  **الشرح:** Loop `for`: كيدوز على العناصر واحد بواحد باش يطبق نفس المنطق عليهم.
- **L120** — `                if self.zones[zone1].type == 'blocked':`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L121** — `                    continue`  
  **الشرح:** `continue`: كيتجاوز بقية هاد iteration ويمشي مباشرة للي بعدها.
- **L122** — `                # never visit the same zone twice in one path,`  
  **الشرح:** Comment: kayشرح l'intention dyal had الجزء; ma kayتنفذش runtime.
- **L123** — `                # otherwise cycles make this loop run forever`  
  **الشرح:** Comment: kayشرح l'intention dyal had الجزء; ma kayتنفذش runtime.
- **L124** — `                if zone1 in path or h[zone1] == float("inf"):`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L125** — `                    continue`  
  **الشرح:** `continue`: كيتجاوز بقية هاد iteration ويمشي مباشرة للي بعدها.
- **L126** — `                new_c = c + c1`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L127** — `                heapq.heappush(`  
  **الشرح:** Kayضيف عنصر للـ min-heap priority queue مع الحفاظ على ترتيب الأولوية O(log n).
- **L128** — `                    priority_queue,`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L129** — `                    (new_c + h[zone1], -(len(path) + 1), new_c,`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L130** — `                     zone1, path + [zone1])`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L131** — `                    )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L132** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L133** — `        if self.paths == []:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L134** — `            raise Invalid_graph("no paths exist in the graph")`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L135** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L136** — `    def min_cost(self) -> None:`  
  **الشرح:** Ta3rif method/function `min_cost`؛ كل مرة كتتستدعى كتنفذ responsibility محددة.
- **L137** — `        """Compute the minimum bottleneck capacity for each discovered path."""`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L138** — `        self.min_path_cost: list[Any] = []`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.min_path_cost: list[Any]` باش يبقى متاح لباقي methods.
- **L139** — `        for path in self.paths:`  
  **الشرح:** Loop `for`: كيدوز على العناصر واحد بواحد باش يطبق نفس المنطق عليهم.
- **L140** — `            min_cost = float("inf")`  
  **الشرح:** `infinity`: قيمة sentinel كتعبّر على cost غير قابل للوصول/blocked أو أفضل cost مازال ما تحددش.
- **L141** — `            zone1 = path[0]`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L142** — `            for zone in path[1:]:`  
  **الشرح:** Loop `for`: كيدوز على العناصر واحد بواحد باش يطبق نفس المنطق عليهم.
- **L143** — `                min_cost = min(`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L144** — `                    min_cost,`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L145** — `                    self.zones[zone1].max_drones,`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L146** — `                    self.connection_dict[(zone1, zone)].max_link_capacity`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L147** — `                    )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L148** — `                zone1 = zone`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L149** — `            self.min_path_cost.append(min_cost)`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L150** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L151** — `    def assign_cost(self, path: list[str]) -> Union[float, int]:`  
  **الشرح:** Ta3rif method/function `assign_cost`؛ كل مرة كتتستدعى كتنفذ responsibility محددة.
- **L152** — `        """Return the cumulative traversal cost of a path.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L153** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L154** — `        Args:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L155** — `            path: The ordered list of zone names.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L156** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L157** — `        Returns:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L158** — `            The total path cost.`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L159** — `        """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L160** — `        cost = 0`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L161** — `        for zone in path:`  
  **الشرح:** Loop `for`: كيدوز على العناصر واحد بواحد باش يطبق نفس المنطق عليهم.
- **L162** — `            cost += self.zones[zone].cost`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `cost +` باش يبقى متاح لباقي methods.
- **L163** — `        return cost`  
  **الشرح:** `return`: كيسالي function ويرجع النتيجة للcaller.
- **L164** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L165** — `    def assign_path_to_drone(self) -> None:`  
  **الشرح:** Ta3rif method/function `assign_path_to_drone`؛ كل مرة كتتستدعى كتنفذ responsibility محددة.
- **L166** — `        """Assign each drone to the path where it should arrive the earliest.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L167** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L168** — `        Estimated arrival = path cost + drones already queued / capacity.`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L169** — `        """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L170** — `        path_obj = [`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L171** — `            Path(`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L172** — `                i,`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L173** — `                self.paths[i],`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L174** — `                self.assign_cost(self.paths[i]),`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L175** — `                self.min_path_cost[i]`  
  **الشرح:** Access لstate ديال نفس object (`self`) باش نستعمل attribute/method مرتبط به.
- **L176** — `            )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L177** — `            for i in range(len(self.paths))`  
  **الشرح:** Loop `for`: كيدوز على العناصر واحد بواحد باش يطبق نفس المنطق عليهم.
- **L178** — `        ]`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L179** — `        for d in self.drones:`  
  **الشرح:** Loop `for`: كيدوز على العناصر واحد بواحد باش يطبق نفس المنطق عليهم.
- **L180** — `            best_cost = float("inf")`  
  **الشرح:** `infinity`: قيمة sentinel كتعبّر على cost غير قابل للوصول/blocked أو أفضل cost مازال ما تحددش.
- **L181** — `            best_path: Optional[Path] = None`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L182** — `            for path in path_obj:`  
  **الشرح:** Loop `for`: كيدوز على العناصر واحد بواحد باش يطبق نفس المنطق عليهم.
- **L183** — `                estimate = path.cost + path.exist_drones / path.capacity`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L184** — `                if estimate < best_cost:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L185** — `                    best_cost = estimate`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L186** — `                    best_path = path`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L187** — `            if best_path is None:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L188** — `                raise Invalid_graph("no path available for drones")`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L189** — `            best_path.exist_drones += 1`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L190** — `            d.path = best_path`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L191** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L192** — `    def is_finished(self) -> bool:`  
  **الشرح:** Ta3rif method/function `is_finished`؛ كل مرة كتتستدعى كتنفذ responsibility محددة.
- **L193** — `        """Return True when every drone has reached the end hub."""`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L194** — `        return all(d.zone is self.end_hub for d in self.drones)`  
  **الشرح:** `return`: كيسالي function ويرجع النتيجة للcaller.
- **L195** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L196** — `    def try_move(self, d: drone) -> Optional[str]:`  
  **الشرح:** Ta3rif method/function `try_move`؛ كل مرة كتتستدعى كتنفذ responsibility محددة.
- **L197** — `        """Try to move one drone along its path.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L198** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L199** — `        Args:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L200** — `            d: The drone to move.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L201** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L202** — `        Returns:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L203** — `            The move label, or None if the drone waits.`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L204** — `        """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L205** — `        p: Any = d.path`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L206** — `        d.target_zone = self.zones[p.path[d.index_path]]`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `d.target_zone` باش يبقى متاح لباقي methods.
- **L207** — `        con = self.connection_dict[(d.zone.name, d.target_zone.name)]`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `con` باش يبقى متاح لباقي methods.
- **L208** — `        return d.movement(con)`  
  **الشرح:** `return`: كيسالي function ويرجع النتيجة للcaller.
- **L209** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L210** — `    def turn(self) -> list[tuple[drone, str]]:`  
  **الشرح:** Ta3rif method/function `turn`؛ كل مرة كتتستدعى كتنفذ responsibility محددة.
- **L211** — `        """Advance the simulation by one discrete turn.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L212** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L213** — `        Returns:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L214** — `            The (drone, label) pairs of every drone that moved this turn.`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L215** — `        """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L216** — `        moves: list[tuple[drone, str]] = []`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L217** — `        if self.is_finished():`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L218** — `            return moves`  
  **الشرح:** `return`: كيسالي function ويرجع النتيجة للcaller.
- **L219** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L220** — `        for con in self.connection_list:`  
  **الشرح:** Loop `for`: كيدوز على العناصر واحد بواحد باش يطبق نفس المنطق عليهم.
- **L221** — `            con.drones_in = 0`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L222** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L223** — `        active = [d for d in self.drones if d.zone is not self.end_hub]`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `active` باش يبقى متاح لباقي methods.
- **L224** — `        moved: set[int] = set()`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L225** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L226** — `        # 1) drones flying toward a restricted zone must arrive first`  
  **الشرح:** Comment: kayشرح l'intention dyal had الجزء; ma kayتنفذش runtime.
- **L227** — `        for d in active:`  
  **الشرح:** Loop `for`: كيدوز على العناصر واحد بواحد باش يطبق نفس المنطق عليهم.
- **L228** — `            if d.in_connection:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L229** — `                label = self.try_move(d)`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `label` باش يبقى متاح لباقي methods.
- **L230** — `                if label is not None:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L231** — `                    moves.append((d, label))`  
  **الشرح:** Kayزيد عنصر فآخر list، محافظا على ترتيب الاكتشاف.
- **L232** — `                    moved.add(d.id)`  
  **الشرح:** Kayضيف عنصر لـ set؛ set مفيد للتحقق من uniqueness بسرعة.
- **L233** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L234** — `        progress = True`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L235** — `        while progress:`  
  **الشرح:** Loop `while`: كيبقى يعاود التنفيذ مادام الشرط True.
- **L236** — `            progress = False`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L237** — `            for d in active:`  
  **الشرح:** Loop `for`: كيدوز على العناصر واحد بواحد باش يطبق نفس المنطق عليهم.
- **L238** — `                if d.id in moved:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L239** — `                    continue`  
  **الشرح:** `continue`: كيتجاوز بقية هاد iteration ويمشي مباشرة للي بعدها.
- **L240** — `                label = self.try_move(d)`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `label` باش يبقى متاح لباقي methods.
- **L241** — `                if label is not None:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L242** — `                    moves.append((d, label))`  
  **الشرح:** Kayزيد عنصر فآخر list، محافظا على ترتيب الاكتشاف.
- **L243** — `                    moved.add(d.id)`  
  **الشرح:** Kayضيف عنصر لـ set؛ set مفيد للتحقق من uniqueness بسرعة.
- **L244** — `                    progress = True`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L245** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L246** — `        if not moves:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L247** — `            raise Invalid_graph(`  
  **الشرح:** `raise`: كيرمي exception عمدا ملي input/state مخالف للقواعد.
- **L248** — `                f"deadlock at turn {self.nb_turn + 1}: no drone can move"`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L249** — `            )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L250** — `        self.nb_turn += 1`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.nb_turn +` باش يبقى متاح لباقي methods.
- **L251** — `        moves.sort(key=lambda m: m[0].id)`  
  **الشرح:** Lambda صغيرة كتحدد key ديال الترتيب بلا ما نكتب function منفصلة.
- **L252** — `        return moves`  
  **الشرح:** `return`: كيسالي function ويرجع النتيجة للcaller.

## Appendix — شرح line by line ديال `render.py`

- **L1** — `import sys`  
  **الشرح:** Kayimporti standard module `sys` li محتاجو had file.
- **L2** — `from classes import drone`  
  **الشرح:** Kayimporti objects mn module `classes` باش had file يقدر يستعمل classes/functions dyalo.
- **L3** — `from simulation import simulation`  
  **الشرح:** Kayimporti objects mn module `simulation` باش had file يقدر يستعمل classes/functions dyalo.
- **L4** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L5** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L6** — `class TerminalRender:`  
  **الشرح:** Ta3rif class `TerminalRender`: had class كتجمع data + behavior مرتبطين بنفس concept.
- **L7** — `    """Print the simulation turn by turn in the terminal.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L8** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L9** — `    Each turn is one line of space-separated moves:`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L10** — `    \`\`D<ID>-<zone>\`\` or \`\`D<ID>-<zone1>-<zone2>\`\` while a drone is flying`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L11** — `    toward a restricted zone. Zone names are colored with their metadata`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L12** — `    color when the output is a real terminal.`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L13** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L14** — `    Attributes:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L15** — `        sim: The simulation controller.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L16** — `        use_color: Whether ANSI colors are printed.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L17** — `    """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L18** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L19** — `    COLORS: dict[str, tuple[int, int, int]] = {`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L20** — `        "black": (0, 0, 0),`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L21** — `        "white": (255, 255, 255),`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L22** — `        "red": (255, 0, 0),`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L23** — `        "blue": (0, 120, 255),`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L24** — `        "green": (0, 255, 0),`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L25** — `        "gray": (128, 128, 128),`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L26** — `        "grey": (128, 128, 128),`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L27** — `        "purple": (160, 32, 240),`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L28** — `        "orange": (255, 165, 0),`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L29** — `        "maroon": (128, 0, 0),`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L30** — `        "gold": (255, 215, 0),`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L31** — `        "darkred": (139, 0, 0),`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L32** — `        "crimson": (220, 20, 60),`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L33** — `        "brown": (139, 69, 19),`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L34** — `        "violet": (238, 130, 238),`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L35** — `        "yellow": (255, 255, 0),`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L36** — `        "cyan": (0, 255, 255),`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L37** — `        "magenta": (255, 0, 255),`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L38** — `        "pink": (255, 105, 180),`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L39** — `        "lime": (50, 205, 50),`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L40** — `    }`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L41** — `    RESET = "\033[0m"`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L42** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L43** — `    def __init__(self, sim: simulation) -> None:`  
  **الشرح:** Constructor: kayتستدعى ملي كنصايبو object جديد وكيهيّأ state الداخلي ديالو.
- **L44** — `        """Store the simulation and detect color support.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L45** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L46** — `        Args:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L47** — `            sim: The simulation to display.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L48** — `        """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L49** — `        self.sim = sim`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.sim` باش يبقى متاح لباقي methods.
- **L50** — `        # no ANSI codes when the output is redirected to a file / pipe`  
  **الشرح:** Comment: kayشرح l'intention dyal had الجزء; ma kayتنفذش runtime.
- **L51** — `        self.use_color = sys.stdout.isatty()`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `self.use_color` باش يبقى متاح لباقي methods.
- **L52** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L53** — `    def colorize(self, text: str, color: str) -> str:`  
  **الشرح:** Ta3rif method/function `colorize`؛ كل مرة كتتستدعى كتنفذ responsibility محددة.
- **L54** — `        """Wrap text in an ANSI color code if the color is known.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L55** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L56** — `        Args:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L57** — `            text: The text to color.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L58** — `            color: The color name from the zone metadata.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L59** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L60** — `        Returns:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L61** — `            The colored (or unchanged) text.`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L62** — `        """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L63** — `        rgb = self.COLORS.get(color.lower())`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `rgb` باش يبقى متاح لباقي methods.
- **L64** — `        if not self.use_color or rgb is None:`  
  **الشرح:** Condition `if`: كيتحقق من شرط؛ ila True كيدخل لهاد branch.
- **L65** — `            return text`  
  **الشرح:** `return`: كيسالي function ويرجع النتيجة للcaller.
- **L66** — `        r, g, b = rgb`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L67** — `        return f"\033[38;2;{r};{g};{b}m{text}{self.RESET}"`  
  **الشرح:** `return`: كيسالي function ويرجع النتيجة للcaller.
- **L68** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L69** — `    def format_move(self, d: drone, label: str) -> str:`  
  **الشرح:** Ta3rif method/function `format_move`؛ كل مرة كتتستدعى كتنفذ responsibility محددة.
- **L70** — `        """Format a single drone move like \`\`D1-roof1\`\`.`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L71** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L72** — `        Args:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L73** — `            d: The drone that moved.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L74** — `            label: The destination zone or connection name.`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L75** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L76** — `        Returns:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L77** — `            The formatted move.`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L78** — `        """`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L79** — `        color = str(d.target_zone.metadata["color"])`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L80** — `        return f"D{d.id}-{self.colorize(label, color)}"`  
  **الشرح:** `return`: كيسالي function ويرجع النتيجة للcaller.
- **L81** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L82** — `    def run(self) -> None:`  
  **الشرح:** Ta3rif method/function `run`؛ كل مرة كتتستدعى كتنفذ responsibility محددة.
- **L83** — `        """Run the simulation until all drones are delivered."""`  
  **الشرح:** Docstring: documentation dyal class/function; مهمة لـ PEP 257 w evaluation.
- **L84** — `        while not self.sim.is_finished():`  
  **الشرح:** Loop `while`: كيبقى يعاود التنفيذ مادام الشرط True.
- **L85** — `            moves = self.sim.turn()`  
  **الشرح:** Kayخزن/يحدّث state ديال object فـ `moves` باش يبقى متاح لباقي methods.
- **L86** — `            print(" ".join(self.format_move(d, lbl) for d, lbl in moves))`  
  **الشرح:** Kayطبع output؛ فهاد المشروع output مهم حيث كل turn خاصو يبان كسطر.
- **L87** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L88** — `        summary = (`  
  **الشرح:** Assignment: كيعطي قيمة لمتغير محلي/attribute باش تستعمل لاحقا.
- **L89** — `            f"Total turns: {self.sim.nb_turn} \| "`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L90** — `            f"Drones delivered: {len(self.sim.drones)}"`  
  **الشرح:** هاد السطر جزء من flow ديال logic؛ كيكمل expression أو call السابق حسب indentation والسياق.
- **L91** — `        )`  
  **الشرح:** Delimiter كيساعد فتنظيم expression متعدد الأسطر.
- **L92** — `        print()`  
  **الشرح:** Kayطبع output؛ فهاد المشروع output مهم حيث كل turn خاصو يبان كسطر.
- **L93** — `        print(self.colorize(summary, "cyan"))`  
  **الشرح:** Kayطبع output؛ فهاد المشروع output مهم حيث كل turn خاصو يبان كسطر.

## Appendix — شرح line by line ديال `Makefile`

- **L1** — ``  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L2** — `MAP ?= maps/challenger/01_the_impossible_dream.txt`  
  **الشرح:** `?=` كيعطي default MAP غير إلا المستخدم ما مررش MAP من command line.
- **L3** — ` `  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L4** — `install:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L5** — `	uv sync`  
  **الشرح:** Command باستعمال `uv` لإدارة environment/dependencies وتشغيل الأدوات بشكل reproducible.
- **L6** — ` `  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L7** — `run:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L8** — `	uv run python3 main.py $(MAP)`  
  **الشرح:** Command باستعمال `uv` لإدارة environment/dependencies وتشغيل الأدوات بشكل reproducible.
- **L9** — ` `  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L10** — `debug:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L11** — `	uv run python3 -m pdb main.py $(MAP)`  
  **الشرح:** Command باستعمال `uv` لإدارة environment/dependencies وتشغيل الأدوات بشكل reproducible.
- **L12** — ` `  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L13** — `clean:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L14** — `	rm -rf __pycache__ .mypy_cache .pytest_cache`  
  **الشرح:** Clean command كيحيد caches وtemporary artifacts ديال Python/mypy/pytest.
- **L15** — ` `  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L16** — `lint:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L17** — `	uv run flake8 . --extend-exclude=.venv`  
  **الشرح:** Command باستعمال `uv` لإدارة environment/dependencies وتشغيل الأدوات بشكل reproducible.
- **L18** — `	uv run mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs`  
  **الشرح:** Command باستعمال `uv` لإدارة environment/dependencies وتشغيل الأدوات بشكل reproducible.
- **L19** — ` `  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L20** — `lint-strict:`  
  **الشرح:** Makefile target: rule كتجمع command(s) باش task يتنفذ بأمر واحد.
- **L21** — `	uv run flake8 . --extend-exclude=.venv`  
  **الشرح:** Command باستعمال `uv` لإدارة environment/dependencies وتشغيل الأدوات بشكل reproducible.
- **L22** — `	uv run mypy . --strict`  
  **الشرح:** Command باستعمال `uv` لإدارة environment/dependencies وتشغيل الأدوات بشكل reproducible.
- **L23** — ` `  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.
- **L24** — `.PHONY: install run debug clean lint lint-strict`  
  **الشرح:** Makefile declaration: كيقول لـ make أن هاد targets أسماء أوامر، ماشي files.
- **L25** — ` `  
  **الشرح:** Satr khawi: kayfssel bin blocs bach code يبقى مقروء ومنظم.


---

# 33. آخر نصيحة قبل evaluation

ما تقولش فقط:

> "استعملت Dijkstra."

قول بالضبط:

> "عندي reverse Dijkstra لحساب exact remaining-cost heuristic، ومن بعد best-first/A*-style simple-path enumeration محدود بـ k candidates. من بعد كنحسب path bottleneck وكنوزع drones بـ load-aware heuristic، ثم turn scheduler كيطبق capacities وrestricted two-turn state."

وإلا evaluator بدّل لك حاجة صغيرة:
- إضافة color.
- تغيير output.
- تغيير default capacity.
- رفع `k`.
- rename function.
- إضافة metadata.
- تغيير deadlock message.

خاصك تعرف فين تمشي مباشرة بلا ما تقلب فالمشروع كامل.

هاد هو الفرق بين واحد حافظ code وواحد **فاهم architecture**.
