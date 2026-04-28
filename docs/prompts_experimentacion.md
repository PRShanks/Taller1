# Documentación del proceso de Prompt Engineering

> Taller 1 — Aplicación de Técnicas Avanzadas de IA Generativa
> Empresa analizada: **Hoteles Estelar S.A.**

Este documento describe el proceso de diseño, prueba e iteración de los prompts
utilizados para las tres tareas del taller (Resumen, FAQ, Q&A). Sigue las
buenas prácticas recomendadas en la documentación oficial de Anthropic y
LangChain.

---

## 1. Principios de diseño aplicados

A todos los prompts se les aplicaron los siguientes principios:

| Principio | Cómo se implementó |
|---|---|
| **Asignación de rol** | Cada prompt comienza con `Eres un analista financiero senior...` para condicionar el estilo de respuesta. |
| **Instrucciones explícitas** | Se enumeran las reglas en bloques `REGLAS ESTRICTAS:` con bullets. |
| **Anti-alucinación** | Cláusula obligatoria: *"Basa tu respuesta ÚNICAMENTE en el contexto provisto"*. |
| **Formato de salida** | Se especifica la estructura de la respuesta (ej: secciones numeradas, formato Markdown). |
| **Idioma fijado** | Se indica `Responde en español` para evitar derivas a inglés. |
| **Delimitadores claros** | El contexto se envuelve entre `=== CONTEXTO ===` y `=== FIN DEL CONTEXTO ===`. |
| **Temperatura adaptada** | Resumen: 0.3 · FAQ: 0.5 · Q&A: 0.0 (máxima fidelidad). |

---

## 2. Prompt de Resumen — iteraciones

### Versión 1 (descartada)
```
Resume el siguiente reporte financiero: {contexto}
```
**Problema:** El modelo producía un resumen genérico, sin estructura, a veces
en inglés, y omitía cifras clave.

### Versión 2 (descartada)
```
Eres un analista financiero. Resume este reporte en 200 palabras: {contexto}
```
**Problema:** Mejoró el tono pero seguía sin estructura predecible y a veces
inventaba interpretaciones (ej: comparaba con años previos que no estaban
en los datos).

### Versión 3 (final — implementada)
Ver `llm/prompts.py → PROMPT_RESUMEN`.

**Mejoras aplicadas:**
- Rol específico (*analista financiero senior del sector hotelero colombiano*).
- Estructura obligatoria en 4 secciones numeradas.
- Cláusula explícita anti-alucinación.
- Recordatorio de unidades (COP millones).
- Límite de palabras explícito.

---

## 3. Prompt de FAQ — iteraciones

### Versión 1 (descartada)
```
Genera 5 preguntas frecuentes sobre este reporte: {contexto}
```
**Problema:** Las preguntas eran muy parecidas entre sí y a veces sin
respuesta clara en el contexto (ej: *"¿cuál es la estrategia futura de la
empresa?"*).

### Versión 2 (final — implementada)
Ver `llm/prompts.py → PROMPT_FAQ`.

**Mejoras aplicadas:**
- Restricción explícita: *"NO formules preguntas cuya respuesta requiera
  información externa"*.
- Indicación de variar temas (identificación, ingresos, rentabilidad,
  apalancamiento, sector, metodología).
- Formato de salida en Markdown con estructura `**P:** / R:`.
- Número de preguntas parametrizable desde la app.

---

## 4. Prompt de Q&A (RAG) — iteraciones

### Versión 1 (descartada)
```
Responde la pregunta usando este contexto: {contexto}
Pregunta: {pregunta}
```
**Problema:** Cuando la pregunta no tenía respuesta en el contexto, el
modelo improvisaba con conocimiento general (alucinación crítica).

### Versión 2 (descartada)
Se agregó *"Si no sabes, dilo"*.
**Problema:** El modelo a veces devolvía respuestas como *"No sé con certeza,
pero podría ser..."* — seguía abriendo la puerta a inventar.

### Versión 3 (final — implementada)
Ver `llm/prompts.py → PROMPT_QA`.

**Mejoras aplicadas:**
- Frase de fallback **literal y obligatoria**: cuando no hay respuesta,
  el modelo debe decir exactamente *"No tengo esa información en los datos
  disponibles."*
- Reglas numeradas (más fáciles de seguir para el LLM).
- Temperatura = 0.0 para minimizar variabilidad.
- Recordatorio de citar unidades y año en cifras monetarias.
- Límite de extensión (1-4 oraciones) para evitar relleno.

### Validación con pregunta trampa
Se probó la pregunta **"¿Quién es el CEO de la empresa?"** (cuya respuesta
**no está** en el contexto). El comportamiento esperado y obtenido es:

> *"No tengo esa información en los datos disponibles."*

Esto confirma que el guardrail anti-alucinación funciona.

---

## 5. Tabla resumen de configuración final

| Tarea | Modelo | Temperatura | Max tokens | Estrategia |
|---|---|---|---|---|
| Resumen | claude-haiku-4-5 | 0.3 | 1024 | Contexto completo |
| FAQ | claude-haiku-4-5 | 0.5 | 2048 | Contexto completo |
| Q&A | claude-haiku-4-5 | 0.0 | 512 | RAG (top-4 chunks) |

---

## 6. Lecciones aprendidas

1. **Especificar el formato de salida** reduce drásticamente la
   variabilidad y facilita el parsing posterior.
2. **Las cláusulas de fallback literal** (frase exacta a usar cuando no
   se sabe) son más efectivas que decir *"no inventes"*.
3. **Asignar un rol específico** mejora notablemente el vocabulario
   técnico del modelo.
4. **Temperatura 0** es la opción correcta para Q&A factual; mantenerla
   más alta solo tiene sentido cuando se busca creatividad (ej: variar
   las preguntas en el FAQ).
5. **Chunking pequeño con overlap** (400/80) funciona bien con
   contexto financiero estructurado, donde cada cifra debe aparecer
   con su etiqueta cercana.
