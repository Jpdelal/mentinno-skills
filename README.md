# Mentinno skills

Skills de Claude y guías prácticas para analítica, negocios y educación con inteligencia artificial, creadas por Juan Pablo Del Alcázar Ponce (fundador de Mentinno, profesor de MBA en la USFQ).

Cada skill es una carpeta que Claude lee para trabajar con un método definido, con scripts que calculan y pruebas que demuestran que los cálculos son correctos. Están pensadas para alumnos, profesionales y equipos que quieren resultados que se puedan defender en una reunión.

[![Pruebas](https://github.com/jpdelal/mentinno-skills/actions/workflows/pruebas.yml/badge.svg)](https://github.com/jpdelal/mentinno-skills/actions/workflows/pruebas.yml)
[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-blue.svg)](LICENSE)

## Catálogo

| Skill | Para qué sirve | Versión |
|---|---|---|
| [analitica-marketing-mentinno-coach](skills/analitica-marketing-mentinno-coach) | Convierte una base de datos de marketing y una pregunta de negocio en una decisión con semáforo de confianza. 14 módulos: descriptivo, RFM, embudo, regresión, propensión, mezcla de medios, pruebas A/B, uplift, diferencias en diferencias, valor de vida del cliente y atribución. | 1.0.0 |

Las siguientes skills y guías se publican en este mismo repositorio, una carpeta por skill dentro de `skills/` y una guía por archivo dentro de `docs/`.

## Instalación

Elige la vía que usas. Las tres parten del mismo contenido.

### Claude.ai (alumnos y profesionales sin programación)

1. Entra a la sección [Releases](../../releases) y descarga `analitica-marketing-mentinno-coach.zip`.
2. En Claude, abre Configuración, ve a la sección de capacidades y habilidades (Skills) y carga el archivo ZIP.
3. Activa el skill. Para usarlo, adjunta tu archivo de datos (CSV o Excel) y escribe tu pregunta, por ejemplo: "Revisa estas ventas y dime en qué canal conviene invertir más".

Los nombres de los menús cambian con las versiones de Claude. Si no encuentras la opción, consulta la [guía oficial de skills](https://support.claude.com) de Anthropic.

### Claude Code

```bash
/plugin marketplace add jpdelal/mentinno-skills
/plugin install analitica-marketing-mentinno-coach@mentinno-skills
```

Otra opción sin plugin: copia la carpeta `skills/analitica-marketing-mentinno-coach` en `~/.claude/skills/`.

### Solo los scripts, sin Claude

Los scripts funcionan como herramientas de línea de comandos. Requieren Python 3.11 o superior y se probaron en 3.11 y 3.13.

```bash
git clone https://github.com/jpdelal/mentinno-skills.git
cd mentinno-skills/skills/analitica-marketing-mentinno-coach
pip install -r requirements.txt
python3 scripts/demo_data.py datos_demo
python3 scripts/ab_test.py leer datos_demo/ab_prueba.csv --grupo grupo --resultado compro --control control
```

## Qué hace diferente a estas skills

**Dicen cuánta confianza tienen.** Cada análisis termina en un semáforo con su razón en una frase de negocio: verde ("puedes decidir con esto"), amarillo ("decide con cautela") o rojo ("sirve como hipótesis"). Un análisis que no tiene datos suficientes lo dice en lugar de entregar una cifra frágil.

**Se probaron contra respuestas conocidas.** Cada módulo se corre contra datos simulados donde el resultado verdadero se conoce de antemano. Esas pruebas encontraron defectos reales durante el desarrollo, entre ellos un efecto con el signo invertido y rangos de incertidumbre que cubrían la verdad solo la mitad de las veces. Están corregidos, y las pruebas se ejecutan en cada cambio del repositorio.

**Separan correlación de causa.** El skill distingue lo que se asocia con las ventas de lo que las causa, y cuando propone mover presupuesto pide una prueba con grupo de control antes de hacerlo.

**Enseñan mientras trabajan.** Un coach integrado explica el concepto detrás de cada resultado, con los datos de la propia persona, en tres niveles de profundidad.

## Ejemplo

Con la base de práctica incluida (`demo_data.py`), el análisis de una prueba A/B de 40.000 personas devuelve:

> La acción subió la compra 1,04 puntos porcentuales sobre la base. El rango no incluye cero y la prueba está bien armada. Semáforo verde.

El valor real simulado fue 1,00. Más ejemplos con sus comandos están en [examples](examples/README.md).

## Estructura del repositorio

```
mentinno-skills/
  skills/                       una carpeta por skill (SKILL.md, scripts, references, tests)
  docs/                         guías y documentos de apoyo
  examples/                     comandos y resultados de práctica
  .github/workflows/            pruebas automáticas
  .claude-plugin/               catálogo para instalar con Claude Code
```

## Cómo citar

Si usas estas skills en clase, investigación o consultoría, cítalas con el botón "Cite this repository" de GitHub o con el archivo [CITATION.cff](CITATION.cff).

## Contribuir

Los reportes de errores y las sugerencias son bienvenidos. Lee [CONTRIBUTING.md](CONTRIBUTING.md) antes de abrir un issue o un pull request.

## Licencia

Código, documentos y guías bajo licencia [MIT](LICENSE). Puedes usarlos, modificarlos y compartirlos con atribución.

## Autor

Juan Pablo Del Alcázar Ponce. Fundador y CEO de Mentinno (Cumbayá, Quito, Ecuador), profesor de MBA en la Universidad San Francisco de Quito y candidato doctoral en la Universidad de Palermo. ORCID: [0000-0002-5444-1691](https://orcid.org/0000-0002-5444-1691).

---

## English summary

Claude skills and practical guides for marketing analytics and AI in business education, by Juan Pablo Del Alcázar Ponce (Mentinno, USFQ). The flagship skill, `analitica-marketing-mentinno-coach`, turns a marketing dataset and a business question into a decision with a confidence traffic light. It covers 14 modules, including A/B testing, uplift modeling, difference-in-differences, customer lifetime value, media mix modeling and multi-touch attribution. Every module is tested against simulated data with a known ground truth. Content is in Spanish. MIT license.
