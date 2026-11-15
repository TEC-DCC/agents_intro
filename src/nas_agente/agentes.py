"""
Cuatro agentes que buscan el mejor predictor de rendimiento para NAS.

Es el primer sistema multiagente del repositorio, y el reparto sigue la regla
del paso 5: **cada agente tiene una responsabilidad y las tools que esa
responsabilidad necesita, ni una mas.**

    ANALISTA        mira los datos y reporta lo que encuentra.    solo lectura
    EXPERIMENTADOR  entrena y evalua predictores.                 el unico que
                                                                  gasta CPU
    ESTADISTICO     dice si las diferencias son reales.           solo lectura
    ORQUESTADOR     reparte el trabajo y redacta la conclusion.   sus tools son
                                                                  los otros tres

El Orquestador usa el patron **agente-como-tool**: sus tools no son funciones
de Python, son los otros agentes. Eso hace el handoff explicito y visible, que
es justo lo que hay que ver en el bloque 5.

El agente que de verdad gana su lugar es el ESTADISTICO, y es poco comun: su
trabajo es *desconfiar de los otros*. Sin el, el sistema reporta el maximo de
una lista y lo llama ganador. El propio paper muestra que Extra Trees, SVR,
XGBoost y Random Forest son estadisticamente indistinguibles.
"""

import json
import sys
import textwrap
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentlib import chat, normalizar_argumentos, ultima_medicion  # noqa: E402

from . import laboratorio as lab  # noqa: E402

MAX_VUELTAS = 10

# El Experimentador necesita mas que los otros: el catalogo tiene 18
# predictores y, si los pide de uno en uno, con 10 vueltas no llega ni a
# terminar los once del paper. No es un numero magico: es 18 + el catalogo +
# margen para que relea faltan_por_evaluar un par de veces.
VUELTAS_EXPERIMENTADOR = 30


# ---------------------------------------------------------------------------
# La vista detallada: que se manda y que vuelve en cada vuelta
#
# El bucle agentico se entiende cuando se ve que en CADA vuelta se manda la
# conversacion ENTERA otra vez. El modelo no recuerda nada: lo que parece
# memoria es que el programa le vuelve a contar todo cada vez.
#
# Por eso el detalle muestra solo lo NUEVO de cada vuelta, pero dice siempre
# cuantos mensajes van en total y cuantos tokens peso el envio. Con 4096
# tokens de contexto real, ver ese numero subir es la mitad de la leccion.
# ---------------------------------------------------------------------------
ANCHO = 1000


def _imprimir(texto=""):
    """
    print() que no tumba el programa.

    La consola de Windows usa cp1252 y el modelo escribe emojis cuando le
    parece. Medido: una corrida completa del orquestador murio con
    UnicodeEncodeError al imprimir un \U0001f4ca en medio de una conclusion
    correcta. En Jupyter no pasa porque usa UTF-8; en la terminal del aula,
    si. Que el programa se caiga por un caracter que el modelo eligio es
    inaceptable: se reemplaza y se sigue.
    """
    try:
        print(texto)
    except UnicodeEncodeError:
        codigo = getattr(sys.stdout, "encoding", None) or "ascii"
        print(texto.encode(codigo, "replace").decode(codigo))


def _recortar(texto, ancho=ANCHO):
    texto = (texto or "").replace("\n", " ").strip()
    return texto if len(texto) <= ancho else texto[:ancho - 3] + "..."


def _linea_mensaje(m):
    """Una linea por mensaje, diciendo que lleva adentro."""
    rol = m.get("role", "?")
    contenido = m.get("content") or ""
    if m.get("tool_calls"):
        pedidos = ", ".join(p["function"]["name"] + "(...)"
                            for p in m["tool_calls"])
        cuerpo = f"PIDE: {pedidos}"
        if contenido.strip():
            cuerpo += f"   + texto: {_recortar(contenido)}"
    else:
        cuerpo = _recortar(contenido) or "(vacio)"
    tam = f"{len(contenido):>6} chars" if contenido else "            "
    return f"      {rol:<10} {tam}  {cuerpo}"


def _cabecera(nombre_agente, vuelta, mensajes, herramientas, ya_mostrados):
    print(f"\n  {'=' * 108}")
    print(f"  VUELTA {vuelta}  ({nombre_agente})")
    print(f"  {'=' * 108}")
    nuevos = len(mensajes) - ya_mostrados
    print(f"  --> SE ENVIA: los {len(mensajes)} mensajes de la conversacion "
          f"+ los esquemas de {len(herramientas)} tools")
    if ya_mostrados:
        print(f"      ({ya_mostrados} ya se mostraron arriba; aqui solo "
              f"{'lo nuevo' if nuevos else 'no hay nada nuevo'})")
    for m in mensajes[ya_mostrados:]:
        _imprimir(_linea_mensaje(m))


def _mostrar_respuesta(respuesta, segundos):
    medicion = ultima_medicion()
    enviados = medicion["tokens_enviados"]
    generados = medicion["tokens_generados"]
    aviso = "  <-- OJO: el contexto real son 4096" if (enviados or 0) > 3500 else ""
    print(f"  <-- VUELVE en {segundos:.1f} s   "
          f"tokens: {enviados} enviados, {generados} generados{aviso}")
    _imprimir(_linea_mensaje(respuesta))


# ---------------------------------------------------------------------------
# El bucle. Es el del paso 4 con sus guardrails, sin la confirmacion humana:
# aqui ninguna tool es destructiva, solo gastan CPU.
# ---------------------------------------------------------------------------
def _bucle(nombre_agente, system, herramientas, disponibles, peticion, ver=True,
           max_vueltas=MAX_VUELTAS, detalle=False):
    """
    El bucle agentico. Con detalle=True imprime, vuelta por vuelta, que se le
    manda al modelo, que devuelve y que se ejecuto en tu maquina.
    """
    mensajes = [{"role": "system", "content": system},
                {"role": "user", "content": peticion}]
    vistas = []
    mostrados = 0   # cuantos mensajes ya se imprimieron, para no repetirlos

    for vuelta in range(1, max_vueltas + 1):
        if detalle:
            _cabecera(nombre_agente, vuelta, mensajes, herramientas, mostrados)
            mostrados = len(mensajes)
        elif ver:
            # Una linea por vuelta, aunque no se pida el detalle. Sin esto, el
            # Experimentador imprime veinte llamadas seguidas y no hay forma de
            # saber cuales fueron en la misma vuelta -que es justo lo que hay
            # que ver: el modelo puede pedir varias tools de un tiron.
            print(f"  --- vuelta {vuelta} de {nombre_agente} " + "-" * 38)

        t0 = time.time()
        respuesta = chat(mensajes, herramientas=herramientas)
        if detalle:
            _mostrar_respuesta(respuesta, time.time() - t0)
            mostrados += 1

        mensajes.append(respuesta)
        pedidos = respuesta.get("tool_calls") or []

        if not pedidos:
            texto = respuesta.get("content", "")
            if detalle:
                print(f"\n  No pidio ninguna tool: el bucle TERMINA aqui, en la "
                      f"vuelta {vuelta}.")
                print(f"  Costo total: {len(mensajes)} mensajes en la "
                      f"conversacion final.\n")
            if ver:
                # Completo, sin truncar. Estos agentes devuelven analisis de
                # varias frases, y cortarlos a 300 caracteres deja la conclusion
                # a medias -justo la parte que interesa leer.
                sangrado = texto.replace("\n", "\n      ")
                _imprimir(f"  [{nombre_agente}] {sangrado}")
            return texto

        if detalle:
            print(f"  --- SE EJECUTA EN TU MAQUINA ({len(pedidos)} "
                  f"{'tool' if len(pedidos) == 1 else 'tools'}). El modelo no "
                  f"ejecuta nada: solo pidio.")

        for pedido in pedidos:
            nom = pedido["function"]["name"]
            args = normalizar_argumentos(pedido)
            firma = (nom, json.dumps(args, sort_keys=True))

            if nom not in disponibles:
                resultado = {"error": f"no existe la tool '{nom}'",
                             "disponibles": list(disponibles)}
            elif firma in vistas:
                resultado = {"error": "ya ejecutaste esta misma peticion; "
                                      "usa lo que ya tienes o prueba otra cosa"}
            else:
                vistas.append(firma)
                try:
                    resultado = disponibles[nom](**args)
                except TypeError as e:
                    resultado = {"error": f"argumentos invalidos: {e}"}

            devuelto = json.dumps(resultado, ensure_ascii=False)
            if detalle:
                _imprimir(f"      {nom}({json.dumps(args, ensure_ascii=False)})")
                _imprimir(f"        -> {_recortar(devuelto)}")
                print(f"        ({len(devuelto)} chars, y los {len(devuelto)} "
                      f"se le mandan de vuelta al modelo en la proxima vuelta)")
            elif ver:
                _imprimir(f"  [{nombre_agente}] {nom}({args}) -> {devuelto}")
            mensajes.append({"role": "tool", "content": devuelto})

    return (f"[{nombre_agente}] se quedo sin vueltas: llego al tope de "
            f"{max_vueltas} y no termino")


# ---------------------------------------------------------------------------
# 1. ANALISTA — mira los datos. No toca nada.
# ---------------------------------------------------------------------------
TOOLS_ANALISTA = [
    {"type": "function", "function": {
        "name": "describir_dataset",
        "description": "Forma del dataset, rangos de los tokens, cromosomas "
                       "repetidos y estadisticas del PSNR objetivo.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "revisar_correlaciones",
        "description": "Correlacion lineal de cada token con el PSNR.",
        "parameters": {"type": "object", "properties": {}}}},
]

SYSTEM_ANALISTA = (
    # Esta primera linea no es adorno: SIN ella, medido, el analista responde
    # sin llamar ninguna tool 5 de 5 veces, e inventa el dataset entero.
    "NUNCA respondas sin haber llamado una tool primero: no conoces este "
    "dataset de memoria y cualquier cifra que no venga de una tool es inventada. "
    "Eres un analista de datos. Inspeccionas el dataset con las tools y "
    "reportas lo que encuentras en 4 o 5 lineas, en espanol. "
    "Menciona SIEMPRE los problemas que veas -datos repetidos, valores "
    "sospechosos- aunque no te los pregunten: de eso depende que lo que venga "
    "despues sirva. No propongas modelos: no es tu trabajo."
)


def analista(peticion="Describe el dataset y dime que problemas tiene.",
             ver=True, detalle=False):
    return _bucle("ANALISTA", SYSTEM_ANALISTA, TOOLS_ANALISTA,
                  {"describir_dataset": lab.describir_dataset,
                   "revisar_correlaciones": lab.revisar_correlaciones},
                  peticion, ver, detalle=detalle)


# ---------------------------------------------------------------------------
# 2. EXPERIMENTADOR — el unico que gasta CPU.
# ---------------------------------------------------------------------------
TOOLS_EXPERIMENTADOR = [
    {"type": "function", "function": {
        "name": "listar_predictores",
        "description": "El catalogo: que predictores se pueden evaluar, cuales "
                       "son los del paper, cuales faltan por evaluar todavia y "
                       "cuanto tarda cada uno. Llamala ANTES de evaluar nada.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "evaluar_predictor",
        # Ojo con esta descripcion: NO enumera los nombres validos, y es a
        # proposito. Cuando los enumeraba, listar_predictores no se llamaba
        # nunca -medido, 0 de 4 corridas contra 4 de 4 sin la enumeracion-.
        # El modelo no pide un catalogo que ya tiene a la vista en otro
        # esquema. Apuntar a la tool en vez de copiarle el contenido es lo que
        # hace que la tool exista de verdad.
        "description": "Entrena un predictor con validacion cruzada de 10 folds "
                       "y devuelve c_index (mayor es mejor) y mse (menor es "
                       "mejor). Los nombres validos salen de listar_predictores: "
                       "llamala primero. Tarda entre 0.02 y 25 segundos segun "
                       "cual pidas.",
        "parameters": {"type": "object", "properties": {
            "predictor": {"type": "string",
                          "description": "nombre exacto, tal como lo devuelve "
                                         "listar_predictores"},
            "codificacion": {"type": "string",
                             "description": "entero (por omision), onehot o binario"}},
            "required": ["predictor"]}}},
    {"type": "function", "function": {
        # La rejilla corre ENTERA dentro de esta tool y vuelve una sola linea:
        # el ganador. Si el agente probara las 26 configuraciones de SVR una
        # por una serian 26 vueltas, y el contexto real son 4096 tokens.
        "name": "buscar_hiperparametros",
        "description": "Prueba decenas de configuraciones de un predictor y "
                       "devuelve SOLO la mejor. Para los once del paper usa su "
                       "rejilla publicada. CARA: entre 1 y 60 segundos segun el "
                       "predictor. Usala solo en los que ya quedaron arriba del "
                       "ranking, no en todos.",
        "parameters": {"type": "object", "properties": {
            "predictor": {"type": "string",
                          "description": "nombre exacto, como en listar_predictores"},
            "codificacion": {"type": "string",
                             "description": "entero (por omision), onehot o binario"}},
            "required": ["predictor"]}}},
    {"type": "function", "function": {
        # Esta tool no mide nada nuevo: ordena lo ya medido. Esta aqui porque
        # el modelo, con los 18 resultados delante, arma mal el ranking 3 de
        # 3 veces. Ordenar es trabajo de `sorted()`, no de un LLM.
        "name": "ranking",
        "description": "Ordena lo que ya se evaluo y devuelve los mejores. "
                       "USALA para el cierre en vez de ordenar tu los numeros.",
        "parameters": {"type": "object", "properties": {
            "metrica": {"type": "string",
                        "description": "c_index (por omision) o mse"},
            "top": {"type": "integer",
                    "description": "cuantos devolver; 5 por omision. Si te "
                                   "piden el orden COMPLETO del mejor al peor, "
                                   "pasa 30 y devuelve la lista entera"}},
            "required": []}}},
]

SYSTEM_EXPERIMENTADOR = (
    "NUNCA reportes una metrica que no venga de evaluar_predictor: no conoces "
    "estos resultados de memoria. "
    "EMPIEZA SIEMPRE llamando listar_predictores: los nombres validos no los "
    "sabes de memoria, dependen de lo que este instalado en esta maquina, y la "
    "lista te dice ademas cuales te faltan. "
    "Eres un investigador de machine learning. Evaluas predictores de "
    "rendimiento para Neural Architecture Search. "
    "LA METRICA QUE IMPORTA ES c_index, no mse: en NAS lo que se necesita es "
    "ORDENAR arquitecturas correctamente, no acertar el valor exacto. Un "
    "predictor con mejor mse pero peor c_index es peor para esta tarea. "
    "Evalua TODOS los del catalogo sin saltarte ninguno: primero los de "
    "del_paper, que son los que se pueden contrastar con un resultado "
    "publicado, y despues los de agregados_por_nosotros. Puedes pedir varias "
    "evaluaciones en la misma vuelta. Si pierdes la cuenta, vuelve a llamar "
    "listar_predictores y mira faltan_por_evaluar. "
    "Cuando hayas evaluado todo el catalogo, llama a ranking y DESPUES usa "
    "buscar_hiperparametros en los TRES primeros, no en todos: esa busqueda "
    "cuesta hasta 60 segundos cada una. Los predictores del catalogo corren "
    "con valores por omision, y ajustarlos cambia el orden -medido: knn sube "
    "de 0.5686 a 0.6595 solo con cambiarle los hiperparametros-. "
    "Si te piden el orden COMPLETO del mejor al peor, llama a ranking con "
    "top=30 y devuelve la lista entera tal como viene, sin reordenarla tu. "
    "No declares un ganador: eso no te toca. Para cerrar llama a ranking: "
    "NO ordenes tu los numeros, que son 18 y te vas a equivocar. Reporta "
    "cuantos predictores evaluaste, cuales ajustaste y el orden que devolvio "
    "ranking, en espanol."
)


def experimentador(peticion="Evalua todos los predictores del catalogo y "
                            "reporta sus metricas.",
                   ver=True, detalle=False):
    return _bucle("EXPERIMENTADOR", SYSTEM_EXPERIMENTADOR, TOOLS_EXPERIMENTADOR,
                  {"listar_predictores": lab.listar_predictores,
                   "evaluar_predictor": lab.evaluar_predictor,
                   "buscar_hiperparametros": lab.buscar_hiperparametros,
                   "ranking": lab.ranking},
                  peticion, ver, max_vueltas=VUELTAS_EXPERIMENTADOR,
                  detalle=detalle)


# ---------------------------------------------------------------------------
# 3. ESTADISTICO — el que desconfia de los demas.
# ---------------------------------------------------------------------------
TOOLS_ESTADISTICO = [
    {"type": "function", "function": {
        "name": "comparar_evaluaciones",
        "description": "Prueba de Friedman sobre todo lo evaluado. Dice si las "
                       "diferencias son significativas y cuales predictores son "
                       "indistinguibles entre si.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "comparar_con_el_paper",
        "description": "Lo que el paper publicado reporta para un predictor.",
        "parameters": {"type": "object", "properties": {
            "predictor": {"type": "string", "description": "por ejemplo extra_trees"}},
            "required": ["predictor"]}}},
]

SYSTEM_ESTADISTICO = (
    "NUNCA concluyas sin haber llamado comparar_evaluaciones primero. "
    "Eres un estadistico y tu trabajo es DESCONFIAR de los resultados que te "
    "pasan. Corre la prueba de Friedman y reporta si las diferencias son "
    "reales o caben en el azar. "
    "Si varios predictores quedan indistinguibles, DILO EXPLICITAMENTE: "
    "nombrar un unico ganador cuando hay empate estadistico es una afirmacion "
    "de mas. En ese caso sugiere desempatar por un criterio secundario, como "
    "el tiempo de entrenamiento. Responde en espanol, 3 o 4 lineas."
)


def estadistico(peticion="Los resultados que hay, son significativos?",
                ver=True, detalle=False):
    return _bucle("ESTADISTICO", SYSTEM_ESTADISTICO, TOOLS_ESTADISTICO,
                  {"comparar_evaluaciones": lab.comparar_evaluaciones,
                   "comparar_con_el_paper": lab.comparar_con_el_paper},
                  peticion, ver, detalle=detalle)


# ---------------------------------------------------------------------------
# 4. ORQUESTADOR — sus tools son los otros agentes
# ---------------------------------------------------------------------------
TOOLS_ORQUESTADOR = [
    {"type": "function", "function": {
        "name": "consultar_analista",
        "description": "Le pide al analista que inspeccione los datos. "
                       "Usalo PRIMERO: no tiene sentido entrenar sobre datos "
                       "que no entiendes.",
        "parameters": {"type": "object", "properties": {
            "peticion": {"type": "string", "description": "que quieres que revise"}},
            "required": ["peticion"]}}},
    {"type": "function", "function": {
        "name": "pedir_experimentos",
        "description": "Le pide al experimentador que evalue predictores, que "
                       "les ajuste los hiperparametros a los mejores, o que "
                       "devuelva el ORDEN COMPLETO de todos del mejor al peor. "
                       "Pidele explicitamente lo que necesites: si quieres el "
                       "orden entero, dilo.",
        "parameters": {"type": "object", "properties": {
            "peticion": {"type": "string", "description": "que quieres que pruebe"}},
            "required": ["peticion"]}}},
    {"type": "function", "function": {
        # La UNICA tool de laboratorio del orquestador, y es de solo lectura:
        # no mide nada, ordena lo que los otros ya midieron.
        #
        # Esta aqui por algo medido. Sin ella, cuando se le pide el orden
        # completo, el orquestador se lo pide al experimentador, lo recibe
        # entero... y al redactar lo COMPRIME: devolvio "Extra Trees, SVR,
        # Hist Gradient Boosting, [otros 15 predictores intermedios], Ridge,
        # Linear...". Un LLM no transcribe listas largas: las resume.
        #
        # Es el mismo problema que el ranking mal ordenado, un piso mas
        # arriba: alli el modelo no sabia ordenar, aqui no sabe copiar. Las
        # dos veces la solucion es la misma, y no es insistir en el prompt.
        "name": "ranking",
        "description": "El orden completo de los predictores ya evaluados, del "
                       "mejor al peor. USALA cuando te pidan el orden o la "
                       "lista completa, y pega lo que devuelva: no se lo pidas "
                       "al experimentador ni lo reescribas de memoria.",
        "parameters": {"type": "object", "properties": {
            "metrica": {"type": "string",
                        "description": "c_index (por omision) o mse"},
            "top": {"type": "integer",
                    "description": "cuantos; usa 30 para la lista completa"}},
            "required": []}}},
    {"type": "function", "function": {
        "name": "consultar_estadistico",
        "description": "Le pide al estadistico que diga si las diferencias "
                       "medidas son reales. Usalo DESPUES de los experimentos y "
                       "ANTES de concluir.",
        "parameters": {"type": "object", "properties": {
            "peticion": {"type": "string", "description": "que quieres que verifique"}},
            "required": ["peticion"]}}},
]

SYSTEM_ORQUESTADOR = (
    "NUNCA respondas sin haber delegado en los especialistas: tu no tienes "
    "acceso a los datos ni a los resultados, solo ellos. "
    "Coordinas a tres especialistas para encontrar el mejor predictor de "
    "rendimiento para Neural Architecture Search. "
    "El orden que funciona es: analista, despues experimentador, despues "
    "estadistico. No concluyas sin haber consultado al estadistico. "
    # Las tres preguntas que se pueden hacer. Estan enumeradas porque el
    # modelo, si no, contesta solo la primera y da por terminado el trabajo.
    "Te pueden pedir tres cosas distintas, y a veces las tres a la vez: "
    "(1) CUAL es el mejor predictor; "
    "(2) el ORDEN COMPLETO de todos, del mejor al peor; "
    "(3) si el resultado es SOLIDO, o sea si las diferencias son reales. "
    "Lee la peticion y fijate cuantas de las tres te estan pidiendo: "
    "contesta TODAS las que te pidan, cada una en su propio parrafo, y no des "
    "por terminado el trabajo despues de la primera. "
    "Para el orden completo NO se lo pidas al experimentador: llama tu a "
    "ranking con top=30 DESPUES de que el haya evaluado, y pega la lista "
    "entera tal como viene, con todos sus renglones. No escribas '[otros N "
    "predictores]' ni resumas el medio de la lista: si te pidieron el orden "
    "completo, completo significa los dieciocho. "
    "Para saber si es solido, el estadistico es el unico que puede decirlo. "
    "Si dice que hay empate, tu conclusion debe decirlo: no nombres un ganador "
    "unico cuando no lo hay; nombra al grupo y sugiere desempatar por un "
    "criterio secundario, como el tiempo de entrenamiento. "
    "Escribe en espanol, y no te extiendas: una recomendacion corta por cada "
    "cosa que te hayan pedido."
)


def orquestador(peticion, ver=True, detalle=False):
    def _sub(agente, nombre):
        def envoltura(peticion):
            if ver or detalle:
                print(f"\n  >>> el orquestador delega en {nombre}")
            # El detalle NO se propaga a los subagentes a proposito: con los
            # cuatro en modo detalle la salida es ilegible. Si quieres ver por
            # dentro a uno de ellos, correlo solo con detalle=True.
            return {"respuesta": agente(peticion, ver=ver)}
        return envoltura

    return _bucle("ORQUESTADOR", SYSTEM_ORQUESTADOR, TOOLS_ORQUESTADOR,
                  {"consultar_analista": _sub(analista, "ANALISTA"),
                   "pedir_experimentos": _sub(experimentador, "EXPERIMENTADOR"),
                   "consultar_estadistico": _sub(estadistico, "ESTADISTICO"),
                   "ranking": lab.ranking},
                  peticion, ver, detalle=detalle)


# ---------------------------------------------------------------------------
# La ficha de cada agente: para mirarlo ANTES de correrlo
#
# Un agente no es "el modelo". Es el modelo mas tres cosas que escribiste tu:
# su system prompt, su lista de tools y los guardrails del bucle. Esas tres
# cosas son TODO lo que hace que el ANALISTA se comporte distinto al
# EXPERIMENTADOR: el modelo que contesta es exactamente el mismo.
#
# `ficha()` las imprime. Es para el que lee, no para el modelo: ningun agente
# llama esta funcion, y no aparece en ninguna lista de tools.
# ---------------------------------------------------------------------------
FICHAS = {
    "analista": {
        "responsabilidad": "mira los datos y reporta lo que encuentra",
        "system": SYSTEM_ANALISTA,
        "tools": TOOLS_ANALISTA,
        "peticion": "Describe el dataset y dime que problemas tiene.",
        "formato": "reportas lo que encuentras en 4 o 5 lineas, en espanol",
        "no_puede": ("entrenar predictores ni proponer modelos: esas tools son "
                     "del Experimentador y no estan en su lista, asi que no "
                     "tiene forma de ejecutarlas aunque quiera"),
    },
    "experimentador": {
        "responsabilidad": "entrena y evalua predictores; el unico que gasta CPU",
        "system": SYSTEM_EXPERIMENTADOR,
        "tools": TOOLS_EXPERIMENTADOR,
        "peticion": ("Evalua todos los predictores del catalogo y reporta "
                     "sus metricas."),
        "formato": ("Reporta cuantos predictores evaluaste, cuales ajustaste "
                    "y el orden que devolvio ranking, en espanol"),
        "no_puede": ("correr la prueba de Friedman ni declarar un ganador: "
                     "eso es del Estadistico. Mide y ordena; no concluye"),
        "vueltas": VUELTAS_EXPERIMENTADOR,
    },
    "estadistico": {
        "responsabilidad": "dice si las diferencias medidas son reales",
        "system": SYSTEM_ESTADISTICO,
        "tools": TOOLS_ESTADISTICO,
        "peticion": "Los resultados que hay, son significativos?",
        "formato": "Responde en espanol, 3 o 4 lineas",
        "no_puede": ("entrenar nada ni mirar el dataset: solo ve lo que el "
                     "Experimentador ya dejo en el pizarron"),
    },
    "orquestador": {
        "responsabilidad": "reparte el trabajo y redacta la conclusion",
        "system": SYSTEM_ORQUESTADOR,
        "tools": TOOLS_ORQUESTADOR,
        "peticion": ("Encuentra el mejor predictor de PSNR para este dataset "
                     "de arquitecturas, dame el orden completo del mejor al "
                     "peor, y dime si el resultado es solido."),
        "formato": ("una recomendacion corta por cada cosa que te hayan "
                    "pedido"),
        "no_puede": ("medir nada: no puede mirar los datos, ni entrenar, ni "
                     "evaluar, ni correr una prueba estadistica. Tres de sus "
                     "cuatro tools son los otros agentes; la cuarta, ranking, "
                     "solo ORDENA lo que ellos ya midieron"),
    },
}

# Si alguien reescribe un system prompt y se olvida de actualizar la ficha,
# esto truena al importar. Es preferible a que la ficha diga en el aula algo
# que el agente ya no recibe.
for _nombre, _f in FICHAS.items():
    assert _f["formato"] in _f["system"], f"la ficha de {_nombre} quedo vieja"


def _firma(funcion):
    """Como se veria la tool si fuera una funcion de Python."""
    parametros = funcion.get("parameters", {})
    props = parametros.get("properties", {})
    if not props:
        return "()"
    obligatorios = parametros.get("required", [])
    return "(" + ", ".join(p if p in obligatorios else f"{p}=..."
                           for p in props) + ")"


def ficha(nombre="analista", crudo=False):
    """
    Imprime con que esta armado un agente, antes de correrlo.

        ficha("analista")              lo legible
        ficha("analista", crudo=True)  ademas, el JSON exacto de las tools

    Lo util de leerla antes es poder comparar: casi todo lo que el agente
    hace despues esta aqui escrito, y lo que NO esta aqui y aun asi pasa es
    justo lo interesante.
    """
    if nombre not in FICHAS:
        print(f"  No hay ficha de '{nombre}'. Hay: {', '.join(FICHAS)}")
        return

    datos = FICHAS[nombre]
    raya = "=" * 74

    def parrafo(texto, ancho=70, sangria="    "):
        print(textwrap.fill(texto, width=ancho,
                            initial_indent=sangria, subsequent_indent=sangria))

    print(raya)
    print(f"  {nombre.upper()}  -  {datos['responsabilidad']}")
    print(raya)

    print("\n  SU SYSTEM PROMPT")
    print("  Viaja en cada una de sus vueltas, antes de tu pregunta. Es lo")
    print("  unico que lo distingue de los otros tres agentes.")
    print("  " + "-" * 70)
    parrafo(datos["system"])

    tools = datos["tools"]
    print(f"\n  SUS TOOLS ({len(tools)})")
    print("  Es lo UNICO que puede ejecutar. El bucle rechaza cualquier otro")
    print("  nombre, asi que esta lista no es una sugerencia: es el limite.")
    print("  " + "-" * 70)
    for tool in tools:
        funcion = tool["function"]
        print(f"    {funcion['name']}{_firma(funcion)}")
        parrafo(funcion["description"], ancho=70, sangria="        ")
        print()
    parrafo("NO PUEDE " + datos["no_puede"], sangria="  ")

    print("\n  EL FORMATO DE SALIDA QUE SE LE PIDE")
    print("  " + "-" * 70)
    parrafo(f'"{datos["formato"]}"')
    print("\n    Nada lo obliga a obedecerlo: es una peticion en texto, no un")
    print("    contrato. Cuenta las lineas de la respuesta y comparalas.")

    print("\n  LOS GUARDRAILS DEL BUCLE")
    print("  " + "-" * 70)
    tope = datos.get("vueltas", MAX_VUELTAS)
    print(f"    tope de vueltas     {tope}; despues devuelve 'se quedo sin vueltas'")
    print("    whitelist           si pide una tool que no esta arriba, le")
    print("                        vuelve un error con la lista de las validas")
    print("    anti-repeticion     si repite una llamada identica, le vuelve un")
    print("                        error en vez del mismo resultado otra vez")
    print("    args invalidos      un TypeError vuelve como error al modelo;")
    print("                        no tumba el bucle")

    print("\n  UNA PETICION TIPICA")
    print("  " + "-" * 70)
    parrafo(f'"{datos["peticion"]}"')

    if crudo:
        print("\n  LO QUE DE VERDAD VIAJA EN EL REQUEST, tal cual")
        print("  " + "-" * 70)
        print(textwrap.indent(json.dumps(tools, indent=2, ensure_ascii=False),
                              "    "))
    else:
        print(f"\n  ficha('{nombre}', crudo=True) imprime ademas el JSON exacto")
        print("  de las tools, que es lo que el modelo recibe de verdad.")


if __name__ == "__main__":
    lab.limpiar_pizarron()
    orquestador("Encuentra el mejor predictor de PSNR para este dataset de "
                "arquitecturas, y dime si el resultado es solido.")
