# Más allá del prompt: introducción a los agentes de IA

Taller de 4 horas. Construimos, sin frameworks, un conjunto de agentes simples
en Python y después los orquestamos.

**Requisito:** Python básico. Nada de machine learning.

---

## Antes del taller

Dos cosas instaladas, y conviene hacerlo **con una semana de anticipación**: el
taller no tiene holgura para resolver instalaciones a mitad del bloque 2.

| Qué | Cómo verificar |
|---|---|
| **Python 3.10 o superior** | `python --version` |
| **Docker Desktop**, corriendo | `docker ps` |

En Windows, si `python` no responde, prueba `py --version`. Y si Python se
instaló desde la Microsoft Store, desinstalalo y usá el de
[python.org](https://python.org): el de la Store tiene permisos restringidos que
rompen los ambientes virtuales de formas difíciles de diagnosticar.

### Windows: clona en una ruta corta

> **`C:\agenticai`, no `C:\Users\TuNombre\Documents\Universidad\Cursos\2026\...`**

Esto no es una preferencia de estilo. Windows limita las rutas a 260 caracteres,
y `jupyterlab` arrastra `debugpy` y `jedi`, que traen archivos con rutas de
hasta **148 caracteres** contando desde la raíz del repo. En una carpeta
profunda, `pip install` **falla a mitad de la instalación** con un
`OSError: [Errno 2] No such file or directory` que no menciona la longitud de la
ruta en ninguna parte — así que nadie lo diagnostica solo.

Las cifras están medidas en esta máquina, no estimadas: el mismo
`requirements.txt`, el mismo Python y el mismo pip fallan en una ruta de 145
caracteres y funcionan en `C:\tmp\prueba_venv`. **El presupuesto para la ruta
del repo es 112 caracteres**, y `verificar_ambiente.py` lo mide.

La alternativa es habilitar rutas largas en el registro, como administrador:

```powershell
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
  -Name LongPathsEnabled -Value 1 -PropertyType DWord -Force
```

Pero para un taller, clonar en `C:\agenticai` es más rápido y no falla.

---

## Arrancar — asistentes del taller

### 1. Clonar el repositorio

```powershell
cd C:\                      # Windows: ruta corta, ver arriba
git clone <url-del-repo> agenticai
cd agenticai
```

### 2. Crear el ambiente virtual

Todo lo que sigue asume que el ambiente está **activado**. Es la fuente de
errores más común: `pip install` sin activar instala en el Python del sistema, y
después `import requests` falla desde el notebook sin explicación aparente.

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Si eso da `no se puede cargar el archivo ... Activate.ps1`, es la política de
ejecución de PowerShell. Dos salidas:

```powershell
# a) permitirlo solo en esta ventana (lo más simple)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1

# b) o usar el activador de cmd, que la política no toca
.\.venv\Scripts\activate.bat
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Sabes que funcionó porque el prompt empieza con `(.venv)`.

### 3. Instalar las dependencias

```bash
pip install -r requirements.txt
```

Son dos paquetes: `requests` y `jupyterlab`. Eso es todo lo que hace falta para
construir un sistema multiagente, y conviene mirar la lista un segundo — es
parte del contenido del taller.

Hay un segundo archivo, [`requirements-frameworks.txt`](requirements-frameworks.txt),
y **no se instala para el taller**: son 81 paquetes que solo necesita el
notebook 09, el que compara el bucle escrito a mano contra LangChain.

### 4. Levantar el backend y el frontend

En tu propia laptop. Sin GPU y sin modelo: son imágenes chicas.

```powershell
.\scripts\win\taller-up.ps1       # Windows
./scripts/linux/taller-up.sh      # Linux
./scripts/mac/taller-up.sh        # macOS
```

La primera vez construye las imágenes y tarda unos minutos. También te crea el
`.env` de la raíz a partir del ejemplo.

### 5. Apuntar a la máquina donde corre Ollama

Copia [`.env.example`](.env.example) a `.env` (`taller-up` ya lo hace) y edita
**una palabra**:

```
OLLAMA_DESTINO=aula
```

Las tres direcciones posibles ya están declaradas ahí y conviven, así que
moverse entre ellas no obliga a volver a averiguar ninguna:

| destino | a dónde habla |
|---|---|
| `localhost` | Ollama en tu propia máquina |
| `aula` | la laptop del instructor, por la red del salón |
| `tec` | el servidor con GPU del Tec, por la VPN |

Durante el taller va `aula`, y la IP la dicta el instructor. **En su máquina
esa línea se escribe sola:** `aula-up` llama a `scripts/fijar_ip_aula.py`, que
detecta la IP de LAN y la fija en el `.env`. Se asigna por DHCP y cambia sola,
así que escribirla a mano envejece mal.

El detector descarta lo que el salón no alcanza —loopback, link-local, las
interfaces de Docker, WSL e Hyper-V— y también **las direcciones con máscara
/32, que es como se ve un cliente de VPN**. Con la VPN del Tec conectada, esa
era la primera candidata de la lista y la peor posible.

El modelo de 6.6 GB vive en la máquina del instructor, no en la tuya.

> **Un solo `.env`, en la raíz.** Lo leen el código de `src/paso*`, los
> notebooks y el contenedor del backend. Y es donde van las claves de API, así
> que no se versiona — está en `.gitignore`.

#### Elegir el modelo: la convención `proveedor:modelo`

```
CHAT_MODEL=ollama:qwen3.5:9b
```

Un solo string dice proveedor y modelo, así que cambiar de uno a otro es
cambiar esta línea — nada de código:

| Valor | Qué usa |
|---|---|
| `ollama:qwen3.5:9b` | el modelo local del taller |
| `ollama:mistral:latest` | el otro modelo local |
| `azure:mi-deployment` | Azure OpenAI |
| `foundry:mi-deployment` | Azure AI Foundry (Mistral Large y otros) |
| `mistral:mistral-large-latest` | api.mistral.ai |

Los de pago necesitan sus claves en el `.env`. La página muestra en el selector
los que estén configurados, y los que no, deshabilitados con "sin configurar" —
así se ve que existen y que falta la clave.

**Las claves nunca llegan al navegador.** La página habla con el backend y el
backend con el proveedor:

```
navegador → nginx :4200 → backend :8000 → proveedor
                              ↑ las claves viven solo aquí
```

Con Ollama local da igual, no hay clave. Con Azure o Mistral no es negociable:
la página es estática y cualquiera puede leer su código fuente.

#### Si eres el instructor: cómo obtener tu IP para compartirla

```powershell
.\scripts\win\aula-ip.ps1          # Windows
./scripts/linux/aula-ip.sh         # Linux
./scripts/mac/aula-ip.sh           # macOS
```

Imprime la línea entera, lista para que el salón la copie:

```
  OLLAMA_URL_AULA=http://192.168.1.NN:11434
      via Wi-Fi
```

El `NN` de arriba es un ejemplo: el script imprime la dirección real que
detectó. Junto con esa línea va `OLLAMA_DESTINO=aula`, que es la que elige el
destino.

Se dicta **la línea completa**, no el número: dictar una IP a veinte personas
genera erratas, y una errata ahí se diagnostica como "no me funciona Ollama".

**Por qué no alcanza con `ipconfig`.** Una laptop típica tiene media docena de
direcciones IPv4 y casi ninguna sirve. En la máquina donde se preparó este
material había siete, y seis eran inútiles para el taller:

| Forma de la dirección | Interfaz | |
|---|---|---|
| `192.168.x.x` | Wi-Fi o Ethernet | **la que se dicta** |
| `172.x.x.x` | vEthernet (WSL), Docker, Hyper-V | virtual: el salón no la alcanza |
| `169.254.x.x` | VPN, Bluetooth, Local Area Connection* | link-local, no las enruta nadie |
| cualquiera con máscara `/32` | cliente de VPN | cambia en cada reconexión |
| `127.0.0.1` | Loopback | solo tu máquina |

Por eso la elige un script y no tú: `fijar_ip_aula.py` descarta esas cinco
formas y se queda con la que el salón puede alcanzar.

Dictar por error la de Docker o de WSL es el error que cuesta diez minutos de
taller, porque *parece* una IP de red local. El script filtra las virtuales
(Docker, WSL, Hyper-V, VPN), las link-local y loopback, y deja solo las
candidatas reales.

Si prefieres hacerlo a mano:

```powershell
# Windows
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.PrefixOrigin -eq "Dhcp" }
```

```bash
ip -o -4 addr show scope global          # Linux
ipconfig getifaddr en0                   # macOS (Wi-Fi)
```

#### Verifícalo desde OTRA laptop

```bash
curl http://192.168.1.NN:11434/api/tags      # la IP que imprimio aula-ip
```

**Desde `localhost` siempre funciona, y eso no prueba nada.** Conviene probarlo
días antes, no el día del taller.

#### Si el curl no devuelve nada: el orden de diagnóstico

Esta es la tabla que resuelve el 90% de los "no me conecto", y sirve igual para
el instructor que para un asistente. La clave es comparar **las dos
direcciones**: `localhost` y la IP de LAN.

| `localhost` | la IP de LAN | Qué pasa | Qué hacer |
|---|---|---|---|
| falla | falla | **Ollama no está arriba.** No hay nada escuchando. | `scripts/<sistema>/aula-up` |
| responde | falla | **El firewall bloquea.** El servicio está bien. | `scripts/<sistema>/aula-firewall` |
| responde | responde | Está bien **en esta máquina**. No dice nada del salón. | probar desde otra laptop |

Si las dos fallan idénticamente, no pierdas tiempo con el firewall: el problema
es que el servicio no existe. Para confirmarlo:

```powershell
docker ps --filter name=agenticai_ollama        # ¿hay contenedor?
netstat -ano | findstr :11434                   # ¿alguien escucha?
```

#### El error de TLS, que engaña a todo el mundo

```
curl: (35) TLS connect error: error:0A00010B:SSL routines::wrong version number
curl: (35) schannel: ... SEC_E_INVALID_TOKEN ...
```

**La causa es una `s` de más: usaste `https://` y Ollama habla HTTP plano.**

```bash
curl http://192.168.1.NN:11434/api/tags      # así
curl https://192.168.1.NN:11434/api/tags     # no: Ollama no hace TLS
```

Y es un error que, paradójicamente, **confirma que todo lo demás está bien**:
para que falle un handshake TLS, el TCP tuvo que establecerse primero. Firewall
abierto, red llegando, Ollama respondiendo. Lo único roto era el esquema.

Conviene saberlo antes de empezar, porque la palabra "SSL" manda a cualquiera
a investigar certificados durante veinte minutos. Lo mismo aplica al `.env`:
tiene que decir `http://`, nunca `https://`.


#### Windows: el perfil de red, que es la trampa de verdad

Una regla de firewall **solo aplica a los perfiles que declara**. Si tu red está
marcada como *Pública* y la regla es *Privada*, la regla se crea, el script dice
"listo", y el salón sigue sin poder conectarse. Es el peor tipo de falla: la que
reporta éxito.

```powershell
Get-NetConnectionProfile      # ¿Public o Private?
```

`aula-firewall.ps1` detecta esto, **se detiene antes de crear una regla
inservible** y te ofrece las dos salidas:

```powershell
# Recomendado: marcar la red del aula como privada (requiere admin)
Set-NetConnectionProfile -InterfaceAlias 'Wi-Fi' -NetworkCategory Private

# O, si no puedes cambiarla, incluir el perfil público acotado a la subred
.\scripts\win\aula-firewall.ps1 -IncluirRedPublica -Subred '192.168.1.0/24'
```

La segunda opción abre el puerto en cualquier red pública a la que te conectes
después, así que acótala con `-Subred` y quítala al terminar con `-Quitar`.

### 6. Verificar

```bash
python scripts/verificar_ambiente.py
```

Comprueba Python, `requests`, el `.env`, que Ollama responda, que tenga el
modelo cargado, y el backend y el frontend. Para cada falla dice qué hacer. Si
todo está en verde, sigue.

### 7. Abrir los notebooks

```bash
jupyter lab
```

**Desde el ambiente activado**, o el notebook no va a encontrar `requests`.
Empieza por `notebooks/00_verificacion_ambiente.ipynb`.

---

## Arrancar — instructor

Los pasos 1 a 3 son los mismos (clonar, ambiente virtual, `pip install`).
Después:

```powershell
# Una vez, como administrador: abre el puerto 11434 en el firewall.
# Publicar el puerto en Docker NO alcanza, y desde localhost todo
# parece funcionar — hay que probarlo desde otra laptop.
.\scripts\win\aula-firewall.ps1

# Levanta Ollama en la GPU e imprime la IP que hay que dictarle al salón.
.\scripts\win\aula-up.ps1

# EL PRIMERO DE TODOS, antes de escribir más material:
# ¿el modelo hace tool calling de verdad? Es el riesgo #1 del plan.
python scripts/smoke_test_tools.py
```

En Linux o macOS son los mismos en `scripts/linux/` o `scripts/mac/`. En una
Mac, `aula-up.sh` avisa y pide confirmación antes de arrancar: Docker Desktop no
accede a la GPU ahí, así que hay que usar Ollama nativo (`brew install ollama`),
que sí usa Metal.

Y en tu `.env` de la raíz, `OLLAMA_DESTINO=localhost`: Ollama corre en tu
propia máquina, y esa dirección ya viene declarada en `OLLAMA_URL_LOCALHOST`.

**Opcional, una vez:** `copiar-volumen-ollama` aísla el volumen de modelos
del proyecto itzae, que por omisión se comparte. Son ~10 GB y unos minutos; los
detalles en [infra/README.md](infra/README.md).

---

## Operación diaria

Lo de arriba es la instalación, que se hace una vez. Esto es lo que se usa
después. Los comandos son de Windows; en Linux y macOS son los mismos en
`scripts/linux/` o `scripts/mac/` con extensión `.sh`.

### Arrancar

```powershell
# Instructor (Ollama en la GPU, compartido por el salón)
.\scripts\win\aula-up.ps1

# Cada laptop (backend + frontend, local)
.\scripts\win\taller-up.ps1

# Y verificar
python scripts\verificar_ambiente.py
```

El instructor corre **los dos**: `aula-up` para el modelo y `taller-up` para su
propio tablero. Un asistente corre solo `taller-up`.

A partir de la segunda vez no reconstruye imágenes ni descarga el modelo:
arranca en segundos.

### Detener

```powershell
.\scripts\win\taller-down.ps1     # backend + frontend
.\scripts\win\aula-down.ps1       # ollama
```

**Son dos comandos porque son dos proyectos compose distintos** — `aula` y
`taller`. La separación es deliberada: lo caro es central y lo barato es local.

Qué **sobrevive** a bajarlos:

| | |
|---|---|
| Las imágenes | `taller-up` no reconstruye |
| El volumen de modelos | ningún `aula-down` pasa `-v` |
| Las trazas y el estado del dominio | viven en `datos/`, montado como bind |

> **Nunca `docker compose down -v` en `infra/aula/`.** El volumen de modelos es
> externo y lo comparte el proyecto itzae: `-v` borraría los 10 GB de los dos.

### El firewall

Solo en la máquina del instructor, y **requiere PowerShell como
administrador**. Es lo único que no se levanta ni se baja con los scripts de
arriba: persiste hasta que lo quites a mano.

```powershell
# Abrirlo. Si tu red está marcada como Privada, alcanza con esto:
.\scripts\win\aula-firewall.ps1

# Si está marcada como Pública, el script se detiene y te avisa.
# En una red de campus o compartida, la salida correcta es acotar a la subred:
.\scripts\win\aula-firewall.ps1 -IncluirRedPublica -Subred '192.168.1.0/24'

# Ver si la regla existe
Get-NetFirewallRule -DisplayName "Agenticai - Ollama taller (11434)"

# Cerrarlo al terminar el taller
.\scripts\win\aula-firewall.ps1 -Quitar
```

En una red que controlas (tu casa), la alternativa más simple es marcarla como
privada una vez y usar la forma corta:

```powershell
Set-NetConnectionProfile -InterfaceAlias 'Wi-Fi' -NetworkCategory Private
```

**No marques como privada una red ajena**: habilita descubrimiento de red y
compartición de archivos hacia desconocidos. Para el campus, `-IncluirRedPublica
-Subred` y `-Quitar` al terminar.

En Linux y macOS, `aula-firewall.sh` hace lo equivalente — `ufw`, `firewalld` o
`iptables` según lo que tengas; en macOS informa el estado, porque ahí el
firewall filtra por aplicación y no por puerto.

### Reiniciar los datos del dominio

Entre práctica y práctica, y después de cada demo de falla del bloque 5:

```powershell
.\scripts\win\reiniciar-datos.ps1
```

---

## Windows, Linux o macOS

```
scripts/
├── win/     8 scripts .ps1   — Windows / PowerShell
├── linux/   8 scripts .sh    — Linux
├── mac/     8 scripts .sh    — macOS
└── los dos diagnósticos .py  — corren en los tres sistemas sin cambios
```

**Busca la carpeta de tu sistema y ahí está todo.** Cada una es autocontenida:
no hay que leer ramas de `if` para saber qué aplica.

Tres scripts no son traducción literal, porque la lógica difiere de verdad —
detectar la IP de LAN, abrir el firewall, y la GPU en macOS. Está explicado en
[scripts/README.md](scripts/README.md).

Si corres un `.sh` en Git Bash sobre Windows, los que no funcionan ahí te mandan
a `scripts\win\` en lugar de fallar de forma confusa.

---

## El repositorio

| Carpeta | Qué hay |
|---|---|
| [`planeacion/`](planeacion/) | El plan del taller, las decisiones de diseño, el [estilo de la prosa](planeacion/estilo.md) y los [hallazgos medidos](planeacion/hallazgos.md). **Empieza por aquí.** |
| [`src/`](src/) | El código: los 5 pasos, el backend y el frontend. |
| [`notebooks/`](notebooks/) | Las demostraciones. Escritas para correrse solo, sin el instructor al lado. |
| [`infra/`](infra/) | Los `docker-compose`: `aula/` para Ollama, `taller/` para el resto. |
| [`scripts/`](scripts/) | Envoltorios de arranque y los dos diagnósticos. |
| [`datos/`](datos/) | La semilla del dominio. |
| [`slides/`](slides/) | Diapositivas de los bloques 1 y 5. |

## Cómo está repartido lo que corre dónde

Lo caro es central y lo barato es local:

```
MÁQUINA DEL INSTRUCTOR          CADA LAPTOP
  ollama  :11434        <----     el código Python del paso en curso
  GPU, qwen3.5:9b                 backend   :8000
  compartido por el salón         frontend  :4200
                                  sin GPU, sin modelo
```

El modelo de 6.6 GB se baja una sola vez y lo comparte el salón. El backend y
el frontend **no** se comparten: si lo fueran, veinte personas escribirían en el
mismo tablero y cada demo se contaminaría con la de al lado. Lo único central es
la inferencia, que es lo único sin estado.

## La regla del taller

**Nada de LangChain, LlamaIndex, CrewAI ni AutoGen.** Solo `requests` y la
librería estándar.

No es purismo. El valor de estas cuatro horas es que **no hay magia**: el bucle
agéntico son sesenta líneas que el asistente escribe y mira. Un framework las
esconde justo cuando hay que verlas. Los frameworks se mencionan al final — y
ahí ya se entienden como una conveniencia, no como una caja negra.

Por el mismo motivo, [`src/agentlib/`](src/agentlib/) contiene solo el
transporte HTTP y la traza. El bucle no vive ahí.

## Antes de hacer commit

Las celdas de imports de los notebooks imprimen la ruta del `.env` y la
dirección de Ollama, así que **cada vez que vuelves a correr un notebook,
reaparecen en las salidas guardadas** tu carpeta de usuario y la IP del
servidor. Un script las saca:

```bash
python scripts/redactar_salidas.py --revisar   # ¿hay algo? devuelve 1 si sí
python scripts/redactar_salidas.py             # redactarlo
```

Las direcciones las lee de tu `.env`, así que no tiene ninguna IP escrita
adentro y sigue sirviendo cuando cambien. Solo toca `outputs`: si una dirección
quedó escrita en el código o en el markdown, la reporta para que la arregles a
mano.

---

## Licencia

Dos licencias, porque el repositorio tiene dos cosas distintas:

| qué | licencia | archivo |
|---|---|---|
| el **código**: `src/`, `scripts/`, `infra/` y las celdas de código de los notebooks | MIT | [LICENSE](LICENSE) |
| el **material**: el texto de los notebooks, `notebooks/imagenes/` y los `README` | CC BY 4.0 | [LICENSE-MATERIAL](LICENSE-MATERIAL) |

Puedes dar este taller en tu clase, traducirlo, recortarlo o construir otro
encima. La única condición del material es **dar crédito**, y hay una
atribución de ejemplo en [LICENSE-MATERIAL](LICENSE-MATERIAL).

Los datos de terceros conservan la licencia de su origen; ver
[datos/README.md](datos/README.md).

---

## Estado

| Parte | Estado |
|---|---|
| Plan del taller | completo |
| Infraestructura (Ollama, compose, scripts) | completo |
| Pasos 1 a 4 | completos |
| Notebooks 00 a 04 | completos |
| Notebooks 07 y 08 (caso NAS y laboratorio de la ventana) | completos |
| Chat del frontend, panel de parámetros y capa de proveedores (ollama/azure/foundry/mistral) | completo |
| Backend de inventario (CRUD sobre CSV) y su diagnóstico de Ollama | completo |
| Estilo de la prosa ([`planeacion/estilo.md`](planeacion/estilo.md)) | fijado y aplicado |
| Notebooks 05 y 06, y el caso de clientes de [`src/mdm/`](src/mdm/) | completos |
| Tablero del frontend | **pendiente del caso de estudio** |

El caso de estudio está en discusión: [`planeacion/caso-de-estudio.md`](planeacion/caso-de-estudio.md).
Lo que ya está hecho es lo que no depende del dominio.
