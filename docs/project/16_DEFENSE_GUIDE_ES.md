# Guía completa de defensa — RAG Against the Machine

## 1. Objetivo de este documento

Este documento prepara la defensa técnica del proyecto mandatory. No sustituye al
README evaluable: el README está en inglés y explica instalación y uso. Aquí se
concentran el relato oral, los invariantes que hay que saber defender, las decisiones,
los riesgos, las preguntas probables y la preparación para un recode corto.

La meta no es memorizar frases. La meta es poder recorrer el sistema desde un archivo
original hasta una respuesta, explicar por qué cada dato conserva su identidad y
justificar con evidencia por qué la solución cumple los límites del subject.

## 2. Resumen ejecutivo de 60 segundos

> El proyecto implementa un RAG completo sobre vLLM 0.10.1. Descubro de forma
> determinista archivos Python, Markdown y texto, y los leo sin normalizar para
> preservar rutas y offsets exactos. Uso dos chunkers: Python se divide alrededor de
> funciones y clases de nivel superior mediante `ast`, mientras que Markdown/texto se
> agrupa por bloques separados por líneas en blanco. Cada chunk conserva el slice
> exacto del archivo y nunca supera 2.000 caracteres.
>
> Persisto los chunks en SQLite y los indexo con FTS5. Las consultas se tokenizan de
> forma segura y se ordenan con BM25. En búsquedas batch reutilizo una conexión y una
> page cache de 64 MiB, elegida después de medir que FTS dominaba el tiempo. El sistema
> supera Recall@5 público con 0.870 en documentación y 0.606 en código. En campus,
> indexó en 10.172 segundos y recuperó 200 preguntas en 8.193 segundos.
>
> Para responder, hidrato cada fuente por ruta y offsets exactos, introduzco un prefijo
> ordenado de chunks completos dentro de un presupuesto real de tokens y genero con
> Qwen3-0.6B en CPU. Python y Pydantic, no el modelo, construyen el JSON. Los errores
> previsibles se traducen en mensajes sin traceback y los outputs batch se reemplazan
> atómicamente.

## 3. Qué exige el subject y cómo se demuestra

### 3.1 Requisitos funcionales

| Requisito | Implementación | Evidencia |
|---|---|---|
| Python 3.10+ | `.python-version` selecciona 3.10; `pyproject.toml` acepta >=3.10 | `uv sync --locked`, CI y mypy |
| uv | Proyecto y lockfile gestionados por uv | Instalación limpia |
| Python Fire | `RagCli` expone todos los comandos | Smokes CLI |
| tqdm | Indexado, búsqueda batch y generación muestran progreso en stderr | Smokes reales |
| Pydantic | Modelos de documentos, chunks, datasets, búsquedas y respuestas | Tests de contratos |
| Dos chunkers | Python estructural y Markdown/texto por bloques | Tests exactos |
| Método lexical | SQLite FTS5 BM25 | Benchmark público |
| Índice persistente | `data/processed/lexical_index.sqlite3` | Recarga y búsqueda sin reindexar |
| Seis comandos | index/search/search_dataset/answer/answer_dataset/evaluate | Rehearsal limpio |
| Qwen3-0.6B | Revisión fijada, CPU float32, greedy, no-thinking | Smokes públicos |
| Fallos sin traceback | Errores conocidos convertidos en FireError | Edge exam 4/4 |

### 3.2 Gates cuantitativos

| Gate | Resultado | Límite |
|---|---:|---:|
| Docs Recall@5 público | 0.870 | >= 0.800 |
| Code Recall@5 público | 0.606 | >= 0.500 |
| Indexado en campus | 10.172 s | <= 300 s |
| 200 búsquedas warm en campus NFS | 8.193 s | <= 90 s |
| Máximo source span | 2.000 caracteres | <= 2.000 |

El holdout privado se utilizó únicamente tras autorización explícita. Los agregados
fueron Docs Recall@5 0.800 y Code Recall@5 0.510. No se inspeccionaron spans privados
para ajustar el sistema y la confirmación posterior de tiempo usó inputs sin respuesta.

## 4. Recorrido completo del pipeline

### 4.1 Descubrimiento y carga

`load_corpus` recibe una raíz configurable y valida que exista. Recorre recursivamente,
acepta `.py`, `.md` y `.txt`, y ordena por ruta POSIX para que el resultado sea
determinista. Cada archivo se abre como UTF-8 con traducción de newline desactivada.

Invariante esencial:

```text
SourceDocument.text == contenido original exacto
SourceDocument.file_path == ruta canónica usada por el evaluador
```

Por qué importa: el evaluador compara `file_path` literalmente y calcula overlap sobre
índices de caracteres. Cambiar CRLF, espacios o prefijos rompe resultados aunque el
texto recuperado parezca correcto.

### 4.2 Chunking Python

El chunker Python usa `ast.parse` para localizar clases, funciones síncronas y
asíncronas de nivel superior. No usa `col_offset` del AST como índice de caracteres:
los offsets de columna del AST pueden estar expresados en bytes UTF-8 y son peligrosos
con Unicode. En su lugar, construye offsets exactos de inicio de línea sobre el string
original.

Comportamiento:

1. Conserva el preámbulo del módulo.
2. Empieza un rango en cada definición estructural superior.
3. Incluye decoradores con la definición.
4. Divide estructuras mayores que el máximo en slices exactos.
5. Si el archivo tiene sintaxis inválida, aplica el fallback acotado.

La estrategia es deliberadamente simple. No intenta reconstruir métodos internos ni
realizar análisis semántico, porque la estructura superior más el límite duro ya cumple
el contrato y mantiene offsets defendibles.

### 4.3 Chunking Markdown/texto

El chunker textual identifica bloques separados por líneas en blanco. Agrupa bloques
adyacentes mientras el rango completo cabe en `max_chunk_size`. Los separadores se
mantienen en el source slice. Un bloque sobredimensionado se divide en segmentos
contiguos exactos.

No existe overlap artificial. Añadir overlap podría mejorar alguna pregunta, pero
duplicaría resultados cercanos y complicaría la interpretación del ranking sin una
necesidad medida.

### 4.4 Construcción y persistencia

El use case de indexado selecciona el chunker por sufijo y construye un
`LexicalIndexBuild` Pydantic con metadata y chunks. El modelo comprueba:

- máximo positivo y <= 2.000;
- número de chunks coherente;
- texto y ancho de cada rango coherentes;
- tipo de chunk válido.

SQLite contiene:

- `metadata`: configuración y contadores serializados;
- `chunks`: ruta, offsets, tipo y texto exacto;
- `chunks_fts`: índice virtual FTS5 sobre el texto.

La base se construye en un archivo temporal cerrado y solo después reemplaza el índice
final. Si falla, se elimina el temporal. Esto evita dejar un índice parcial como si
fuera válido.

### 4.5 Consulta y BM25

La consulta se reduce a tokens Unicode mediante `\w+`. Cada token se cita y los tokens
se unen con `OR`. Esto evita interpretar signos de puntuación del usuario como sintaxis
FTS y permite que una pregunta natural recupere chunks con cualquiera de sus términos.

SQL conceptual:

```text
MATCH <términos citados con OR>
ORDER BY bm25(chunks_fts), chunks.id
LIMIT k
```

`chunks.id` es el desempate estable. La proyección devuelve exclusivamente
`MinimalSource`: ruta y rango exacto.

Casos deliberados:

- `k < 0`: error;
- `k = 0`: resultado vacío válido;
- query vacía o solo puntuación: error claro;
- query sin coincidencias: resultado vacío válido;
- índice ausente/corrupto: error técnico claro.

### 4.6 Búsqueda batch y page cache

`search_dataset` valida el JSON como `RagDataset`, conserva ID, texto y orden, y ejecuta
las preguntas mediante una única conexión SQLite. Antes de consultar solicita:

```text
PRAGMA cache_size=-65536
```

El valor negativo representa KiB, por lo que el máximo solicitado es 64 MiB. SQLite
asigna páginas bajo demanda y libera la cache al cerrar la conexión.

Defensa clave: no es el bonus de cache de queries. No guarda respuestas por pregunta,
no tiene keys ni invalidación y ayuda a preguntas distintas al reutilizar páginas del
índice. La optimización se retuvo porque el profiling atribuyó 99.92% del tiempo local
a FTS. mmap era ligeramente más rápido localmente, pero se rechazó por depender más
del filesystem objetivo NFS.

### 4.7 Evaluación Recall@k

El evaluador local agrupa por `question_id`, rechaza duplicados y valida que cada
source no supere 2.000 caracteres. Para cada source esperado comprueba si algún source
en top-k tiene:

1. la misma ruta exacta;
2. IoU de rangos estrictamente mayor que 0.05.

La métrica por pregunta es la proporción de sources esperados encontrados. El resultado
final es la macro-media de las preguntas con ground truth no vacío. No es hit rate ni
micro-recall.

La herramienta local reproduce los agregados públicos, pero el evaluador oficial usa
Moulinette. El código del estudiante nunca importa ni invoca Moulinette.

### 4.8 Hidratación exacta para respuestas

El flujo `answer` busca una vez. Para cada `MinimalSource`, SQLite consulta por igualdad
en ruta, offset inicial y offset final. Cero filas significa source stale; más de una
significa identidad ambigua. Ambos son errores.

Todas las fuentes se hidratan antes de decidir cuáles caben en el prompt. Así, una
fuente stale no se oculta simplemente porque finalmente quedaría fuera del presupuesto.

### 4.9 Presupuesto de contexto

Defaults:

```text
token_budget = 2048
max_new_tokens = 128
```

Se valida:

```text
0 < max_new_tokens < token_budget <= contexto soportado
prompt_completo + max_new_tokens <= token_budget
```

El contexto soportado es el mínimo entre el límite real del modelo y un límite válido
del tokenizer; valores sentinel enormes del tokenizer se ignoran.

Los chunks se etiquetan con ranking, ruta y offsets. Se añade el prefijo más largo de
chunks completos que cabe. Si el chunk de rank N no cabe, se detiene: no se salta a uno
inferior más corto. Nunca se trunca un fragmento para forzar su entrada.

### 4.10 Qwen

Configuración real:

- modelo: `Qwen/Qwen3-0.6B`;
- revisión fijada: `c1899de289a04d12100db370d81485cdf75e47ca`;
- CPU, float32;
- generación greedy (`do_sample=False`);
- `enable_thinking=False`;
- `trust_remote_code=False`;
- carga lazy de tokenizer y pesos.

El mensaje de sistema obliga a usar solo el contexto y admitir evidencia insuficiente.
Qwen devuelve texto, no JSON. Python introduce ese texto en el modelo Pydantic.

`uv sync` no descarga pesos. La primera ejecución puede descargarlos si hay red. Para
un examen offline hay que preprovisionar la revisión fijada en `models/huggingface` y
usar `--local_files_only=True`.

### 4.11 Answer batch

`answer_dataset` recibe resultados de búsqueda ya calculados. No recupera de nuevo.
Procesa en orden, reutiliza un generador lazy y abre una conexión SQLite solo al llegar
a la primera pregunta con fuentes. Las preguntas sin fuentes abstienen sin SQLite ni
modelo.

El JSON final se escribe en un temporal hermano y se reemplaza atómicamente. Un fallo
de source, modelo, presupuesto o filesystem elimina el temporal y conserva un output
anterior.

## 5. Arquitectura defendible

La arquitectura es un monolito modular, no una implementación ceremonial de
hexagonal. Separaciones reales:

- `domain`: modelos e invariantes Pydantic;
- `application`: casos de uso puros y puertos mínimos;
- `infrastructure`: SQLite, corpus y Transformers;
- `adapters`: CLI Fire;
- `chunking`: algoritmos source-preserving.

Por qué no hay más capas:

- una interfaz con una única implementación sin necesidad real añade ruido;
- no se necesita servicio de base de datos para un índice local;
- no se necesita async para un evaluador CLI CPU-only;
- la API HTTP es bonus y debe reutilizar casos de uso estables cuando exista.

Pregunta probable: “¿Por qué el CLI conoce infraestructura?”

Respuesta: el composition root necesita construir adaptadores concretos. Algunos flujos de
orquestación dataset siguen en el CLI porque solo existe esa frontera mandatory. La lógica
crítica reusable —index build, Recall y respuesta grounded— está en application. Extraer
más antes de un segundo adapter sería abstracción especulativa.

## 6. Decisiones y trade-offs

### BM25 frente a TF-IDF

El subject exige al menos uno. FTS5 ofrece persistencia, tokenización y BM25 dentro de
SQLite estándar, sin añadir una librería o cargar matrices completas por proceso. Es
suficiente para superar los dos gates públicos.

### SQLite frente a motor externo

El índice es local, reproducible y de decenas de MiB. SQLite simplifica instalación,
atomicidad y defensa. Elasticsearch u otro servicio serían desproporcionados y frágiles
en campus.

### Sin embeddings en mandatory

Los embeddings son bonus. Introducirlos antes de pasar mandatory habría añadido pesos,
latencia, persistencia vectorial y tuning. BM25 ya superó Recall@5.

### Sin overlap textual

No hubo necesidad medida. El chunk máximo grande y los bloques completos alcanzaron
0.870 Docs Recall@5. Overlap puede duplicar vecinos en top-k y reducir diversidad.

### Secuencial frente a concurrente

La generación domina y el host es CPU-only. La concurrencia competiría por CPU/RAM y
complicaría orden, progreso y recuperación de fallos. El flujo secuencial es estable y
reutiliza recursos.

### Presupuesto conservador

2.048/128 limita memoria y hace los prompts reproducibles. El contexto arquitectónico
mayor de Qwen no implica que todos los hosts puedan usarlo eficientemente.

## 7. Evidencia de rendimiento y cómo explicarla

### Público

```text
Docs R@1/3/5/10 = 0.600 / 0.780 / 0.870 / 0.890
Code R@1/3/5/10 = 0.354 / 0.545 / 0.606 / 0.667
199 preguntas k=10 = 12.187 s en baseline público
Rehearsal limpio final: index 3.551 s; retrieval 4.926 s combinado
```

El rehearsal final se ejecutó desde un worktree detached, con `.venv` nueva y los
archives públicos suministrados. Reprodujo exactamente los mismos valores de Recall,
por lo que la diferencia de tiempo es evidencia de ejecución del baseline actual, no
de un cambio adicional de ranking.

### Campus

```text
Index = 10.172 s
Docs unanswered 100 = 4.079 s
Code unanswered 100 = 4.114 s
Total = 8.193 s
```

No afirmar que toda la diferencia frente a 92 s sea causalmente la page cache. Cambió
el host y el runner tenía una modificación local no conservada. La afirmación válida es:
el commit mandatory fusionado pasó la carga objetivo sobre campus NFS con margen.

### Generación

El perfil público de diez preguntas atribuyó aproximadamente 91-97% al generate del
modelo. Reducir fuentes, añadir cache de queries o microoptimizar serialización no
resolvería ese coste. Tampoco se redujo `max_new_tokens`, porque eso degradaría calidad
para maquillar tiempo sin un gate de generación equivalente.

## 8. Demo recomendada durante la defensa

Orden corto y observable:

1. Mostrar `uv sync --locked` ya preparado.
2. Ejecutar `make check`.
3. Mostrar ayuda: `uv run python -m src --help`.
4. Indexar con `--max_chunk_size 2000`.
5. Ejecutar un `search` y enseñar ruta/offsets.
6. Ejecutar `search_dataset` sobre un dataset público pequeño o completo.
7. Ejecutar `evaluate` y explicar Recall@k.
8. Ejecutar `answer --k 0` para demostrar abstención sin modelo.
9. Si el cache está preparado, ejecutar la pregunta pública de Volta con `k=1`.
10. Abrir el JSON y señalar que su estructura procede de Pydantic.

Antes de empezar la demo:

- confirmar corpus, datasets e índice;
- confirmar modelo cacheado si se demostrará Qwen;
- no depender de internet;
- usar paths explícitos;
- no ejecutar el holdout privado otra vez.

## 9. Preguntas probables y respuestas

### “¿Cómo garantizas offsets exactos?”

Leo con newline preservation, mantengo el string original, calculo límites sobre ese
string y construyo `chunk.text` con el slice exacto. Pydantic verifica que
`len(text) == end - start`. Tests cubren Unicode, CRLF y reconstrucción.

### “¿Por qué half-open?”

Es la convención de slicing de Python. El ancho es `end - start`, concatenar rangos
contiguos no duplica caracteres y la validación es directa.

### “¿Qué ocurre con Python inválido?”

`ast.parse` puede fallar; entonces uso el splitter exacto acotado. Un archivo inválido
no derriba el indexado completo ni pierde offsets.

### “¿Por qué OR en FTS?”

Una pregunta natural no necesita que todos sus términos aparezcan en el mismo chunk.
Citar tokens evita inyección de sintaxis FTS. BM25 ordena la relevancia entre matches.

### “¿Qué evita resultados no deterministas?”

Descubrimiento ordenado por ruta, chunks en orden estable, IDs secuenciales y desempate
SQL por chunk ID después de BM25.

### “¿Por qué 64 MiB?”

El índice medido era ~35 MiB y el default SQLite ~2 MiB. 32 y 64 MiB dieron ganancias
parecidas; 64 ofrece margen para crecimiento sin reservar todo de golpe. 256 MiB mmap
se rechazó por riesgo NFS.

### “¿Eso no es el bonus de caching?”

No. Es page cache interna y efímera de una conexión. No guarda resultados por query ni
sobrevive al proceso. El bonus #20 necesita persistencia, key, revisión de índice e
invalidación explícita.

### “¿Qué pasa si una fuente ya no existe?”

La hidratación exacta falla. No sustituyo por una región cercana porque eso rompería
la trazabilidad y podría fundamentar la respuesta con evidencia distinta.

### “¿Por qué hidratas fuentes que después no caben?”

Para validar que toda identidad recuperada sigue siendo válida. Si no, una fuente stale
inferior podría quedar oculta por el límite del prompt.

### “¿Por qué no truncas el último chunk?”

Porque el source devuelto representa un fragmento exacto y completo. Truncarlo para el
prompt haría más difícil defender qué evidencia vio el modelo y podría cortar código o
texto en un punto arbitrario.

### “¿Qué pasa sin resultados?”

Se devuelve una abstención fija y no se carga el modelo. Ausencia de evidencia no es
igual a fallo técnico.

### “¿Qué pasa si faltan los pesos?”

Es un error técnico claro. No se convierte en abstención. `uv sync` instala librerías,
no pesos; el cache debe prepararse o debe haber red en la primera ejecución.

### “¿Puede el modelo inventar el JSON?”

No. El modelo solo genera answer text. Pydantic y Python preservan IDs, preguntas,
sources, k y estructura.

### “¿Por qué el código Recall es menor?”

Las preguntas pueden parafrasear conceptos mientras el código contiene identificadores.
BM25 depende de solapamiento lexical. Aun así, 0.606 supera el gate 0.50. La mejora
semántica pertenece al bonus y debe compararse sin eliminar BM25.

### “¿Cómo evitas overfitting privado?”

Todo ajuste se hizo con datos públicos. Del holdout solo se conservaron métricas
agregadas tras autorización; no se inspeccionaron spans por pregunta para modificar
ranking o chunking.

### “¿Por qué no async o threads?”

No lo exige el contrato y la carga es CPU/memoria. Añadir concurrencia antes de medir
sería complejidad sin prueba de beneficio y podría empeorar Qwen.

### “¿Qué cambiarías con más tiempo?”

Primero indexado incremental con manifest e `index_revision`; después retrieval
semántico e híbrido medidos; luego cache persistente correctamente invalidada; por
último una API local sobre los mismos casos de uso.

## 10. Preparación para el recode

El subject permite pedir una modificación breve. Practicar cambios pequeños en los
puntos reales, sin memorizar parches:

### Ejercicio A: añadir un sufijo textual

Localizar el mapa de chunkers del CLI y `SUPPORTED_SUFFIXES`. Explicar que ambos deben
cambiar para que discovery y routing permanezcan alineados. Añadir test de fixture.

### Ejercicio B: cambiar el default de k

Localizar la firma Fire concreta, cambiar solo el comando solicitado y verificar ayuda,
output y tests. No cambiar wrappers Pydantic.

### Ejercicio C: añadir un cutoff a evaluate

Modificar `DEFAULT_CUTOFFS`, explicar macro-recall y comprobar que no cambia matching.

### Ejercicio D: cambiar la instrucción de grounding

Modificar `_SYSTEM_INSTRUCTION`, verificar que counting y generation comparten
`_messages`, y mantener no-thinking.

### Ejercicio E: añadir un campo metadata del índice

Modificar el modelo Pydantic y persistencia de metadata, explicar schema compatibility.
No tocar chunks ni FTS si el campo no afecta retrieval.

### Método durante el recode

1. Repetir el requisito con palabras propias.
2. Localizar definición y usos.
3. Nombrar el invariante que no debe romperse.
4. Escribir o ajustar una comprobación mínima.
5. Hacer el diff más pequeño.
6. Ejecutar test focalizado, Flake8/mypy y explicar resultado.

Nunca improvisar una abstracción nueva durante un recode de minutos.

## 11. Checklist previo a evaluación

### Repositorio

- [ ] `main` apunta al baseline mandatory final.
- [ ] Worktree limpio.
- [ ] Sin datasets, índices, modelos, outputs o binarios evaluadores tracked.
- [ ] `README.md` comienza con la frase exacta y está en inglés.
- [ ] `uv.lock` presente.

### Entorno

- [ ] `uv --version` disponible.
- [ ] Python 3.10+.
- [ ] SQLite tiene FTS5.
- [ ] Espacio suficiente.
- [ ] Corpus y datasets en paths conocidos.
- [ ] Qwen cacheado si no se garantiza red.

### Gates

- [ ] `uv sync --locked`.
- [ ] `make check`.
- [ ] `make lint-strict`.
- [ ] Indexado <= 300 s.
- [ ] 200 búsquedas <= 90 s.
- [ ] Docs/Code Recall@5 >= 0.80/0.50.
- [ ] Edge cases sin traceback.

### Demo

- [ ] Comandos copiados desde README.
- [ ] Output directory limpio o deliberado.
- [ ] Pregunta pública preparada.
- [ ] No ejecutar ground truth privado.

## 12. Límites que hay que declarar honestamente

- Qwen puede ser incompleto con evidencia débil.
- No hay garantía de red o pesos preinstalados en el evaluador.
- Los tiempos de generación dependen mucho del CPU y de la contención.
- BM25 no resuelve bien toda paráfrasis código-lenguaje natural.
- El contexto máximo arquitectónico no equivale a memoria práctica garantizada.
- El dato campus de 8.193 s demuestra cumplimiento, no una atribución causal perfecta.
- Los bonus todavía no forman parte del baseline mandatory.

Declarar límites aumenta credibilidad; ocultarlos crea preguntas más difíciles.

## 13. Qué no decir

Evitar afirmaciones falsas o imprecisas:

- “El sistema es semántico” — todavía no.
- “La cache guarda búsquedas” — la page cache no lo hace.
- “Qwen siempre responde correctamente” — no existe esa evidencia.
- “Probamos todos los contextos de 40k tokens” — no se hizo.
- “El privado se usó para optimizar” — está prohibido y no ocurrió.
- “8.193 s son exclusivamente gracias al PRAGMA” — no es un benchmark causal pareado.
- “answer_dataset vuelve a buscar” — consume resultados previos.

## 14. Cierre oral recomendado

> Priorizamos primero el contrato mandatory: rutas y offsets exactos, dos chunkers,
> BM25 persistente, modelos Pydantic, CLI completa, errores controlados y Qwen
> grounded. Medimos antes de optimizar y solo retuvimos una mejora SQLite pequeña que
> preservaba outputs. El resultado supera Recall y tiempos tanto en público como en
> campus, mantiene el holdout privado blind y deja cada bonus separado detrás de un
> baseline obligatorio estable.

## 15. Referencias internas para repaso

- `README.md`: instalación, comandos y resumen evaluable.
- `docs/project/03_EVALUATION_CONTRACT.md`: gates del corrector.
- `docs/project/09_GENERATION_RUNTIME.md`: Qwen, cache y presupuesto.
- `docs/project/10_GROUNDED_ANSWER.md`: respuesta individual.
- `docs/project/11_ANSWER_DATASET.md`: batch y atomicidad.
- `docs/project/14_CLEAN_CHECKOUT_REHEARSAL.md`: instalación limpia.
- `docs/project/15_RETRIEVAL_PERFORMANCE.md`: profiling, page cache y campus.
- `docs/progress/BENCHMARKS.md`: ledger de métricas.
- `docs/progress/DECISION_LOG.md`: decisiones aceptadas.
