# Guion — presentación 2 (10 minutos + 5 de preguntas)

Deck: `presentacion-2.pptx` / `presentacion-2.pdf` (15 diapositivas).
Tiempos entre corchetes. Frases en cursiva = lo que dices casi literal; el resto, ideas.

---

## 1 · Portada [0:00–0:30]
*«Buenos días. Soy [tu nombre], de Qaracter, y presento a Cuentalia Regalos nuestra propuesta:
My Story Marker, un servicio que escribe novelas personalizadas para regalar.»*
- Ocasión: su catálogo de Navidad 2026.
- Idea fuerza: *«Lo difícil no es escribir diez capítulos con IA; es poder demostrar que lo que
  entregamos es coherente, está personalizado y no contiene nada vetado.»*

## 2 · Problema y cliente [0:30–1:30]
- Quién compra: hijos y nietos (jubilaciones, 70 cumpleaños), parejas (aniversarios, bodas),
  padres y padrinos (un cuento en el que el niño es el protagonista).
- Por qué no sirven las alternativas: un escritor por encargo tarda semanas y cuesta como
  artesanía; las plantillas «pon tu nombre aquí» no emocionan; un chatbot genérico se contradice
  y no garantiza nada.
- *«Nuestro cliente necesita las dos cosas a la vez: que el destinatario se reconozca y que la
  historia se lea sin tropezar. Una sin la otra no se vende.»*

## 3 · Configuración y lectura [1:30–2:30]
- **Configurar:** asistente de 5 pasos (destinatario, personas, recuerdos, historia con género,
  tono y vetos, dedicatoria). El brief se valida con JSON Schema y reglas de coherencia —p. ej.
  6 años + romance se bloquea— *antes de gastar un token*. El texto libre se trata como dato.
- **Leer:** lector web con portada y dedicatoria, índice, fichas de personajes y lugares
  enlazadas a los capítulos; PDF con la misma estructura.
- **Corregir:** seleccionas un fragmento y pides «la perra se llama Nala»; solo se regeneran
  los capítulos que usan ese hecho y la versión anterior se conserva. *Lo veremos en la demo.*

## 4 · Arquitectura 1/2 — roles [2:30–3:30]
- *«Cinco roles LLM, cada uno con un solo trabajo, orquestados por código, no por otro LLM.»*
- interviewer → brief; planner → plan de 10 capítulos × 3 escenas, reparto, cronología;
  writer → escenas; editor → une, pule y critica el capítulo; judge → puntúa con rúbrica.
- Todos Claude Haiku 4.5. El orquestador es una máquina de estados con reintentos acotados,
  checkpoint por capítulo y reanudación.
- Por qué multi-agente: cada rol tiene su prompt, su schema de salida y su validador; si algo
  falla sabemos quién y lo reintentamos solo a él.

## 5 · Arquitectura 2/2 — contexto, story bible, tools, hooks [3:30–4:30]
- **Contexto:** ningún rol ve la novela entera ni el texto libre crudo: su trozo del plan, los
  hechos asignados, resúmenes de capítulos previos y las últimas 250 palabras. Muy por debajo de
  los 100k tokens.
- **Story bible en SQLite:** cada hecho es una fila y sabemos en qué capítulo se usa; cronología
  para Lean; versiones que nunca se sobrescriben.
- **Tools** de solo lectura con schema (query_story_bible, get_chapter_summary), trazadas.
- **Hooks de Claude Code:** validación de capítulo y policy, con el mismo código del pipeline.
- *«Permisos en código y no en prompts; hechos exactos en vez de RAG; y lo determinista, como el
  calendario, fuera del modelo.»*

## 6 · Validación 1/4 — cuatro tipos, cuatro puntos [4:30–5:00]
- Programáticos (schema, nombres exactos, longitud, calendario, cobertura del brief, palabras
  prohibidas, visual), semánticos (juez LLM con rúbrica + revisión humana), formal de la historia
  (Lean 4) y formal del sistema (TLA+).
- Puntos: hook del brief, cada escena, cada capítulo, antes de publicar.
- Un fallo vuelve a quien lo produjo con la evidencia. Cada resultado es un score en Langfuse.

## 7 · Validación 2/4 — resultados y tuning [5:00–5:30]
- Cinco briefs: ejemplo, infantil, inyección, trampas temporales, contradictorio.
- *«Antes del tuning se publicaban 0 de 3; después, 2 de 3, sin bajar ningún umbral de
  calidad.»* El de trampas temporales sigue bloqueado — y es lo correcto. El contradictorio se
  rechaza en la entrevista.
- Tuning 2 en la novela de 10 capítulos: los días de la semana no cuadraban con las fechas;
  ahora el calendario lo calcula Python. El siguiente intento se publicó a la primera:
  10.645 palabras, 3,10 USD.

## 8 · Validación 3/4 — Lean y TLC [5:30–6:00]
- **Lean:** de la story bible se genera la cronología y se demuestran 4 invariantes (orden
  temporal, edad coherente, no estar en dos sitios, no aparecer tras morir o irse).
- **Caso real L04:** la mascota muere en 2005 y lleva los anillos en la boda de 2008. Lean lo
  señala con evento y capítulo; el juez de capítulo lo aprobó. *Honestamente, el juez de novela
  también lo vio: el valor de Lean es que es determinista y actúa sobre el plan, antes de escribir.*
- **TLA+/TLC:** el harness como máquina de estados; 5 capítulos, 2 reintentos, crash y cambio del
  lector: 5,5 millones de estados sin errores. Durante el desarrollo TLC encontró 4
  contraejemplos reales que cambiaron el código.

## 9 · Validación 4/4 — Langfuse [6:00–6:30]
- *«Esto es una traza real.»* Una sesión por novela, una traza por generación, spans por fase,
  capítulo, rol, tool y validador, con tokens, coste y latencia: 9 min 42 s y 0,43 USD para un
  capítulo.
- A la derecha, el brief con inyección: marcada dos veces (prescan y modelo) y aun así todos los
  validadores en verde: *no se siguió.*
- Prompts versionados: sabemos qué versión produjo cada resultado del antes/después.

## 10 · Guardrails [6:30–7:00]
- Palabras prohibidas en 3 niveles (global, por novela, léxico), normalizando mayúsculas,
  acentos, plurales y variantes. Ejemplo real: una escena con «idiota» → rechazada → vuelve al
  writer con el término → reescrita sin él. Límite de 2; si se agota, se para y se informa.
- Datos personales solo en la base de datos; inyección: prescan determinista y el texto libre
  nunca llega crudo a un rol. Todo en el audit log (`policy_decision`).

## 11 · Presupuesto y coste 1/2 [7:00–7:30]
- *«Coste medido en Langfuse: la novela de 10 capítulos publicada costó 3,10 USD de modelo y 69
  minutos; un cambio del lector, 0,94 USD.»* Entre 0,20 y 0,49 USD por capítulo.
- El writer es el rol más caro; luego editor y juez: son los que producen y leen más texto.
- Gasto real de todo el desarrollo con modelo: 27 USD, la mitad en intentos bloqueados — que no
  se cobran: solo se factura lo publicado.
- Propuesta: piloto de 8 semanas por 28.800 €, 600 €/mes de plataforma y 12 € por novela
  publicada. Con un PVP de 39 €, a Cuentalia le quedan 27 € de margen bruto.

## 12 · Presupuesto y coste 2/2 [7:30–8:00]
- **Coste unitario:** 3,10 USD de tokens medidos en Langfuse (2,79 €) + 30 % de contingencia por
  reintentos + el cambio incluido (0,85 €) + infraestructura (0,30 € a 500 novelas/mes) ≈ **4,77 €**.
  Cobramos 12 € → **margen operativo ≈ 7,23 € (60 %)**.
- **Proyecto:** 360 h a 80 €/h = **28.800 €** (diseño 60, desarrollo 180, validación 90,
  despliegue 30) — exactamente el piloto.
- **Volumen:** a 100 / 500 / 2.000 novelas al mes, Cuentalia gana 2.100 / 12.900 / 53.400 € y
  Qaracter 1.203 / 4.214 / 15.504 €.
- **Sensibilidad:** tokens +50 % → nuestro margen baja a ~5 €, sigue positivo. Más de 3
  revisiones: si se cobran a 2 € el margen sube; si fueran gratis, con 6 y tokens +50 % perdemos
  1,35 € por novela. *Por eso los cambios adicionales se cobran y recomendamos 3 incluidas.*

## 13 · Demo [8:00–9:00]
- *«La perra se llama Nala.»* La petición entra por el lector; `fact_usage` dice qué capítulos
  usan el hecho (1 y 3–10); se regeneran solo esos en una versión 2; el 2 se copia.
- Mismos validadores, versión 2 publicada, versión 1 intacta: «Canela» 44 → 0, «Nala» 0 → 45.
  Unos 27 minutos y 0,94 USD. El PDF nuevo trae la página de «Novedades».

## 14 · Riesgos y siguientes pasos [9:00–9:40]
- Lo que aún no está demostrado: días sin fecha al lado y duraciones en la prosa; Lean solo
  prueba lo que el planner registra; revisión humana a escala.
- Siguientes pasos: extender el calendario a la prosa, más invariantes, el piloto con 50 novelas
  y QA editorial.

## 15 · Cierre [9:40–10:00]
*«Separamos la verdad de la prosa: lo que es cierto sobre la historia vive en una base de datos y
lo comprueban validadores, Lean y TLA+. Solo se publica lo que pasa todo. Gracias.»*

