# infra/

Dos `docker-compose` y no uno, porque el taller corre en dos lugares distintos.

| Carpeta | Dónde corre | Qué levanta |
|---|---|---|
| [`aula/`](aula/) | **Solo la máquina del instructor** | Ollama con `qwen3.5:9b`, en la GPU, expuesto a la LAN |
| [`taller/`](taller/) | **La laptop de cada asistente** | El backend y el frontend. Sin GPU, sin modelo. |

Lo caro es central y lo barato es local. El modelo de 6.6 GB se baja una vez y
lo comparte el salón; el backend y el frontend son locales para que cada quien
tenga su propio tablero. Si el backend fuera compartido, veinte personas
escribirían en el mismo estado y cada demo se contaminaría con la de al lado.
Lo único que se centraliza es la inferencia, que es lo único sin estado.

Nadie corre `docker compose` a mano: lo envuelven los scripts de
[`../scripts/`](../scripts/).

## El volumen de modelos

`aula/docker-compose.yml` declara el volumen como **externo**, apuntando a
`itzae_itzae_ollama_data` — donde `qwen3.5:9b` ya está descargado. Eso evita
bajar 6.6 GB el día del taller.

El costo es que se comparte con itzae: un `ollama pull` desde el taller escribe
en el mismo volumen. Para aislarlo, `copiar-volumen-ollama` (en `../scripts/win/`,
`linux/` o `mac/`) una
vez (son ~10 GB y unos minutos) y cambiar el `name:` del compose.

**`docker compose down -v` en `aula/` borraría los modelos de los dos
proyectos.** Ningún `aula-down` pasa `-v`.

## Lo que se reutilizó de itzae

- `aula/ollama/entrypoint.sh`, sin cambios: arranca el servidor, espera la API,
  hace `ollama pull` (no-op si ya está) y se queda en primer plano.
- El patrón de healthcheck con `depends_on: condition: service_healthy`.
- `taller/docker-compose.override.yml` con el código montado en vivo y
  `uvicorn --reload`. En un taller donde se edita código en vivo, esto no es
  opcional: es también lo que permite que alguien atorado copie el archivo del
  paso siguiente y lo vea correr de inmediato.

## Lo que cambió respecto de itzae

- Fuera MongoDB, Qdrant, Redis y el encoder de embeddings. No hacen falta.
- Sin `profiles: [ollama]`: aquí Ollama es el centro, no un extra opcional.
- Sin reserva de GPU para el backend. En itzae el backend la necesitaba para el
  encoder y competía con el modelo por los 8 GB; aquí no hay encoder, así que la
  GPU es toda de Ollama y `qwen3.5:9b` entra sin pelear.
- `OLLAMA_KEEP_ALIVE=-1` y `OLLAMA_MAX_LOADED_MODELS=1`, que en un servidor
  compartido por un salón importan más que en uso individual.
