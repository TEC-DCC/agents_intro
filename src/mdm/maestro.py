"""
El motor de datos maestros: las funciones que los agentes pueden ejecutar.

Es el equivalente de `nas_agente/laboratorio.py` para este caso. Python comun y
corriente: los agentes no saben nada de lo que hay aqui adentro, solo lo
llaman.

El reparto de este archivo es la leccion del bloque 4, y esta puesto a
proposito:

    LO DETERMINISTA VIVE AQUI     normalizar, agrupar en candidatos, comparar
                                  campo por campo, fusionar, calificar.
    EL JUICIO NO ESTA AQUI        decidir si dos registros son la misma
                                  persona, y que valor gana cuando se
                                  contradicen.

`comparar()` es el centro de ese reparto. Devuelve EVIDENCIA, no un veredicto:
dice que el RFC coincide y que el telefono no, y se calla sobre que significa
eso. El veredicto lo da el agente. Si esta funcion devolviera "son la misma
persona", el agente sobraria y el bloque 4 no tendria nada que ensenar.

Medido en planeacion/hallazgos.md: el modelo no calcula y no ordena listas
largas. Comparar 85 registros contra 85 son 3570 pares, y ninguno de esos pares
se le manda al modelo. `generar_candidatos()` los baja a las decenas con reglas
duras, y el modelo ve un par a la vez.
"""

import csv
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

DIR = Path(__file__).resolve().parent / "datos"

# Cada fuente trae sus propias columnas y su propio orden de nombre. El cruce
# es un diccionario, no un agente: saber que `razon_social` de facturacion es
# lo mismo que `nombre` del CRM no requiere juicio, requiere leer el esquema.
FUENTES = {
    "crm": {
        "archivo": "bronce_crm.csv",
        "columnas": {"nombre": "nombre", "correo": "correo",
                     "telefono": "telefono", "rfc": "rfc",
                     "lugar": "ciudad", "alta": "alta"},
        "orden_nombre": "nombres_primero",
    },
    "facturacion": {
        "archivo": "bronce_facturacion.csv",
        "columnas": {"nombre": "razon_social", "correo": "email",
                     "telefono": "tel", "rfc": "rfc",
                     "lugar": "estado", "alta": "registro"},
        "orden_nombre": "apellidos_primero",
    },
}

# Particulas que pertenecen al apellido o al nombre que siguen, y no cuentan
# como palabra aparte al partir "APELLIDO APELLIDO NOMBRE".
PARTICULAS = {"DE", "DEL", "LA", "LAS", "LOS", "Y", "SAN", "SANTA"}

# Las abreviaturas que aparecen en estos datos y que SI se pueden resolver sin
# juicio, porque solo tienen una lectura en espanol de Mexico.
ABREVIATURAS = {"MA": "MARIA", "GPE": "GUADALUPE", "FCO": "FRANCISCO",
                "JO": "JOSE", "ANT": "ANTONIO", "RBTO": "ROBERTO"}


# ---------------------------------------------------------------------------
# Normalizacion: bronce -> plata
# ---------------------------------------------------------------------------
def _sin_acentos(texto):
    """`Hernández` se vuelve `Hernandez`. Sin esto las dos fuentes no empatan."""
    plano = unicodedata.normalize("NFD", texto)
    return "".join(c for c in plano if unicodedata.category(c) != "Mn")


def normalizar_telefono(crudo):
    """
    Los ultimos 10 digitos, sin nada mas.

    `+52 55 2345 6789`, `55 2345 6789` y `5523456789` son el mismo telefono.
    Quedarse con los ultimos 10 tira la lada internacional sin tener que
    razonar sobre ella.
    """
    digitos = re.sub(r"\D", "", crudo or "")
    return digitos[-10:] if len(digitos) >= 10 else ""


def normalizar_correo(crudo):
    """Minusculas y sin espacios. Un correo no distingue mayusculas."""
    return (crudo or "").strip().lower()


def partir_rfc(crudo):
    """
    Devuelve `(raiz, homoclave)`. La raiz son 10 caracteres; la homoclave 3.

    **Esta funcion es la razon de ser del caso.** La raiz se arma con las
    iniciales del nombre y la fecha de nacimiento, asi que dos personas
    distintas pueden compartirla — para eso existe la homoclave. Una raiz
    repetida es un candidato fuerte y nunca una prueba.
    """
    limpio = re.sub(r"[^A-Z0-9]", "", (crudo or "").upper())
    if len(limpio) < 10:
        return "", ""
    return limpio[:10], limpio[10:13]


def partir_nombre(crudo, orden):
    """
    Parte un nombre en apellidos y nombres, y dice de que no esta seguro.

    Devuelve `(apellidos, nombres, dudas)`. `dudas` es una lista de cadenas; si
    viene vacia, la particion es confiable y ningun agente tiene que mirarla.

    El orden lo da la fuente, no el texto: el CRM escribe `Ana Cristina Garcia
    Lopez` y facturacion escribe `GARCIA LOPEZ ANA CRISTINA`. Eso es
    determinista.

    Lo que **no** es determinista, y por eso se reporta como duda:

    - una inicial suelta (`Ana C. Garcia Lopez`), que puede ser un segundo
      nombre o un apellido abreviado;
    - una abreviatura que no esta en el diccionario (`Pablo Emilio Guerrero S.`);
    - menos de tres palabras, donde no se sabe si falta un apellido;
    - una particula (`de`, `del`, `la`) que puede mover el corte entre
      apellidos y nombres.
    """
    texto = _sin_acentos((crudo or "").upper()).replace(".", " ")
    partes = [ABREVIATURAS.get(p, p) for p in texto.split() if p]
    dudas = []

    iniciales = [p for p in partes if len(p) == 1]
    if iniciales:
        dudas.append("hay iniciales sueltas: " + ", ".join(iniciales))
    if len(partes) < 3:
        dudas.append("solo trae %d palabras; puede faltar un apellido" % len(partes))

    # Las particulas se pegan a la palabra que sigue, para que "DE JESUS"
    # cuente como una sola pieza al partir.
    piezas, acumulado = [], []
    for p in partes:
        acumulado.append(p)
        if p not in PARTICULAS:
            piezas.append(" ".join(acumulado))
            acumulado = []
    if acumulado:
        piezas.append(" ".join(acumulado))
    if any(" " in pieza for pieza in piezas):
        dudas.append("hay particulas (de, del, la) y el corte puede moverse")

    if len(piezas) < 2:
        return " ".join(piezas), "", dudas + ["no se pudo partir"]

    if orden == "apellidos_primero":
        apellidos, nombres = piezas[:2], piezas[2:]
    else:
        apellidos, nombres = piezas[-2:], piezas[:-2]

    if not nombres:
        dudas.append("no quedaron nombres de pila despues de partir")
    return " ".join(apellidos), " ".join(nombres), dudas


def _normalizar_lugar(crudo):
    """
    `CDMX`, `Mexico DF` y `CIUDAD DE MEXICO` son el mismo lugar.

    El diccionario es corto a proposito: solo lo que aparece en estas dos
    fuentes. Un catalogo completo de estados no ensena nada sobre agentes.
    """
    t = _sin_acentos((crudo or "").upper()).strip()
    equivalencias = {
        "CDMX": "CIUDAD DE MEXICO", "MEXICO DF": "CIUDAD DE MEXICO",
        "DF": "CIUDAD DE MEXICO", "GDL": "JALISCO",
        "GUADALAJARA": "JALISCO", "MONTERREY": "NUEVO LEON",
        "LEON": "GUANAJUATO", "MERIDA": "YUCATAN",
        "TIJUANA": "BAJA CALIFORNIA", "CANCUN": "QUINTANA ROO",
        "TOLUCA": "MEXICO",
    }
    return equivalencias.get(t, t)


def cargar_bronce():
    """Los 85 registros crudos de las dos fuentes, con su esquema original."""
    salida = []
    for fuente, cfg in FUENTES.items():
        with open(DIR / cfg["archivo"], encoding="utf-8") as f:
            for fila in csv.DictReader(f):
                salida.append({"fuente": fuente, **fila})
    return salida


def normalizar(registro):
    """
    Un registro de bronce a plata. Devuelve el registro con campos parejos.

    El campo `dudas` es el que importa para el reparto del bloque 4: lo que
    esta funcion no pudo resolver sin juicio queda anotado ahi, y es lo unico
    que tiene sentido mandarle a un agente.
    """
    cfg = FUENTES[registro["fuente"]]
    col = cfg["columnas"]
    raiz, homoclave = partir_rfc(registro[col["rfc"]])
    apellidos, nombres, dudas = partir_nombre(registro[col["nombre"]],
                                              cfg["orden_nombre"])
    # El estado del RFC NO es una duda: es una propiedad conocida de la fuente
    # -el CRM captura la raiz de 10 y facturacion los 13 completos- y no hay
    # nada que un agente pueda decidir al respecto. Meterlo en `dudas` inflaba
    # la cola del Normalizador de 11 registros a 45 sin una sola decision
    # adentro. `comparar()` ya lo reporta donde si importa.
    estado_rfc = "completo" if homoclave else ("sin_homoclave" if raiz else "ausente")
    return {
        "id": registro["id"],
        "fuente": registro["fuente"],
        "apellidos": apellidos,
        "nombres": nombres,
        "rfc_raiz": raiz,
        "rfc_homoclave": homoclave,
        "rfc_estado": estado_rfc,
        "correo": normalizar_correo(registro[col["correo"]]),
        "telefono": normalizar_telefono(registro[col["telefono"]]),
        "lugar": _normalizar_lugar(registro[col["lugar"]]),
        "alta": registro[col["alta"]],
        "dudas": dudas,
        "original": registro[col["nombre"]],
    }


def capa_plata():
    """
    Los 85 registros normalizados, indexados por id. **Recien salidos del CSV.**

    Cada llamada construye una capa nueva, sin las correcciones que haya hecho
    el Normalizador. La que conserva el trabajo de la corrida es `plata_viva()`.
    """
    return {r["id"]: r for r in (normalizar(b) for b in cargar_bronce())}


# ---------------------------------------------------------------------------
# El estado vivo de una corrida
#
# Vive AQUI y no en `agentes.py`, y es una decision, no un accidente.
# `importlib.reload` reejecuta el modulo entero: una variable de modulo en
# `agentes` se vacia cada vez que alguien recarga los agentes despues de
# editarlos, que es justo lo que hay que hacer durante el taller. Con el estado
# de este lado, recargar `agentes` no cuesta nada.
#
# Es el mismo reparto que `nas_agente`, donde el pizarron vive en
# `laboratorio` y no en los agentes.
# ---------------------------------------------------------------------------
PLATA = {}
DICTAMENES = []
_ORO = {}


def plata_viva():
    """
    La capa plata de la corrida. Se carga la primera vez que alguien la pide.

    Es la viva, no una copia: lo que el Normalizador corrige queda aqui y lo ve
    todo lo que sigue. Es tambien lo que usan por omision las funciones que
    reciben `plata=None`.
    """
    if not PLATA:
        PLATA.update(capa_plata())
    return PLATA


def reiniciar():
    """
    Deja la corrida como al principio: plata recargada, dictamenes y oro vacios.

    Para borrar **solo** la capa oro y conservar los dictamenes, que es lo que
    hace falta al recalcular los golden records, usa `reiniciar_oro()`.
    """
    PLATA.clear()
    DICTAMENES.clear()
    return reiniciar_oro()


def reiniciar_oro():
    """Borra solo la capa oro. Devuelve cuantos golden records borro."""
    cuantos = len(_ORO)
    _ORO.clear()
    return cuantos


def registros_con_dudas(plata=None):
    """
    Los registros que la normalizacion no pudo resolver sola.

    Es la cola de trabajo del agente Normalizador. Si sale vacia, ese agente no
    hace falta, y el notebook lo dice con el numero en la mano.
    """
    plata = plata if plata is not None else plata_viva()
    return [r for r in plata.values() if r["dudas"]]


# ---------------------------------------------------------------------------
# Agrupar en candidatos: plata -> pares
# ---------------------------------------------------------------------------
def _llaves(r):
    """
    Las llaves de bloqueo de un registro. Dos registros son candidatos si
    comparten aunque sea una.

    Cuatro llaves, y cada una atrapa un caso que las otras no:

        rfc     el camino directo, cuando los dos traen RFC.
        tel     cuando el RFC falta de un lado.
        mail    cuando ademas el telefono cambio.
        nom     cuando no hay ningun identificador en comun.

    La ultima es la que salva los pares dificiles y la que mete ruido. Las dos
    cosas van juntas: una llave que no trae falsos candidatos tampoco trae los
    verdaderos dificiles.
    """
    llaves = set()
    if r["rfc_raiz"]:
        llaves.add("rfc:" + r["rfc_raiz"])
    if r["telefono"]:
        llaves.add("tel:" + r["telefono"])
    if r["correo"]:
        llaves.add("mail:" + r["correo"])
    if r["apellidos"]:
        primero = r["apellidos"].split()[0]
        inicial = r["nombres"][:1] if r["nombres"] else ""
        llaves.add("nom:%s|%s" % (primero, inicial))
    return llaves


def generar_candidatos(plata=None):
    """
    Los pares que vale la pena mirar, y por que llave entraron.

    Devuelve una lista de `(id_a, id_b, [llaves que comparten])`, ordenada, sin
    repetir y sin pares de un registro consigo mismo.

    **Aqui es donde el caso cabe en la ventana de contexto.** Comparar todos
    contra todos son miles de pares; esto los baja a decenas, y el modelo ve un
    par a la vez. El contexto real de qwen3.5:9b en el aula son 4096 tokens
    (planeacion/hallazgos.md).

    Incluye pares de la MISMA fuente: un sistema tambien se duplica solo.
    """
    plata = plata if plata is not None else plata_viva()
    indice = {}
    for r in plata.values():
        for llave in _llaves(r):
            indice.setdefault(llave, []).append(r["id"])

    pares = {}
    for llave, ids in indice.items():
        if len(ids) < 2:
            continue
        ordenados = sorted(ids)
        for i, a in enumerate(ordenados):
            for b in ordenados[i + 1:]:
                pares.setdefault((a, b), []).append(llave)
    return [(a, b, sorted(ll)) for (a, b), ll in sorted(pares.items())]


# ---------------------------------------------------------------------------
# Comparar: la evidencia, no el veredicto
# ---------------------------------------------------------------------------
def _similitud(a, b):
    """De 0.0 a 1.0. `SANCHEZ` contra `SANCHES` da 0.857."""
    if not a or not b:
        return 0.0
    return round(SequenceMatcher(None, a, b).ratio(), 3)


def _compatibles_por_inicial(a, b):
    """
    `ANA C` contra `ANA CRISTINA` es compatible. `ANA C` contra `ANA LUCIA`, no.

    Una inicial no confirma nada, pero descarta bastante, y descartar es lo que
    sirve para no fusionar de mas.
    """
    ta, tb = a.split(), b.split()
    if not ta or not tb:
        return False
    for pa, pb in zip(ta, tb):
        if len(pa) == 1 or len(pb) == 1:
            if pa[0] != pb[0]:
                return False
        elif pa != pb:
            return False
    return True


def _rareza(plata, r):
    """
    En cuantos registros del acervo aparece este nombre. Es una CUENTA, no una
    opinion.

    Existe por una falla medida el 2026-11-16. El Emparejador fallaba los dos
    pares donde el telefono y el correo cambiaron entre sistemas -C007/F007 y
    C016/F016-: decia "personas distintas" porque los datos de contacto no
    coincidian. Agregar una regla al system prompt no lo arreglo. Lo que faltaba
    no era una instruccion, era un dato: que "TORRES MENDOZA CLAUDIA" aparezca
    en 2 registros de 85 es evidencia fuerte, y que "MENDOZA LARA JOSE ANTONIO"
    tambien aparezca en 2 no lo es, porque ahi el RFC separa.

    Es el mismo patron que la calculadora del notebook 02 y que `lab.ranking()`
    del 07: el modelo no cuenta ocurrencias en una lista de 85, y pedirle en el
    prompt que lo haga bien no cambia que no pueda.
    """
    ap = sum(1 for x in plata.values() if x["apellidos"] == r["apellidos"])
    primero = r["nombres"].split()[0] if r["nombres"] else ""
    completo = sum(1 for x in plata.values()
                   if x["apellidos"] == r["apellidos"]
                   and x["nombres"].split()[:1] == [primero])
    return ap, completo


def comparar(id_a, id_b, plata=None):
    """
    La evidencia campo por campo de un par. **No dice si son la misma persona.**

    Ese silencio es deliberado. Si esta funcion devolviera un veredicto, el
    agente no tendria nada que decidir. Lo que hace es poner la evidencia sobre
    la mesa, incluida la que se contradice.

    Devuelve un dict con `senales_a_favor` y `senales_en_contra` en texto
    corto, que es lo que viaja al modelo.
    """
    plata = plata if plata is not None else plata_viva()
    a, b = plata[id_a], plata[id_b]
    a_favor, en_contra, no_se_sabe = [], [], []

    if a["rfc_raiz"] and b["rfc_raiz"]:
        if a["rfc_raiz"] == b["rfc_raiz"]:
            a_favor.append("la raiz del RFC es la misma: " + a["rfc_raiz"])
            if a["rfc_homoclave"] and b["rfc_homoclave"]:
                if a["rfc_homoclave"] == b["rfc_homoclave"]:
                    a_favor.append("la homoclave tambien coincide: "
                                   "el RFC completo es identico")
                else:
                    en_contra.append(
                        "la homoclave DIFIERE: %s contra %s; con la misma raiz, "
                        "eso significa dos personas distintas"
                        % (a["rfc_homoclave"], b["rfc_homoclave"]))
            else:
                # Va en "no se sabe", NO en "en contra". La ausencia de un dato
                # no es evidencia contra la identidad, y medido el 2026-11-16
                # ponerla entre las senales en contra alcanzaba para que el
                # Emparejador separara a una persona de si misma.
                quien = id_a if not a["rfc_homoclave"] else id_b
                no_se_sabe.append(
                    "la raiz del RFC coincide, pero %s no trae homoclave: por el "
                    "RFC no se puede ni confirmar ni descartar" % quien)
        else:
            en_contra.append("la raiz del RFC difiere: %s contra %s"
                             % (a["rfc_raiz"], b["rfc_raiz"]))
    else:
        sin_rfc = [i for i, r in ((id_a, a), (id_b, b)) if not r["rfc_raiz"]]
        no_se_sabe.append("no hay RFC en %s: por el RFC no se puede comparar"
                          % " ni en ".join(sin_rfc))

    sim_ap = _similitud(a["apellidos"], b["apellidos"])
    if a["apellidos"] == b["apellidos"]:
        a_favor.append("los apellidos son identicos: " + a["apellidos"])
    elif sim_ap >= 0.85:
        a_favor.append("los apellidos casi coinciden (%s): %s contra %s"
                       % (sim_ap, a["apellidos"], b["apellidos"]))
    else:
        en_contra.append("los apellidos no coinciden (%s): %s contra %s"
                         % (sim_ap, a["apellidos"], b["apellidos"]))

    sim_no = _similitud(a["nombres"], b["nombres"])
    if a["nombres"] == b["nombres"]:
        a_favor.append("los nombres de pila son identicos: " + a["nombres"])
    elif _compatibles_por_inicial(a["nombres"], b["nombres"]):
        a_favor.append("los nombres de pila son compatibles: %s contra %s"
                       % (a["nombres"], b["nombres"]))
    else:
        en_contra.append("los nombres de pila no coinciden (%s): %s contra %s"
                         % (sim_no, a["nombres"], b["nombres"]))

    if a["telefono"] and b["telefono"]:
        if a["telefono"] == b["telefono"]:
            a_favor.append("el telefono es el mismo: " + a["telefono"])
        else:
            en_contra.append("el telefono difiere: %s contra %s"
                             % (a["telefono"], b["telefono"]))
    if a["correo"] and b["correo"]:
        if a["correo"] == b["correo"]:
            a_favor.append("el correo es el mismo: " + a["correo"])
        else:
            en_contra.append("el correo difiere: %s contra %s"
                             % (a["correo"], b["correo"]))
    if a["lugar"] and b["lugar"]:
        if a["lugar"] == b["lugar"]:
            a_favor.append("el lugar coincide: " + a["lugar"])
        else:
            en_contra.append("el lugar difiere: %s contra %s"
                             % (a["lugar"], b["lugar"]))
    if a["fuente"] == b["fuente"]:
        a_favor.append("los dos vienen de %s: seria un duplicado interno"
                       % a["fuente"])

    # La rareza del nombre, contada sobre los 85 registros. Solo se reporta
    # cuando los apellidos empatan, porque es ahi donde cambia la lectura.
    if a["apellidos"] == b["apellidos"]:
        _, cuantos = _rareza(plata, a)
        total = len(plata)
        if cuantos <= 2:
            a_favor.append(
                "el nombre '%s %s' aparece en %d registros de %d: es raro, y un "
                "nombre raro que empata exacto pesa mas que un dato de contacto "
                "que cambio" % (a["nombres"].split()[0] if a["nombres"] else "",
                                a["apellidos"], cuantos, total))
        else:
            en_contra.append(
                "el nombre '%s %s' aparece en %d registros de %d: no es raro, "
                "asi que empatar por nombre no dice mucho"
                % (a["nombres"].split()[0] if a["nombres"] else "",
                   a["apellidos"], cuantos, total))

    return {
        "a": id_a,
        "b": id_b,
        "resumen_a": _resumen(a),
        "resumen_b": _resumen(b),
        "senales_a_favor": a_favor,
        "senales_en_contra": en_contra,
        "lo_que_no_se_sabe": no_se_sabe,
    }


def _resumen(r):
    """
    Un registro en una linea. Es lo que ve el modelo, y paga tokens.

    El RFC incompleto se escribe `GALA920621 (sin homoclave)` y NO con un
    relleno tipo `???`. Medido el 2026-11-16: con el relleno, el Emparejador
    leyo `???` como una homoclave distinta de `K37` y dictamino "personas
    distintas" sobre un par que si era la misma persona, citando ese `???`
    como prueba. Un dato ausente que se imprime como si estuviera presente no
    es un detalle de formato: cambia el veredicto.
    """
    if r["rfc_estado"] == "completo":
        rfc = r["rfc_raiz"] + r["rfc_homoclave"]
    elif r["rfc_estado"] == "sin_homoclave":
        rfc = r["rfc_raiz"] + " (sin homoclave)"
    else:
        rfc = "(sin RFC)"
    return "%s %s | %s | %s | %s | %s" % (
        r["nombres"], r["apellidos"], rfc,
        r["correo"], r["telefono"], r["lugar"])


# ---------------------------------------------------------------------------
# Fusionar: plata -> oro
#
# Esta es la parte destructiva, y es la unica del archivo que lo es. Fusionar
# dos registros destruye la distincion entre ellos: si eran dos personas, ya no
# hay forma de saber cual campo era de cual. En un MDM de verdad, deshacer un
# merge es el problema caro, y por eso los merges dudosos van a una persona.
# ---------------------------------------------------------------------------
CAMPOS_ORO = ("apellidos", "nombres", "rfc_raiz", "rfc_homoclave",
              "correo", "telefono", "lugar")

# `_ORO` y las dos funciones que lo reinician estan arriba, con el resto del
# estado vivo de la corrida.


def valores_en_conflicto(ids, plata=None):
    """
    En que campos no se ponen de acuerdo los registros de un grupo.

    Devuelve `{campo: {valor: [ids que lo traen]}}` solo con los campos donde
    hay mas de un valor. Igual que `comparar()`, es evidencia y no decision:
    dice que un registro trae un correo y el otro trae otro, y no opina sobre
    cual sobrevive.

    Elegir cual gana es *survivorship*, y ahi si hay juicio: el mas reciente no
    siempre es el bueno, y el mas completo tampoco.
    """
    plata = plata if plata is not None else plata_viva()
    conflicto = {}
    for campo in CAMPOS_ORO:
        por_valor = {}
        for i in ids:
            valor = plata[i][campo]
            if valor:
                por_valor.setdefault(valor, []).append(i)
        if len(por_valor) > 1:
            conflicto[campo] = por_valor
    return conflicto


def fusionar(ids, valores=None, plata=None):
    """
    Crea un golden record a partir de varios registros. **Es destructiva.**

        ids       los registros que son la misma persona.
        valores   que valor gana en cada campo. Lo que no venga aqui se toma
                  del registro mas completo del grupo.

    Devuelve el golden record. Falla si algun id ya quedo fusionado en otro
    golden record, porque eso significa que dos decisiones se contradicen y
    taparlo en silencio es peor que detenerse.
    """
    plata = plata if plata is not None else plata_viva()
    ids = sorted(set(ids))
    if not ids:
        raise ValueError("fusionar necesita al menos un registro")
    for golden in _ORO.values():
        repetidos = set(ids) & set(golden["origen"])
        if repetidos:
            raise ValueError(
                "%s ya esta en el golden record %s. Un registro pertenece a una "
                "sola persona." % (", ".join(sorted(repetidos)), golden["id"]))

    # El registro "mas completo" es el que trae menos campos vacios. Es un
    # criterio determinista y discutible, y por eso es solo el valor por
    # omision: el agente puede pisarlo campo por campo.
    # Un campo que no existe se RECHAZA con su lista de validos, no se ignora.
    # Medido el 2026-11-16: el Fusionador mando valores={'nombre': 'ANA
    # CRISTINA'} -el campo se llama 'nombres', en plural- y la version que
    # filtraba en silencio lo tiro y devolvio un golden record con el nombre
    # viejo. El modelo noto la contradiccion en su respuesta y no pudo hacer
    # nada, porque nadie le dijo que el campo no existia.
    desconocidos = sorted(set(valores or {}) - set(CAMPOS_ORO))
    if desconocidos:
        raise ValueError(
            "estos campos no existen: %s. Los validos son: %s"
            % (", ".join(desconocidos), ", ".join(CAMPOS_ORO)))

    base = max(ids, key=lambda i: sum(1 for c in CAMPOS_ORO if plata[i][c]))
    golden = {c: plata[base][c] for c in CAMPOS_ORO}
    golden.update(valores or {})
    golden["id"] = "G%03d" % (len(_ORO) + 1)
    golden["origen"] = ids
    _ORO[golden["id"]] = golden
    return golden


def golden_records():
    """La capa oro tal como va. Un dict por golden record."""
    return list(_ORO.values())


def consolidar_restantes(plata=None):
    """
    Pasa a oro, cada uno solo, los registros que nadie fusiono.

    Un registro que no empato con ninguno **tambien es un golden record**: es
    una persona que aparece una sola vez. Olvidar esto es el error clasico al
    armar un MDM por primera vez, y deja la capa oro con los duplicados
    resueltos y sin los clientes que nunca estuvieron duplicados.
    """
    plata = plata if plata is not None else plata_viva()
    ya = {i for g in _ORO.values() for i in g["origen"]}
    nuevos = 0
    for i in sorted(plata):
        if i not in ya:
            fusionar([i], plata=plata)
            nuevos += 1
    return nuevos


def guardar_oro(ruta=None):
    """Escribe la capa oro a CSV. Devuelve la ruta."""
    ruta = Path(ruta) if ruta else DIR / "oro.csv"
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id"] + list(CAMPOS_ORO) + ["origen"])
        for g in _ORO.values():
            w.writerow([g["id"]] + [g[c] for c in CAMPOS_ORO]
                       + [" ".join(g["origen"])])
    return ruta


# ---------------------------------------------------------------------------
# Calificar: contra la respuesta publicada
# ---------------------------------------------------------------------------
def calificar():
    """
    Compara la capa oro contra `verdad.csv` y devuelve el marcador.

    Existe porque un agente **no se verifica comparando cadenas**: la
    temperatura hace que la misma entrada de salidas distintas. Se verifica por
    su efecto, y aqui el efecto es un numero: cuantos golden records quedaron.

        golden_records     los que produjo la corrida. Lo correcto son 55.
        fusiones_correctas pares que si eran la misma persona.
        fusiones_de_mas    pares que fusiono y eran personas distintas. **Es el
                           error caro**: destruye la distincion y no se deshace.
        pares_perdidos     pares que eran la misma persona y quedaron sueltos.

    `fusiones_de_mas` y `pares_perdidos` no cuestan lo mismo, y el notebook
    tiene que decirlo: un duplicado que sobrevive se arregla despues; dos
    personas fundidas en una, no.
    """
    with open(DIR / "verdad.csv", encoding="utf-8") as f:
        verdad = {r["registro_id"]: r["persona_id"] for r in csv.DictReader(f)}

    de_mas, correctas, agrupados = [], 0, {}
    for g in _ORO.values():
        for i in g["origen"]:
            agrupados[i] = g["id"]
        personas = {verdad[i] for i in g["origen"]}
        if len(personas) > 1:
            de_mas.append({"golden": g["id"], "origen": g["origen"],
                           "personas": sorted(personas)})
        else:
            correctas += len(g["origen"]) - 1

    perdidos = []
    for persona in sorted(set(verdad.values())):
        suyos = sorted(i for i, p in verdad.items() if p == persona)
        grupos = {agrupados.get(i) for i in suyos}
        if len(grupos) > 1:
            perdidos.append({"persona": persona, "registros": suyos})

    return {
        "golden_records": len(_ORO),
        "golden_records_correctos": 55,
        "fusiones_correctas": correctas,
        "fusiones_de_mas": de_mas,
        "pares_perdidos": perdidos,
        "sin_consolidar": sorted(set(verdad) - set(agrupados)),
    }
