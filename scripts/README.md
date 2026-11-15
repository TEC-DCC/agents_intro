# scripts/

```
scripts/
├── win/     8 scripts .ps1   — Windows / PowerShell
├── linux/   8 scripts .sh    — Linux
├── mac/     8 scripts .sh    — macOS
├── verificar_ambiente.py     — los diagnósticos y el detector de IP son
├── smoke_test_tools.py         Python: corren en los tres sistemas sin
└── fijar_ip_aula.py            cambios
```

**Cada carpeta es autocontenida.** Busca la de tu sistema y ahí está todo: no
hay que leer ramas de `if` para saber qué aplica. No sabemos con qué máquinas
van a llegar los asistentes.

Los dos diagnósticos quedaron en la raíz de `scripts/` porque son el mismo
archivo en los tres sistemas. Triplicarlos solo garantizaría que las copias se
desincronicen; en vez de eso, detectan el sistema y te dicen la ruta correcta
cuando sugieren un script.

---

## Antes del taller (una vez, máquina del instructor)

| Qué hace | Script |
|---|---|
| **Correr primero.** ¿El modelo hace tool calling de verdad? | `verificar_ambiente.py` y después `smoke_test_tools.py` |
| Abre el puerto 11434 para el salón | `<sistema>/aula-firewall` |
| Opcional: aísla el volumen de modelos del de itzae | `<sistema>/copiar-volumen-ollama` |

`smoke_test_tools.py` es el riesgo #1 del plan. Las notas del `.env` de itzae
registran que `qwen3.5:9b` dio "8428 caracteres de pensamiento y 0 de
respuesta". Si eso pasa con tools en juego, los pasos 2 al 5 no funcionan
y hay que cambiar de modelo antes de escribir más material.

```
python scripts/smoke_test_tools.py
python scripts/smoke_test_tools.py --modelo qwen3:8b      # plan B
```

## El día del taller

| Qué hace | Dónde corre | Script |
|---|---|---|
| Levanta Ollama y **escribe la IP del aula en el `.env`** | instructor | `<sistema>/aula-up` |
| Baja Ollama | instructor | `<sistema>/aula-down` |
| La línea exacta de `.env` que copia el salón | instructor | `<sistema>/aula-ip` |
| Detecta la IP de LAN y la fija en el `.env` | instructor | `fijar_ip_aula.py` |
| Backend y frontend | **cada asistente** | `<sistema>/taller-up` |
| Los baja | cada asistente | `<sistema>/taller-down` |
| **Minuto 0.** Diagnóstico con la acción para cada falla | cada asistente | `verificar_ambiente.py` |
| Vuelve el dominio al estado inicial | cada asistente | `<sistema>/reiniciar-datos` |

Windows usa `.\scripts\win\aula-up.ps1`; Linux y macOS,
`./scripts/linux/aula-up.sh` y `./scripts/mac/aula-up.sh`.

`reiniciar-datos` se usa más de lo que parece: entre práctica y práctica, y
después de cada demo de falla del bloque 5 — sobre todo la que cancela lo que no
debía.

---

## Qué está duplicado y qué no

Esto importa a la hora de corregir algo.

**Idénticos entre `linux/` y `mac/`** — una corrección va a los dos:

```
taller-up.sh   taller-down.sh   aula-down.sh
reiniciar-datos.sh   copiar-volumen-ollama.sh
```

**Genuinamente distintos en los tres sistemas** — cada uno tiene su propia
lógica, no solo su propia sintaxis:

| Script | En qué difiere |
|---|---|
| `aula-ip` | Enumerar interfaces de red no se parece en nada: `Get-NetIPAddress` en Windows, `ip -o -4 addr` en Linux, y en macOS la interfaz de la ruta por omisión vía `route -n get default`. Los tres filtran Docker, WSL, Hyper-V, Kubernetes y las VPN, porque **el salón no las alcanza** y es el error que cuesta diez minutos de taller. |
| `aula-firewall` | Windows tiene `New-NetFirewallRule`. Linux puede tener `ufw`, `firewalld` o `iptables` pelado, y el script detecta cuál está activo. En macOS el firewall filtra **por aplicación y no por puerto**, así que no hay regla equivalente: el script informa el estado y explica cómo permitir Docker. |
| `aula-up` | La versión de macOS **avisa y pide confirmación antes de arrancar**: Docker Desktop no accede a la GPU ahí, así que un 9B correría en CPU — inservible para un taller de cuatro horas. En una Mac hay que usar Ollama nativo (`brew install ollama`), que sí usa Metal. La de Linux avisa si falta el NVIDIA Container Toolkit. |

---

## Tres trampas que cuestan tiempo de taller

**La verificación del firewall hay que hacerla desde otra laptop.** Desde
`localhost` todo funciona siempre, y eso no prueba nada. Los tres
`aula-firewall` terminan ejecutando `aula-ip`, que imprime el `curl` exacto para
correr desde afuera.

**`aula-ip` y `aula-firewall` de `linux/` y `mac/` detectan Git Bash** por
`uname` y mandan a `scripts\win\`, en lugar de fallar de forma confusa en una
máquina Windows.

**Nunca `docker compose down -v` en `infra/aula/`.** El volumen de modelos es
externo y lo comparte el proyecto itzae: `-v` borraría los 10 GB de los dos.
Ningún `aula-down` lo pasa.
