# SES Mount Mode (Modo de Montaje)

> **Definición de contrato y especificación técnica para la indexación y sincronización incremental no intrusiva de repositorios documentales masivos.**

---

## 📖 1. Definición del Concepto

El **Mount Mode (Modo de Montaje)** es el pilar operativo de **SES**. Consiste en instalar el motor semántico directamente sobre un universo documental preexistente (discos locales, NAS, SAN o carpetas compartidas de red) y construir una **capa semántica derivada** sin alterar las fuentes de información originales ni convertirse en el repositorio principal de archivos.

El archivo original **permanece intacto y en modo de solo lectura** en su infraestructura de almacenamiento corporativa. SES únicamente extrae el contenido textual y genera el índice semántico necesario para encontrarlo, correlacionarlo y responder preguntas complejas sobre él.

---

## 🎯 2. Regla de Oro del Producto

> [!IMPORTANT]
> **SES nunca debe requerir que el usuario ordene, copie o suba manualmente un repositorio completo.**
> El motor asume la responsabilidad de procesar de forma autónoma el almacenamiento corporativo (incluso volúmenes de 40 a 60 GB) con el siguiente flujo no intrusivo:

```text
Disco original (Solo lectura) ➔ Inventario recursivo ➔ Extracción de texto ➔ Segmentación (Chunking) ➔ Embeddings ➔ Qdrant
                                                                                                                │
                                                                       Consultas RAG ➔ Referencia foliada al original
```

---

## ⚡ 3. Responsabilidades del Filesystem Connector

Un conector de archivos corporativo de nivel producción debe cumplir estrictamente con las siguientes especificaciones:

* **Lectura No Invasiva**: Operar estrictamente bajo permisos de solo lectura sobre las carpetas montadas.
* **Descubrimiento Inteligente**: Rastrear de forma recursiva toda la estructura de directorios y subdirectorios.
* **Filtro de Extensiones**: Discriminar y procesar solo formatos de archivo compatibles (PDF, DOCX, CSV, XLSX, TXT, MD, etc.).
* **Trazabilidad Completa (`source_path`)**: Registrar la ruta física absoluta de cada documento para permitir su recuperación o apertura física instantánea por parte del usuario.
* **Registro de Metadatos Clave**: Almacenar en la cabecera del documento metadatos críticos como el `filename`, la extensión, el tamaño en bytes y la fecha de última modificación.
* **Sincronización Incremental (Detección de Cambios)**: Calcular firmas de versión o hashes criptográficos de cada archivo para evitar la reindexación de documentos que no hayan sufrido alteraciones.
* **Tolerancia a Fallos Activa**: Registrar errores de forma granular en caso de archivos corruptos o ilegibles sin interrumpir ni colapsar el proceso global de indexación.
* **Checkpoints de Progreso**: Persistir puntos de control para permitir que indexaciones interrumpidas (por caída de red, energía o reinicios) puedan reanudarse desde el último archivo procesado.

---

## 🗄️ 4. Responsabilidades del Índice Vectorial

La base de datos vectorial (**Qdrant**) almacena las representaciones matemáticas de los chunks derivadas del procesamiento:

* **Vector del Chunk**: Embedding numérico del fragmento de texto (dimensión `384` usando `all-MiniLM-L6-v2`).
* **Snippet de Texto Trazable**: Fragmento plano de texto para su recuperación inmediata (eliminando la necesidad de volver a leer el archivo original durante la búsqueda).
* **Identificador Único (`original_id`)**: Llave relacional asociada al documento original.
* **Metadata de Auditoría**: Ubicación exacta dentro del documento original (número de página, sección, foliado de renglón y metadatos complementarios).

> [!WARNING]
> **Qdrant no es un file server.** El índice vectorial nunca debe tratarse como el espacio donde vive la copia del archivo original; solo almacena índices derivados optimizados para búsqueda de alta velocidad.

---

## 📈 5. Estrategia de Prueba con Disco Real (40 a 60 GB)

Para garantizar la estabilidad operativa del motor y la eficiencia del consumo de memoria de la aceleración en Rust (`jas_vector_core`), se establece una indexación progresiva por etapas:

| Etapa | Descripción del Volumen | Métricas a Evaluar |
| :---: | :--- | :--- |
| **Etapa 0** | Inventario recursivo sin indexar (Mapeo de estructura). | Cantidad total de archivos y distribución por tipos de extensión. |
| **Etapa 1** | Muestra de prueba inicial pequeña (500 MB a 1 GB). | Tasa de archivos fallidos y rendimiento base de extracción. |
| **Etapa 2** | Muestra de escala media (5 GB). | Tiempo acumulado de generación de embeddings e incremento en Qdrant. |
| **Etapa 3** | Dataset de escala empresarial (10 GB). | Latencia de búsqueda semántica y consumo de memoria del Core en Rust. |
| **Etapa 4** | Volumen corporativo completo (40 a 60 GB). | Throughput de indexación global y estabilidad de hilos de ejecución. |

---

## 🧪 6. Protocolo de Validación Semántica

La validación del sistema va más allá de asegurar que la API retorne resultados técnicos. El sistema se somete a un riguroso protocolo de preguntas reales:

* **Búsquedas de Entidades Nominadas**: Consultar nombres específicos de personas, empresas o números de contratos.
* **Búsquedas Conceptuales**: Interrogar sobre un tema utilizando terminología y sinónimos completamente distintos a los escritos en el documento original.
* **Respuestas de Síntesis Cruzada (Multi-Documento)**: Formular preguntas cuya respuesta requiera consolidar fragmentos de información distribuidos en archivos independientes.
* **Prueba de Respuestas Vacías (Veracidad/Anti-Alucinación)**: Preguntas capciosas o sobre temas inexistentes para auditar que el motor retorne con precisión un "no encontrado" en lugar de alucinar.
* **Validación de Citas Físicas**: Corroborar que el enlace y la ruta retornada (`source_path`) abran exactamente el archivo correcto en el renglón citado.

---

## 🚀 Estado de Implementación en la Rama Main

La arquitectura base del **Mount Mode** está completamente consolidada en la rama estable:
* **Escaneo y Monitoreo Activo**: El watcher en segundo plano (`WATCH_DIRECTORIES`) monitorea de forma incremental carpetas físicas locales usando `watchdog` y realiza encolamiento con debounce asíncrono.
* **Extracción Multi-Formato**: Soporte maduro para PDF, DOCX, CSV y TXT estructurado.
* **Indexación y RAG Trazable**: Endpoints listos para ingestión programática, búsqueda conceptual, síntesis de respuestas con atribución detallada de fuentes corporativas y exportación de reportes PDF homologados.
