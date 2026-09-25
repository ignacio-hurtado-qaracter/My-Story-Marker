# Guion de la presentación

> Generado por `presentacion/build/build_deck.py` a partir de los mismos datos que el deck (`build/data/runs.json`, evals, TLC, informe de seguridad…). Las cifras coinciden con las diapositivas; si cambian los datos, se regenera. Para cambiar el texto, edita el script, no este fichero.

**Duración estimada:** 14 min 50 s en 20 diapositivas (objetivo 12–15 min). Las notas del orador de cada diapositiva llevan este mismo guion.

**Consejos:** habla a partir de los puntos, no leas. Si vas justo de tiempo, acorta Langfuse (11), contraejemplos (10) y Claude Code (17); no recortes la 14 (novelas bloqueadas): es el argumento central.

## 1. Portada · ≈ 30 s

**Mensaje clave.** Un producto (novelas-regalo) y el harness que lo hace fiable y verificable.

**Qué decir:**

- Buenos días. Soy [tu nombre] y presento My Story Marker.
- Es una solución técnico-comercial: un servicio que escribe novelas personalizadas para regalar, y el harness de agentes que las genera.
- La idea que quiero que os llevéis: aquí lo difícil no es escribir 10 capítulos, es poder demostrar que lo que se publica es coherente y está personalizado.
- Os lo cuento en cuatro partes: el problema, cómo funciona, cómo sabemos que funciona y qué cuesta.

**Cifras que mencionar:** 10 capítulos · 6 roles en Haiku 4.5 · Lean 4 + TLA+

**Transición:** Empiezo por el problema del cliente.

## 2. Problema y propuesta de valor · ≈ 45 s

**Mensaje clave.** El cliente quiere dos cosas a la vez: que el destinatario se reconozca y que la historia se lea bien.

**Qué decir:**

- Clientes: padres, parejas, bodas, jubilaciones. Y un regalo tiene fecha.
- Si se lo pides a un LLM sin más, falla de formas muy concretas: cambia nombres, olvida recuerdos, contradice fechas, y la mascota que murió vuelve a aparecer.
- Además el cliente tiene vetos: el nombre de una expareja, un tema que no quiere. Eso no puede aparecer nunca.
- La propuesta: una entrevista que produce un brief validado, una novela de 10 capítulos, lectura web y PDF con portada, índice y fichas, y cambios puntuales.
- La decisión D11 es el criterio de todo el sistema: personalización y calidad narrativa pesan igual. Meter los datos a martillazos no cuenta como éxito.

**Transición:** Veamos cómo se ve el producto.

## 3. Demo del producto · ≈ 50 s

**Mensaje clave.** El cliente recibe una novela con portada, índice y fichas, y puede pedir un cambio que solo toca lo necesario.

**Qué decir:**

- Estas capturas las tomó el propio sistema: el validador visual abre el lector con Playwright antes de publicar.
- Portada con dedicatoria personalizada, índice navegable, y fichas de personajes y lugares generadas desde la base de datos, con enlaces al capítulo donde aparece cada uno.
- Lo interesante es el cambio: el lector dice «el perro se llama Nala». Ese nombre es un único hecho en la base de datos y sabemos en qué capítulos se usa.
- Solo esos capítulos se regeneran, en una versión nueva. La anterior se conserva y el índice marca qué ha cambiado; el PDF lleva una página de novedades.
- Lo probamos de verdad: cero apariciones del nombre antiguo, dieciséis del nuevo, y la versión 1 intacta.

**Cifras que mencionar:** v1 conservada · 0 nombres antiguos / 16 nuevos

**Transición:** ¿Qué hay detrás? La arquitectura.

## 4. Arquitectura del harness · ≈ 50 s

**Mensaje clave.** Seis roles con un solo trabajo cada uno; el código decide, los modelos solo redactan.

**Qué decir:**

- El entrevistador produce el brief; el planner, el plan con reparto y cronología; el writer escribe tres escenas por capítulo; el editor las une y pule; el juez puntúa con una rúbrica.
- Debajo, los cuatro puntos de validación: al entregar el brief, en cada escena, al cerrar cada capítulo y antes de publicar.
- Todo bucle está acotado: como mucho 2 reescrituras por escena, 2 por capítulo y 2 rondas de reparación de la novela.
- La decisión clave: ningún modelo tiene herramientas. El orquestador, en Python, elige qué ve cada rol, valida su salida con JSON Schema y escribe él en la base de datos: los permisos se aplican en código, no se piden en un prompt.

**Cifras que mencionar:** reintentos 2/2 · 2 rondas de reparación

**Transición:** Todo eso gira en torno a una memoria: la story bible.

## 5. Memoria: la story bible · ≈ 35 s

**Mensaje clave.** Una sola fuente de verdad en SQLite que usan validadores, lector y Lean.

**Qué decir:**

- La story bible es una SQLite autoritativa: si algo no está ahí, no es verdad para el sistema.
- Cada hecho del brief es una fila, y fact_usage registra en qué capítulo y escena se usa. Eso es lo que permite regenerar solo los capítulos afectados.
- La cronología guarda eventos con fecha, lugar y participantes, y es exactamente lo que se exporta a Lean.
- Texto del capítulo y checkpoint se guardan en la misma transacción: si se cae, se reanuda en el primer capítulo incompleto sin duplicar ni perder nada.

**Cifras que mencionar:** 16 tablas

**Transición:** Sobre esa memoria actúan los validadores.

## 6. Validadores · ≈ 50 s

**Mensaje clave.** Cuatro tipos de validador, cada uno en el punto donde arreglar el fallo es más barato.

**Qué decir:**

- Programáticos: schema, longitud, nombres exactos, cobertura de los datos del brief. El último que añadimos es calendar_consistency: comprueba que un día de la semana junto a una fecha es el correcto. Luego os cuento por qué.
- También hay un linter de prosa, prose_repetition, que detecta repeticiones y clichés de IA; es el opcional X02 y es blando para no provocar bucles.
- Semánticos: el juez por capítulo y por novela, con una rúbrica de continuidad, tono, calidad narrativa, personalización natural y final. Aprueba con cada criterio ≥ 3 y media ≥ 3,5.
- Formales: Lean sobre la cronología de cada novela, y TLA+ sobre el propio harness.
- La regla: si un fallo agota su presupuesto, la versión se bloquea. Nunca se publica algo que no pasó.

**Cifras que mencionar:** 4 tipos · 4 puntos de ejecución · juez: ≥ 3 y media ≥ 3,5

**Transición:** Un tipo especial de validador son los guardrails.

## 7. Guardrails y policy · ≈ 45 s

**Mensaje clave.** Los vetos del cliente y la inyección se paran en código, antes y después del modelo.

**Qué decir:**

- Palabras prohibidas en tres niveles: globales, las del cliente para su novela, y variantes léxicas.
- Un único normalizador quita tildes, mayúsculas, plurales y leetspeak antes de comparar.
- Si aparece un veto, el capítulo vuelve al escritor con un límite de intentos; si se agota, la generación se para y queda registrado.
- El texto libre del cliente se trata como no confiable: un prescan determinista antes del modelo, el extractor solo devuelve hechos, y ningún rol ve el texto crudo.
- Y los hooks de Claude Code usan el mismo código: si yo, o un agente, intento escribir una clave o borrar la base de datos, se bloquea.

**Cifras que mencionar:** 3 niveles de vetos · 14 casos de hooks probados

**Transición:** Para la coherencia temporal usamos verificación formal: Lean.

## 8. Lean 4 · ≈ 60 s

**Mensaje clave.** Lean prueba la coherencia temporal de la cronología; en el caso real cazó lo que el juez de capítulo aprobó.

**Qué decir:**

- De la story bible se genera un fichero Lean y se demuestran cuatro invariantes: orden temporal, edades, nadie en dos sitios, nadie reaparece tras morir o irse.
- Corre antes de publicar; si falla, la versión no se publica y el fallo vuelve al editor. Y el mismo diagnóstico se aplica al plan, antes de escribir una línea.
- El enunciado pide un caso real. Lo forzamos con el brief de trampas temporales, quitando el prechequeo: la mascota muere en 2005 y lleva los anillos en la boda de 2008.
- Lean lo vio, con evento, fecha y capítulo. El juez de novela también. Pero el juez de capítulo aprobó el capítulo que cuenta la muerte y la boda, y los validadores programáticos no miran fechas.
- Lo digo con honestidad: no es algo que solo viera Lean. Su valor es que es determinista, localiza el evento y actúa antes de gastar la escritura.

**Cifras que mencionar:** 2 validadores lo vieron · ~0,12 USD en el plan frente a ~1,3 USD de novela

**Transición:** Lean verifica la historia; TLA+ verifica el harness.

## 9. TLA+ · ≈ 45 s

**Mensaje clave.** El harness es una máquina de estados y TLC comprueba que nunca publica nada sin validar y que siempre termina.

**Qué decir:**

- Modelamos el flujo completo como máquina de estados: configuración, plan, escenas, editor, cierre de capítulo, checkpoint, pre-publicación y publicación; con reintentos, crash y reanudación, y cambio del lector.
- Cuatro invariantes de seguridad: nunca se publica sin validar, reanudar no duplica ni pierde capítulos, la versión anterior se conserva, y los reintentos están acotados incluso tras un crash.
- Y liveness: toda generación acaba publicando o en error, nunca en un bucle.
- TLC explora el modelo pequeño que pide el enunciado, 5 capítulos con 2 reintentos: 5.492.531 estados distintos, sin errores.
- Al subir las rondas de reparación de 1 a 2, lo primero fue volver a pasar TLC.

**Cifras que mencionar:** 5.492.531 estados distintos · 10.031.846 generados · profundidad 127 · 08min 17s

**Transición:** Lo más valioso de TLA+ no fue este verde, fueron los rojos de antes.

## 10. Contraejemplos CE1–CE4 · ≈ 45 s

**Mensaje clave.** TLC encontró cuatro errores de diseño cuando aún eran baratos: antes de escribir el pipeline.

**Qué decir:**

- Escribimos el modelo en paralelo al diseño, leyendo el esquema tal cual. TLC encontró cuatro trazas mínimas que lo rompían.
- CE1: si el proceso cae entre guardar el capítulo y guardar el checkpoint, al reanudar se escribe dos veces. Solución: las dos cosas en una transacción.
- CE2 y CE4: los contadores de reintentos y de rondas de reparación vivían en memoria; un crash los ponía a cero y el coste dejaba de estar acotado. Solución: se leen de la base de datos.
- CE3: la reparación insertaba una segunda fila del mismo capítulo. Solución: upsert por versión y capítulo, y una versión publicada no se toca. El pipeline nació ya con esas cuatro reglas.

**Cifras que mencionar:** 4 contraejemplos · trazas de 18 a 50 estados

**Transición:** Todo esto se puede ver en ejecución gracias a la observabilidad.

## 11. Observabilidad con Langfuse · ≈ 35 s

**Mensaje clave.** Cada novela es una sesión con coste, validadores y versión de prompt por llamada.

**Qué decir:**

- Una sesión por novela, que incluye la entrevista y las regeneraciones; una traza por generación o cambio.
- Spans con nombre por fase, capítulo, rol y tool; tokens, coste y latencia por llamada, por capítulo y por novela.
- Todos los validadores, incluidos Lean y el juez, llegan como scores.
- Y los prompts están versionados en Langfuse: la tabla de la derecha sale de las evals y dice qué versión produjo cada resultado. Es lo que hace creíble el antes/después del tuning.

**Transición:** Y eso nos lleva a las evals.

## 12. Evals y tuning 1 · ≈ 50 s

**Mensaje clave.** Una iteración de tuning medida: de 0 a 2 novelas publicadas sin bajar ningún umbral.

**Qué decir:**

- Cinco briefs: ejemplo, infantil, inyección, trampas temporales y contradictorio.
- Antes del tuning se publicaban 0 de 3. El problema no eran las novelas: brief_coverage exigía la frase literal del recuerdo aunque el capítulo lo contara, y el espejo Python de noAfterExit daba un falso positivo.
- Arreglamos los validadores, añadimos marcas temporales al plan, hicimos que el juez solo bloquee por defectos graves y concretos, y que la reparación toque solo los capítulos que el juez pide.
- Después: 2 de 3 publicadas. Los umbrales de calidad no se bajaron.
- El brief de trampas temporales sigue bloqueado, y es lo correcto: su trampa de edad no tiene ninguna lectura coherente. El contradictorio se rechaza antes de generar.

**Cifras que mencionar:** 0/3 → 2/3 publicadas · coste medio publicada ≈ 0,99 USD

**Transición:** Antes de los resultados finales, un punto de seguridad.

## 13. Seguridad y opcionales · ≈ 40 s

**Mensaje clave.** Revisión de seguridad hecha por un agente: 15 hallazgos, ninguno crítico ni alto, y los medios corregidos con test.

**Qué decir:**

- Además del red-team, hicimos el opcional X04: un agente revisó el sistema. 15 hallazgos, 0 críticos o altos; los 5 medios están corregidos, cada uno con un test que falla sin el cambio.
- Ejemplo: el prescan de inyección solo detectaba 10 de 17 variantes; ahora 17 de 17.
- El hallazgo más serio era que no había autenticación. Lo cerró el login, X03: bcrypt, JWT, y un usuario no puede ver las novelas de otro.
- X01 es un servidor MCP de solo lectura para consultar y descargar novelas, que respeta la identidad. X02 es el linter de prosa.

**Cifras que mencionar:** 15 hallazgos · 0 críticos/altos · 6 corregidos · inyección 17/17

**Transición:** Ahora, los resultados con novelas de verdad de 10 capítulos.

## 14. Novelas de 10 capítulos y tuning 2 · ≈ 95 s

**Mensaje clave.** Las dos primeras novelas completas se bloquearon, y eso es el sistema funcionando: nada sin validar llega al cliente.

**Qué decir:**

- Esta es para mí la diapositiva más importante.
- Primer intento: diez capítulos escritos y el juez de novela la suspendió por saltos temporales y dos capítulos solapados. Coste 3,68 USD. No se publicó. Eso motivó el tuning 1.
- Segundo intento, tras el tuning 1: tras 2 rondas de reparación, bloqueada otra vez: el 24 de junio aparecía como lunes cuando es miércoles, y en cada ronda los días de la semana cambiaban. Coste 4,61 USD. Tampoco se publicó.
- La causa: nadie calculaba el calendario. El modelo inventaba el día de la semana, y cada reparación inventaba otro, así que no convergía. El error ya estaba en el plan.
- Tuning 2: el calendario lo calcula Python, no el LLM. El plan se corrige, el writer recibe las fechas reales, y un validador determinista para el error en el capítulo, sin gastar una ronda del juez.
- El intento final, ya con el tuning 2, se publicó: 10 capítulos, 10.645 palabras, 0 rondas de reparación, 3,10 USD.
- Y una ejecución paralela con el mismo código, novela-ejemplo-b, se paró: el juez de novela la aprobaba, pero un evento del plan no tenía lugar y la exportación a Lean falló; las 2 rondas reescribieron prosa que no podía arreglarlo. Coste 6,05 USD. Ahora el chequeo del plan rechaza ese evento y un error de exportación para la ejecución sin gastar rondas.

**Cifras que mencionar:** intentos parados: 3,68 USD, 4,61 USD, 6,05 USD · total gastado sin publicar: 14,34 USD

**Transición:** Veamos la novela que sí se entrega.

## 15. Novela de ejemplo · ≈ 25 s

**Mensaje clave.** El sistema funciona de principio a fin: brief → novela publicada → PDF.

**Qué decir:**

- Esta es la novela de ejemplo: 10 capítulos, 10.645 palabras, generada con el brief del README.
- Portada con dedicatoria, índice navegable y fichas, igual que en la web.
- Costó 3,10 USD y tardó 69 min, con 0 rondas de reparación.
- Pasó todos los validadores: nombres, cobertura, calendario, Lean y el juez de novela.

**Cifras que mencionar:** 10 capítulos · 10.645 palabras · 3,10 USD · 69 min

**Transición:** ¿Y cuánto cuesta esto como negocio?

## 16. Coste y latencia · ≈ 35 s

**Mensaje clave.** Una novela de 10 capítulos cuesta unos pocos dólares de modelo y se genera en menos de dos horas.

**Qué decir:**

- Un capítulo cuesta de media 0,35 USD y unos 8 min de modelo, contando escenas, editor, juez y reparaciones.
- La novela de 10 capítulos publicada costó 3,10 USD.
- El writer es el rol más caro, seguido del editor y el juez: tiene sentido, son los que producen y leen más texto.
- Comercialmente, el coste de modelo es pequeño frente al precio de un regalo personalizado; lo que cuesta de verdad es el tiempo, y por eso los bucles están acotados: una novela nunca se queda gastando indefinidamente.

**Cifras que mencionar:** 0,35 USD/capítulo · 8 min/capítulo · 3,10 USD

**Transición:** Cómo se construyó todo esto: Claude Code.

## 17. Uso de Claude Code · ≈ 40 s

**Mensaje clave.** Claude Code fue el equipo: un orquestador, subagentes en paralelo y reglas que hacían cumplir el proceso.

**Qué decir:**

- CLAUDE.md y AGENTS.md definen el proceso: primero docs, luego spec, luego plan y código, y antes de editar, una ronda de preguntas con recomendación.
- Un orquestador repartió el trabajo en bloques; cada subagente trabajaba en su propio worktree, en paralelo, y los contratos entre bloques se publicaban primero.
- Skills propias: gift-novel-run para generar e inspeccionar una novela, y security-review-harness para repetir la revisión de seguridad. Comandos como /generate-novel o /change-fact.
- Y el browser MCP no fue decorativo: encontró un error 500 intermitente por una conexión SQLite compartida entre hilos, que corregimos.

**Cifras que mencionar:** 14 casos de hooks · 1 worktree por agente

**Transición:** Toda esta construcción se apoya en decisiones que tomamos conscientemente.

## 18. Decisiones y trade-offs · ≈ 40 s

**Mensaje clave.** Cada decisión tiene alternativa, criterio y coste; la más importante es separar la verdad de la prosa.

**Qué decir:**

- Multi-agente frente a un agente con herramientas: elegimos roles orquestados por código porque los permisos se aplican en código y cada paso se valida y reintenta por separado. El precio: más llamadas.
- SQLite con hechos estructurados frente a RAG vectorial: aquí necesitamos hechos exactos y saber en qué capítulo se usa cada uno, no fragmentos parecidos.
- Calendario en Python en vez de confiar en el juez: lo aprendimos por las malas con la segunda novela bloqueada.
- Y el juez es bloqueante: por D11, la calidad narrativa también puede impedir la publicación.

**Transición:** Ninguna de estas decisiones es gratis; estas son las limitaciones.

## 19. Limitaciones y siguientes pasos · ≈ 40 s

**Mensaje clave.** Sabemos exactamente qué no está demostrado todavía, y está escrito.

**Qué decir:**

- Prefiero decirlo yo antes de que me lo preguntéis.
- Las fichas de personajes no están versionadas en la base de datos: si cambia la descripción de un personaje, la versión antigua de la ficha no la conserva; el nombre sí.
- El validador de calendario solo mira días de la semana junto a una fecha; «aquel lunes» o «treinta años» dependen del prompt.
- Lean solo prueba lo que el planner mete en la cronología: si alguien emigra y el plan no crea el evento de partida, nadie lo detecta.
- Y queda una decisión abierta sobre una regla heredada de accesos a ficheros.

**Transición:** Para cerrar, la decisión que lo resume todo.

## 20. Cierre · ≈ 35 s

**Mensaje clave.** Separar la verdad de la prosa, y publicar solo lo que pasa todos los validadores.

**Qué decir:**

- Si tuviera que quedarme con una decisión: separar la verdad de la prosa.
- Lo que es cierto sobre la historia vive en una base de datos, y lo comprueban validadores deterministas, Lean y TLA+. Los modelos solo redactan.
- El bucle está acotado y solo publica lo que pasa todo. Las dos novelas bloqueadas que os he enseñado son la prueba de que eso se cumple.
- En los anexos está el detalle de TLA+, Lean, evals y arquitectura. Muchas gracias; encantado de responder preguntas.

**Transición:** Preguntas.

---

## Preguntas probables del tribunal

**1. ¿Por qué multi-agente y no un solo agente con herramientas?**

Porque quería que los permisos se cumplieran en código. Ningún modelo tiene herramientas: el orquestador decide qué ve cada rol, valida su salida con schema y escribe él en la base de datos. Así cada paso se valida y se reintenta por separado, hay trazas por rol y cada fallo vuelve al rol que puede arreglarlo. El coste es más llamadas y más código de orquestación; un agente único sería más simple, pero no podría demostrar quién escribió qué.

**2. ¿Por qué SQLite y no RAG vectorial?**

Porque lo que necesita el pipeline son hechos exactos, no fragmentos parecidos: el nombre del perro, la fecha de la boda, y en qué capítulo se usa cada hecho (fact_usage), que es lo que permite regenerar solo lo afectado y exportar la cronología a Lean. Los roles reciben hechos estructurados a través de tools validadas con schema (app/tools/). El índice heredado del harness genérico sí tiene FTS5 y sqlite-vec, pero el pipeline de novelas-regalo no lo usa: una búsqueda por similitud podría devolver un hecho parecido pero falso.

**3. ¿Qué detecta Lean que no detecte el juez?**

Caso L04, con el brief de trampas temporales y sin el prechequeo: la mascota muere en 2005 y lleva los anillos en la boda de 2008. Lean lo detectó con evento, fecha y capítulo. judge_novel también, pero judge_chapter aprobó el capítulo que cuenta la muerte y la boda, y ningún validador programático mira fechas. La diferencia: Lean es determinista, localiza el evento exacto y actúa sobre el plan, antes de escribir (~0,12 USD frente a ~1,3 USD de novela). Limitación: solo prueba lo que el planner pone en la cronología.

**4. ¿Qué contraejemplos encontró TLC y qué cambiaron en el código?**

Cuatro, antes de que existiera el pipeline. CE1: un crash entre guardar el capítulo y el checkpoint duplicaba el capítulo → texto y checkpoint en una transacción. CE2: el contador de reintentos de capítulo vivía en memoria → se cuenta desde validator_result. CE3: la reparación insertaba una segunda fila → upsert por (versión, capítulo) y la versión publicada no se escribe. CE4: el contador de rondas de reparación en memoria → columna repair_rounds guardada junto a «blocked». El modelo actual pasa: 5.492.531 estados distintos, sin errores.

**5. ¿Cómo evitas que la personalización estropee la narrativa?**

Es la decisión D11: las dos pesan igual. brief_coverage comprueba que cada dato obligatorio aparece, pero el juez puntúa continuidad, tono, calidad narrativa, personalización natural (penaliza la personalización forzada) y final, y aprueba solo con cada criterio ≥ 3 y media ≥ 3,5. Un capítulo con todos los datos pero mal escrito no pasa. El linter de prosa añade repeticiones y clichés.

**6. ¿Cómo tratas la inyección en el texto libre?**

Como contenido no confiable. Un prescan determinista antes del modelo (tras la revisión de seguridad detecta 17 de 17 variantes), el extractor solo devuelve hechos y marca la sospecha, ningún rol recibe el texto crudo, y ningún modelo tiene herramientas para hacer daño. Las peticiones de cambio del lector también se escanean. Riesgo aceptado: un hecho extraído llega a los prompts, delimitado como dato.

**7. ¿Qué pasa si el juez suspende?**

En un capítulo, el editor lo reescribe con la evidencia, como mucho 2 veces. En la novela, hay hasta 2 rondas de reparación solo de los capítulos que el juez señala. Si se agota, la versión queda «blocked» y nunca se publica: es el invariante NoUnvalidatedPublish de TLA+. Las dos novelas de 10 capítulos bloqueadas son exactamente eso.

**8. ¿Cuánto cuesta y cuánto tarda una novela?**

La novela de 10 capítulos publicada costó 3,10 USD y tardó 69 min, con 0 rondas de reparación. Un capítulo cuesta de media 0,35 USD y unos 8 min de modelo; la novela de 3 capítulos publicada costó 0,85 USD en 21 min.

**9. ¿Por qué Haiku?**

Por coste y latencia: una novela son unas 70–80 llamadas. La calidad la vigila el juez con umbrales bloqueantes. Subir un rol concreto a Sonnet es una variable de entorno (MODEL_<ROL>) y se registraría en el log de iteraciones; no hizo falta: los fallos que vimos eran de diseño (calendario, validadores), no del modelo.

**10. ¿Cómo funciona el cambio del lector y qué se conserva?**

El lector pide «el perro se llama Nala». El hecho es una fila única; fact_usage dice qué capítulos lo usan y, si es un nombre, se busca el antiguo en hechos, brief, plan y texto. Solo esos capítulos se regeneran a una versión v+1, todo en una transacción. La versión anterior se conserva intacta (PreviousVersionKept), el índice marca los capítulos modificados y el PDF lleva una página de novedades.

**11. ¿Cuáles son las limitaciones reales?**

Las fichas de personajes no están versionadas en la BD (solo el nombre); los días de la semana sin fecha al lado y las duraciones no se validan; Lean solo ve lo que el planner registra; y hay una regla heredada de accesos a ficheros pendiente de decisión (el test de fronteras).

**12. ¿Qué harías con más tiempo?**

Versionar el reparto, validar días y duraciones en toda la prosa, exigir eventos de partida cuando el brief dice que alguien se fue, hacer la revisión humana y calibrar el juez, paralelizar capítulos para bajar la latencia y añadir tools de escritura al servidor MCP con confirmación.

**13. ¿Cómo usaste Claude Code?**

Como un equipo: una sesión orquestadora escribió la spec del programa y lanzó subagentes en paralelo, uno por bloque y cada uno en su git worktree, con contratos publicados antes. CLAUDE.md y AGENTS.md fijan el proceso docs → spec → plan → código. Hooks de validación y de policy, skills propias (gift-novel-run, security-review-harness), comandos / y el browser MCP, que encontró un 500 intermitente de SQLite entre hilos.

**14. ¿Por qué se bloquearon las novelas de 10 capítulos? ¿No es un fracaso?**

Es el sistema funcionando. La primera, por saltos temporales y capítulos solapados; la segunda, por días de la semana que contradecían su fecha, que el modelo reinventaba en cada reparación. Ninguna llegó al cliente. Cada bloqueo produjo una iteración de tuning con causa y efecto registrados; la segunda movió el calendario a Python y a un validador determinista.

---

## Frase para el email (≤ 3 líneas)

> Separé la verdad de la prosa: una story bible SQLite con validadores deterministas, Lean y TLA+ decide qué es cierto, y un bucle acotado planner → writer → editor → juez solo publica versiones que lo pasan todo; si no, bloquea, nunca entrega.
