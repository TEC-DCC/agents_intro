"""
Tres agentes que consolidan dos fuentes de clientes en una sola.

El reparto sigue la regla del paso 5 — una responsabilidad por agente y las
tools que esa responsabilidad necesita, ni una mas — y aqui coinciden tres
cosas que normalmente no coinciden: la etapa del pipeline, el tipo de decision
y el permiso.

    NORMALIZADOR   bronce -> plata        resuelve lo que la normalizacion
                                          determinista no pudo: iniciales y
                                          abreviaturas.     escribe el borrador
    EMPAREJADOR    plata -> dictamenes    decide si dos registros son la misma
                                          persona.               SOLO LECTURA
    FUSIONADOR     dictamenes -> oro      elige que valor gana y crea el
                                          golden record.        EL DESTRUCTIVO

**Fusionar es irreversible.** Al crear un golden record se destruye la
distincion entre los registros que lo formaron: si eran dos personas, ya no hay
forma de saber que campo era de cual. Por eso el Fusionador es el unico que
pide confirmacion, y por eso en un MDM de verdad los merges dudosos van a una
persona. El guardrail del paso 4 aqui no es un requisito inventado.

El Emparejador ve **un par a la vez**, nunca la lista completa. Eso no es una
optimizacion: es lo que hace que el caso quepa. El contexto real de qwen3.5:9b
en el aula son 4096 tokens, y el modelo no ordena ni barre listas largas — 3 de
3 fallo un ranking de 18 (planeacion/hallazgos.md). Un par son dos renglones.

Sobre el costo: el Emparejador podria recibir la evidencia ya calculada en su
peticion, en vez de pedir `comparar` como tool, y costaria la mitad de llamadas
al modelo. Se deja con la tool porque el bucle agentico es el tema del taller y
hay que verlo. Cuanto cuesta esa decision se mide en el notebook 06, en la demo
del costo escondido: `emparejador` pide la evidencia como tool y
`emparejador_directo` la recibe en su peticion, y ahi se cuentan las dos.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentlib import chat, normalizar_argumentos, ultima_medicion  # noqa: E402

from . import maestro  # noqa: E402

MAX_VUELTAS = 6

# El estado de la corrida -la capa plata, los dictamenes y la capa oro- vive en
# `maestro`, NO aqui. Este archivo no guarda nada entre llamadas.
#
# Es lo que permite recargar los agentes despues de editarlos sin perder la
# corrida: `importlib.reload(agentes)` reejecuta este modulo, y si `PLATA` y
# `DICTAMENES` estuvieran declarados arriba, cada recarga los dejaria vacios.
# Editar el system prompt de un agente y volver a probarlo es la operacion mas
# comun del taller, y no puede costar media hora de corrida.


def _plata():
    """La capa plata viva. Atajo de `maestro.plata_viva()`."""
    return maestro.plata_viva()


def reiniciar():
    """Deja todo como al principio: plata recargada, dictamenes y oro vacios."""
    return maestro.reiniciar()


# ---------------------------------------------------------------------------
# El bucle. Es el mismo de los pasos 2 al 4, con los nombres de los agentes.
# ---------------------------------------------------------------------------
def _bucle(agente, system, herramientas, disponibles, peticion, ver=True,
           max_vueltas=MAX_VUELTAS):
    """
    El bucle agentico: el modelo pide, tu codigo ejecuta, el resultado vuelve.

    Devuelve el texto final del modelo. Con `ver=True` imprime una linea por
    tool ejecutada, que es lo que se proyecta.
    """
    mensajes = [{"role": "system", "content": system},
                {"role": "user", "content": peticion}]
    vistas = []

    for vuelta in range(1, max_vueltas + 1):
        respuesta = chat(mensajes, herramientas=herramientas)
        mensajes.append(respuesta)
        pedidos = respuesta.get("tool_calls") or []

        if not pedidos:
            texto = respuesta.get("content", "")
            if ver:
                print("  [%s] %s" % (agente, texto.replace("\n", "\n      ")))
            return texto

        for pedido in pedidos:
            nom = pedido["function"]["name"]
            args = normalizar_argumentos(pedido)
            firma = (nom, json.dumps(args, sort_keys=True))

            if nom not in disponibles:
                resultado = {"error": "no existe la tool '%s'" % nom,
                             "disponibles": list(disponibles)}
            elif firma in vistas:
                # El mismo pedido dos veces es el bucle infinito del bloque 5.
                # Devolverlo como error -y no como excepcion- le da al modelo
                # la oportunidad de corregirse solo.
                resultado = {"error": "ya pediste exactamente esto; usa lo que "
                                      "ya tienes o toma una decision"}
            else:
                vistas.append(firma)
                try:
                    resultado = disponibles[nom](**args)
                except TypeError as e:
                    resultado = {"error": "argumentos invalidos: %s" % e}
                except ValueError as e:
                    resultado = {"error": str(e)}
                except KeyError as e:
                    # Red de seguridad. Las tools ya validan sus ids, pero una
                    # excepcion que suba de aqui mata la celda del notebook, y
                    # eso no puede pasar por un argumento inventado.
                    resultado = {"error": "no existe la clave %s" % e}

            devuelto = json.dumps(resultado, ensure_ascii=False, default=str)
            if ver:
                print("  [%s] %s(%s) -> %s" % (agente, nom, args, devuelto[:300]))
            mensajes.append({"role": "tool", "content": devuelto})

    return "[%s] se quedo sin vueltas: llego al tope de %d" % (agente, max_vueltas)


# ---------------------------------------------------------------------------
# 1. NORMALIZADOR — bronce a plata. Escribe el borrador, nada mas.
# ---------------------------------------------------------------------------
def _existe(*ids):
    """
    Revisa los ids antes de usarlos. Devuelve un dict de error, o None.

    Existe porque un id inventado llegaba a `plata[id]` y levantaba un
    `KeyError` que **tumbaba el programa**. Medido el 2026-11-16: el bucle solo
    atrapaba `TypeError` y `ValueError`, asi que la excepcion subia hasta la
    celda del notebook y la corrida se moria por un argumento que el modelo se
    invento.

    Es la misma regla del paso 3, aplicada aqui: un argumento malo es
    informacion que se le devuelve al modelo, no una excepcion. Y el mensaje
    dice el formato, porque un error sin el formato correcto solo consigue que
    el modelo invente otra vez.
    """
    plata = _plata()
    faltan = [i for i in ids if i not in plata]
    if not faltan:
        return None
    crm = sorted(i for i in plata if i.startswith("C"))
    fac = sorted(i for i in plata if i.startswith("F"))
    return {"error": "no existe el registro %s" % ", ".join(faltan),
            "formato": "los ids del CRM van de %s a %s y los de facturacion de "
                       "%s a %s" % (crm[0], crm[-1], fac[0], fac[-1])}


def _ver_registro(id):
    """Un registro de plata, como lo dejo la normalizacion determinista."""
    malo = _existe(id)
    if malo:
        return malo
    r = dict(_plata()[id])
    r.pop("dudas", None)
    return r


def _buscar_parecidos(id):
    """
    Los registros que comparten alguna llave de bloqueo con este.

    Existe por los apellidos abreviados: `Pablo Emilio Guerrero S.` solo se
    resuelve mirando el registro con el que empata, donde el apellido esta
    completo. Sin esta tool, el agente no tiene de donde sacarlo y lo inventa.
    """
    malo = _existe(id)
    if malo:
        return malo
    plata = _plata()
    cand = maestro.generar_candidatos(plata)
    vecinos = [b if a == id else a for a, b, _ in cand if id in (a, b)]
    return [{"id": v, "nombre": "%s %s" % (plata[v]["nombres"], plata[v]["apellidos"]),
             "rfc": plata[v]["rfc_raiz"] + plata[v]["rfc_homoclave"]}
            for v in vecinos]


def _corregir_nombre(id, apellidos, nombres):
    """Escribe la correccion en la capa plata. Reversible con `reiniciar()`."""
    malo = _existe(id)
    if malo:
        return malo
    plata = _plata()
    antes = "%s / %s" % (plata[id]["apellidos"], plata[id]["nombres"])
    plata[id]["apellidos"] = apellidos.upper().strip()
    plata[id]["nombres"] = nombres.upper().strip()
    plata[id]["dudas"] = []
    return {"id": id, "antes": antes, "ahora": "%s / %s" % (apellidos, nombres)}


TOOLS_NORMALIZADOR = [
    {"type": "function", "function": {
        "name": "ver_registro",
        "description": "Un registro tal como quedo despues de la normalizacion "
                       "automatica.",
        "parameters": {"type": "object",
                       "properties": {"id": {"type": "string"}},
                       "required": ["id"]}}},
    {"type": "function", "function": {
        "name": "buscar_parecidos",
        "description": "Otros registros que comparten telefono, correo, RFC o "
                       "apellido con este. Sirve para completar una abreviatura.",
        "parameters": {"type": "object",
                       "properties": {"id": {"type": "string"}},
                       "required": ["id"]}}},
    {"type": "function", "function": {
        "name": "corregir_nombre",
        "description": "Guarda la particion correcta del nombre.",
        "parameters": {"type": "object", "properties": {
            "id": {"type": "string"},
            "apellidos": {"type": "string", "description": "los dos apellidos"},
            "nombres": {"type": "string", "description": "los nombres de pila"}},
            "required": ["id", "apellidos", "nombres"]}}},
]

SYSTEM_NORMALIZADOR = (
    "NUNCA contestes sin haber llamado una tool primero: no conoces estos "
    "registros de memoria y cualquier dato que no venga de una tool es inventado. "
    "Eres un normalizador de nombres mexicanos. Un nombre completo trae DOS "
    "apellidos y uno o dos nombres de pila. "
    "Te llegan registros donde la particion automatica no quedo segura, casi "
    "siempre por una inicial abreviada. "
    "Si la inicial esta entre los nombres de pila, es un segundo nombre y se "
    "deja como esta. Si la inicial esta donde va un apellido, busca el registro "
    "parecido con buscar_parecidos y toma de ahi el apellido completo. "
    "NO inventes un apellido que no viste en ningun registro: si no lo "
    "encuentras, deja la inicial. "
    "Cuando tengas la particion, llama corregir_nombre UNA vez y termina."
)


def normalizador(id, ver=True):
    """Resuelve las dudas de un registro. Devuelve el texto final del modelo."""
    r = _plata()[id]
    peticion = (
        "Registro %s, de la fuente %s.\n"
        "Nombre tal como vino: %r\n"
        "Particion automatica: apellidos=%r nombres=%r\n"
        "Lo que no quedo claro: %s" %
        (id, r["fuente"], r["original"], r["apellidos"], r["nombres"],
         "; ".join(r["dudas"]) or "nada"))
    return _bucle("NORMALIZADOR", SYSTEM_NORMALIZADOR, TOOLS_NORMALIZADOR,
                  {"ver_registro": _ver_registro,
                   "buscar_parecidos": _buscar_parecidos,
                   "corregir_nombre": _corregir_nombre},
                  peticion, ver)


def normalizar_pendientes(ver=True, limite=None):
    """
    Pasa el Normalizador por toda la cola de dudas.

    `limite` corta la corrida para la demo en vivo. Devuelve cuantos atendio.
    """
    cola = maestro.registros_con_dudas(_plata())
    cola = cola[:limite] if limite else cola
    for r in cola:
        if ver:
            print("--- %s  %r" % (r["id"], r["original"]))
        normalizador(r["id"], ver=ver)
    return len(cola)


# ---------------------------------------------------------------------------
# 2. EMPAREJADOR — decide si son la misma persona. No escribe nada.
# ---------------------------------------------------------------------------
def _comparar(id_a, id_b):
    """La evidencia del par. No trae veredicto: ese es el trabajo del agente."""
    return _existe(id_a, id_b) or maestro.comparar(id_a, id_b, _plata())


def _dictaminar(id_a, id_b, veredicto, razon):
    """
    Registra la decision del Emparejador.

    `veredicto` es una de tres: `misma_persona`, `personas_distintas` o
    `no_se`. La tercera existe a proposito: un sistema que nunca puede dudar
    fusiona de mas, y fusionar de mas es el error que no se deshace.
    """
    malo = _existe(id_a, id_b)
    if malo:
        return malo
    validos = ("misma_persona", "personas_distintas", "no_se")
    if veredicto not in validos:
        return {"error": "veredicto invalido: %r" % veredicto,
                "validos": list(validos)}
    maestro.DICTAMENES.append({"a": id_a, "b": id_b, "veredicto": veredicto,
                               "razon": razon})
    return {"registrado": True, "a": id_a, "b": id_b, "veredicto": veredicto}


TOOLS_EMPAREJADOR = [
    {"type": "function", "function": {
        "name": "comparar",
        "description": "La evidencia campo por campo de un par de registros: "
                       "que coincide y que no.",
        "parameters": {"type": "object", "properties": {
            "id_a": {"type": "string"}, "id_b": {"type": "string"}},
            "required": ["id_a", "id_b"]}}},
    {"type": "function", "function": {
        "name": "dictaminar",
        "description": "Registra tu decision sobre el par.",
        "parameters": {"type": "object", "properties": {
            "id_a": {"type": "string"}, "id_b": {"type": "string"},
            "veredicto": {"type": "string",
                          "enum": ["misma_persona", "personas_distintas", "no_se"]},
            "razon": {"type": "string", "description": "una linea, en espanol"}},
            "required": ["id_a", "id_b", "veredicto", "razon"]}}},
]

SYSTEM_EMPAREJADOR = (
    "NUNCA dictamines sin haber llamado comparar primero: no conoces estos "
    "registros de memoria. "
    "Decides si dos registros de cliente son la MISMA persona o DOS personas "
    "distintas. Trabajas con clientes mexicanos. "
    "Reglas que no se negocian:\n"
    "1. El RFC de una persona fisica son 13 caracteres: 10 de raiz mas 3 de "
    "homoclave. La raiz sale de las iniciales y la fecha de nacimiento, asi que "
    "DOS PERSONAS DISTINTAS PUEDEN TENER LA MISMA RAIZ. Si las raices coinciden "
    "y las homoclaves DIFIEREN, son personas distintas: la homoclave existe "
    "justamente para separarlas. Pero una homoclave AUSENTE no es una homoclave "
    "distinta: cuando un registro no la trae, el RFC no descarta nada y tienes "
    "que decidir con el resto de la evidencia.\n"
    "2. Un telefono o un correo compartido NO identifica a una persona: "
    "identifica a una casa o a un negocio. Dos personas con nombres distintos y "
    "el mismo telefono son dos personas.\n"
    "2b. Y al reves tampoco: un telefono o un correo DISTINTO no prueba que sean "
    "personas distintas. La gente cambia de telefono y de correo, y cada sistema "
    "guarda el que tenia cuando lo capturo. Un dato de contacto que no coincide "
    "resta un poco de peso, nunca descarta.\n"
    "3. Mismo nombre no es misma persona. Padre e hijo comparten nombre, "
    "domicilio y telefono, y son dos.\n"
    "4. Si dudas, usa no_se. Fusionar de mas destruye informacion y no se "
    "deshace; dejar un duplicado se corrige despues.\n"
    "Llama comparar, despues dictaminar UNA vez, y termina."
)


def emparejador(id_a, id_b, ver=True):
    """Dictamina un par. El agente ve este par y nada mas."""
    peticion = ("Decide si %s y %s son la misma persona. "
                "Pide la evidencia con comparar y despues dictamina." % (id_a, id_b))
    return _bucle("EMPAREJADOR", SYSTEM_EMPAREJADOR, TOOLS_EMPAREJADOR,
                  {"comparar": _comparar, "dictaminar": _dictaminar},
                  peticion, ver)


def emparejador_directo(id_a, id_b, ver=True):
    """
    El mismo veredicto, con la evidencia ya puesta en la peticion.

    Es el Emparejador sin la tool `comparar`: el programa llama a
    `maestro.comparar()` antes y le pega el resultado al prompt. El agente
    conserva `dictaminar`, asi que sigue habiendo bucle, pero una vuelta menos.

    Existe para medir el costo del bucle, que es la demo 5 del bloque 5. La
    pregunta no es retorica: si los veredictos salen iguales, pedir la evidencia
    como tool cuesta llamadas y no compra nada. Y si salen distintos, tambien
    hay algo que decir.
    """
    ev = _comparar(id_a, id_b)
    if "error" in ev:
        return ev["error"]
    def _lista(claves):
        return "\n".join("  - " + x for x in claves) or "  - nada"

    peticion = "\n".join([
        "Decide si %s y %s son la misma persona." % (id_a, id_b),
        "Esta es toda la evidencia, ya calculada:",
        "",
        "  " + ev["resumen_a"],
        "  " + ev["resumen_b"],
        "",
        "A favor:",
        _lista(ev["senales_a_favor"]),
        "",
        "En contra:",
        _lista(ev["senales_en_contra"]),
        "",
        "Lo que no se sabe:",
        _lista(ev["lo_que_no_se_sabe"]),
        "",
        "Dictamina.",
    ])
    # Solo `dictaminar`: sin `comparar`, porque la evidencia ya viaja arriba.
    tools = [t for t in TOOLS_EMPAREJADOR
             if t["function"]["name"] == "dictaminar"]
    return _bucle("DIRECTO", SYSTEM_EMPAREJADOR, tools,
                  {"dictaminar": _dictaminar}, peticion, ver)


def emparejar_candidatos(ver=True, limite=None):
    """
    Pasa el Emparejador por todos los pares candidatos.

    Devuelve `(atendidos, segundos)`. Con `limite` se corta para la demo: la
    corrida completa son decenas de llamadas al modelo.
    """
    pares = maestro.generar_candidatos(_plata())
    pares = pares[:limite] if limite else pares
    t0 = time.time()
    for a, b, llaves in pares:
        if ver:
            print("--- %s vs %s   (entraron por %s)" % (a, b, ", ".join(llaves)))
        emparejador(a, b, ver=ver)
    return len(pares), round(time.time() - t0, 1)


def dictamenes(veredicto=None):
    """Los dictamenes de la corrida, opcionalmente filtrados."""
    if veredicto is None:
        return list(maestro.DICTAMENES)
    return [d for d in maestro.DICTAMENES if d["veredicto"] == veredicto]


# ---------------------------------------------------------------------------
# 3. FUSIONADOR — el unico destructivo. Pide confirmacion.
# ---------------------------------------------------------------------------
def confirmar_en_consola(ids, valores):
    """Le pregunta a una persona antes de fusionar. El guardrail del paso 4."""
    print("\n  ATENCION: fusionar es irreversible.")
    print("  Se van a unir en un solo golden record: %s" % ", ".join(ids))
    for i in ids:
        print("     %s  %s" % (i, maestro._resumen(_plata()[i])))
    if valores:
        print("  Valores elegidos: %s" % valores)
    return input("  Fusionar? [s/N] ").strip().lower() in ("s", "si", "y")


def aprobar_todo(ids, valores):
    """Aprueba sin preguntar. Para corridas automaticas y para la demo 4."""
    return True


def rechazar_todo(ids, valores):
    """Niega todo. Sirve para ver el bucle sin tocar los datos."""
    return False


def _hacer_fusionador(confirmar):
    """Arma las tools del Fusionador con la politica de confirmacion dada."""

    def conflictos(ids):
        return _existe(*ids) or maestro.valores_en_conflicto(ids, _plata())

    def fusionar(ids, valores=None):
        malo = _existe(*ids)
        if malo:
            return malo
        if not confirmar(ids, valores or {}):
            return {"cancelado": True,
                    "motivo": "una persona no autorizo la fusion"}
        g = maestro.fusionar(ids, valores, _plata())
        return {"golden": g["id"], "origen": g["origen"],
                "nombre": "%s %s" % (g["nombres"], g["apellidos"])}

    return {"valores_en_conflicto": conflictos, "fusionar": fusionar}


TOOLS_FUSIONADOR = [
    {"type": "function", "function": {
        "name": "valores_en_conflicto",
        "description": "En que campos no coinciden los registros de un grupo.",
        "parameters": {"type": "object", "properties": {
            "ids": {"type": "array", "items": {"type": "string"}}},
            "required": ["ids"]}}},
    {"type": "function", "function": {
        "name": "fusionar",
        "description": "DESTRUCTIVA E IRREVERSIBLE. Crea el golden record.",
        "parameters": {"type": "object", "properties": {
            "ids": {"type": "array", "items": {"type": "string"}},
            "valores": {"type": "object",
                        "description": "campo -> valor que gana"}},
            "required": ["ids"]}}},
]

SYSTEM_FUSIONADOR = (
    "Creas el registro unico de un cliente a partir de registros que ya se "
    "confirmo que son la misma persona. "
    "Primero pide valores_en_conflicto para ver en que campos no coinciden. "
    "Despues elige, campo por campo, el valor que sobrevive, con este criterio: "
    "gana el dato mas completo y mas reciente; un RFC de 13 caracteres le gana "
    "a uno de 10; un nombre completo le gana a uno con iniciales; "
    "un correo corporativo y uno personal son los dos validos, y se queda el del "
    "registro mas reciente. "
    "Los campos se llaman exactamente asi, y no hay otros: apellidos, nombres, "
    "rfc_raiz, rfc_homoclave, correo, telefono, lugar. Fijate en que 'nombres' y "
    "'apellidos' van en plural. "
    "Despues llama fusionar UNA vez con los ids y los valores elegidos. "
    "Fusionar es irreversible: si los registros no te parecen la misma persona, "
    "NO fusiones y dilo."
)


def fusionador(ids, ver=True, confirmar=aprobar_todo):
    """
    Crea el golden record de un grupo ya confirmado.

    `confirmar` es el guardrail: `confirmar_en_consola` pregunta,
    `aprobar_todo` no. Apagarlo es la demo de falla 4 del bloque 5.
    """
    peticion = ("Estos registros son la misma persona: %s. "
                "Arma el registro unico." % ", ".join(ids))
    return _bucle("FUSIONADOR", SYSTEM_FUSIONADOR, TOOLS_FUSIONADOR,
                  _hacer_fusionador(confirmar), peticion, ver)
