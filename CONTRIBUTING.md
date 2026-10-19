# Cómo contribuir

Gracias por querer mejorar estas skills. Las contribuciones más útiles son reportes de errores con datos reproducibles, casos donde el semáforo dio un color equivocado y mejoras a la claridad de las guías.

## Antes de abrir un issue

1. Revisa si ya existe uno parecido.
2. Corre las pruebas para confirmar que el error no viene de tu instalación:
   ```bash
   cd skills/analitica-marketing-mentinno-coach
   pip install -r requirements.txt
   python3 tests/check_ab.py
   ```
3. Si el error aparece con tus datos, prepara un archivo de ejemplo sin información personal o genera uno simulado que muestre el mismo problema.

## Cómo reportar un error

Usa la plantilla "Reportar un error". Incluye el comando exacto, el mensaje que obtuviste, la versión de Python y de las librerías, y una muestra de datos anonimizada.

## Cómo proponer un cambio

1. Abre un issue que describa el cambio antes de escribir código.
2. Haz un fork y crea una rama con nombre descriptivo.
3. Todo cambio en un script debe acompañarse de una prueba en `tests/` que use datos simulados con respuesta conocida. Un cálculo sin prueba contra la verdad no se acepta.
4. Corre todas las pruebas antes de abrir el pull request.
5. Actualiza `CHANGELOG.md`.

## Estilo

- Español con tildes y signos de apertura (¿ ¡).
- Títulos con mayúscula solo en la primera palabra y nombres propios.
- Sin emojis y sin guiones largos.
- Lenguaje de negocio en los textos que lee el usuario final; la jerga técnica va en las guías de referencia.

## Conducta

Se espera trato respetuoso y centrado en las ideas. Los comentarios que ataquen a personas se eliminan.
