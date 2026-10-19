# Historial de cambios

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el versionado sigue [Semantic Versioning](https://semver.org/lang/es/).

## [1.0.0] - 2026-10-19

### Agregado
- Skill `analitica-marketing-mentinno-coach` con 14 módulos.
- Módulos nuevos: pruebas A/B e incrementalidad (11), uplift y diferencias en diferencias (12), valor de vida del cliente (13) y atribución multitoque (14).
- Calibración de la mezcla de medios con resultados de experimentos (`--calibrar`).
- Semáforo de confianza con motivo en frase de negocio en todos los módulos.
- Revisión amigable de dependencias antes de ejecutar cualquier script.
- Bases de práctica para los módulos 11 a 14 en `demo_data.py`.
- Pruebas contra respuesta conocida para cada módulo y compuerta de regresión para la mezcla de medios.

### Corregido
- Efecto con el signo invertido en la salida del módulo de uplift (tabla por deciles y efecto promedio).
- Rangos de incertidumbre de la mezcla de medios que cubrían la verdad en 53% de los casos; ahora cubren 84%.
- Semáforo verde en un clasificador con AUC de 0,75 cuando había dinero en juego; criterios más estrictos.
- Error de ejecución del clasificador con variables solo numéricas.
- Descripción del skill por encima del límite de 1.024 caracteres.
- `demo_data.py --help` creaba una carpeta con nombre `--help`.
