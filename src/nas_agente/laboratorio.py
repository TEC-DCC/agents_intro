"""
El laboratorio: las funciones que los agentes pueden ejecutar.

Esto es el equivalente del backend de inventario del paso 3, pero para el caso
NAS. Python comun y corriente: los agentes no tienen nada que ver con lo que
hay aqui adentro, solo lo llaman.

El dataset son 1193 arquitecturas de super-resolucion del espacio BASS, cada
una con su cromosoma de 28 tokens (valores 0-7, codigos Gray de 3 bits) y el
PSNR de validacion medido tras entrenarla 5 epocas en DIV2K.

Generar esos 1193 datos costo ~9500 horas de GPU. Entrenar un predictor sobre
ellos cuesta entre 0.02 y 3 segundos de CPU. Ese desbalance es toda la razon de
ser de los predictores: y tambien lo que hace viable este ejemplo en un taller.

Fuente: Sarmiento-Rosales, Sosa Hernandez y Monroy (2026), "Evolutionary Neural
Architecture Search for Super-Resolution", Swarm and Evolutionary Computation.
github.com/SergioSarmientoRosales/MoNAS-SR-Predictors-Dataset
"""

import ast
import csv
import json
import time
from pathlib import Path

import numpy as np
from sklearn.ensemble import (AdaBoostRegressor, BaggingRegressor,
                              ExtraTreesRegressor, GradientBoostingRegressor,
                              HistGradientBoostingRegressor,
                              RandomForestRegressor)
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, WhiteKernel
from sklearn.linear_model import (BayesianRidge, ElasticNet, HuberRegressor,
                                  Lasso, LinearRegression, Ridge)
from sklearn.model_selection import KFold
from sklearn.neighbors import KNeighborsRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import OneHotEncoder
from sklearn.svm import SVR
from sklearn.tree import DecisionTreeRegressor

# XGBoost es el unico de los once del paper que no viene con scikit-learn, y
# son 100 MB de descarga. Por eso es opcional y NO esta en requirements.txt:
# el taller no lo necesita y la red del aula ya es un riesgo conocido.
#
# Si falta, el nombre no aparece en el catalogo y listar_predictores explica
# como instalarlo. Mejor que el agente no vea el nombre, a que lo pida y
# reciba un error.
try:
    from xgboost import XGBRegressor
    HAY_XGBOOST = True
except ImportError:
    HAY_XGBOOST = False

DATOS = Path(__file__).resolve().parent / "datos" / "1193_P_Trained_models_psnr_result.csv"

# Lo que el paper reporta, para poder calificar al agente (Tabla 3).
PAPER = {
    "extra_trees": {"c_index": 0.6771, "mse": 12.14},
    "svr": {"c_index": 0.6739, "mse": 12.08},
    "xgboost": {"c_index": 0.6737, "mse": 12.73},
    "random_forest": {"c_index": 0.6726, "mse": 12.83},
    "knn": {"c_index": 0.6542, "mse": 14.43},
    "adaboost": {"c_index": 0.5618, "mse": 18.33},
    "linear": {"c_index": 0.5489, "mse": 18.77},
    "ridge": {"c_index": 0.5488, "mse": 18.75},
    "lasso": {"c_index": 0.5485, "mse": 18.62},
    "elasticnet": {"c_index": 0.5483, "mse": 18.58},
    "decision_tree": {"c_index": 0.5357, "mse": 19.60},
}


# ---------------------------------------------------------------------------
# Los datos
# ---------------------------------------------------------------------------
def _cargar():
    """
    El CSV trae TRES campos por fila: el cromosoma y dos PSNR.

        campo 1  cromosoma de 28 tokens      -> X
        campo 2  PSNR de ENTRENAMIENTO       -> Y_ENTRENAMIENTO (no se usa)
        campo 3  PSNR de VALIDACION          -> Y, el objetivo

    Que el objetivo sea el TERCERO no es una suposicion: es lo que hace el
    codigo de los autores, `y = data.iloc[:, -1]` en Codes/Model_based_search.py.

    Que el segundo sea el de entrenamiento SI es una inferencia, y conviene
    saberlo. La evidencia: si el tercero es validacion, al segundo no le queda
    otra cosa que ser; y encaja, porque el PSNR de entrenamiento suele salir
    mayor que el de validacion -aqui +0.50 dB de media- y correlacionan 0.91.

    Lo cargamos aunque no lo usemos, para que `describir_dataset` pueda
    reportarlo. Esta roto: 41 infinitos y 34 ceros contra ninguno del tercero.
    Entrenar contra el daria un resultado que parece bien y esta mal, y por eso
    importa que el agente lo vea en lugar de que alguien lo descarte en
    silencio.
    """
    X, y_val, y_ent = [], [], []
    with open(DATOS, encoding="utf-8", newline="") as f:
        for cromosoma, col2, col3 in csv.reader(f):
            X.append(ast.literal_eval(cromosoma))
            y_ent.append(float(col2))
            y_val.append(float(col3))
    return (np.array(X, dtype=float), np.array(y_val), np.array(y_ent))


X_CRUDO, Y, Y_ENTRENAMIENTO = _cargar()


def vistazo(n=5):
    """
    Las primeras n arquitecturas, legibles.

    X_CRUDO y Y son arreglos de numpy, no DataFrames de pandas: sklearn quiere
    arreglos y no vale la pena cargar pandas solo para mirar. Pero eso
    significa que `.head()` no existe -el equivalente es `X_CRUDO[:3]`- y que
    la salida cruda sale con flotantes y se parte en dos renglones.

    Esto imprime lo mismo en una linea por arquitectura.
    """
    print(f"  {'#':>4}  {'cromosoma (28 tokens)':<60}  {'entren.':>8}  {'valid.':>8}")
    print(f"  {'-'*4}  {'-'*60}  {'-'*8}  {'-'*8}")
    for i in range(min(n, len(Y))):
        tokens = " ".join(f"{int(v)}" for v in X_CRUDO[i])
        ent = Y_ENTRENAMIENTO[i]
        ent_txt = f"{ent:>8.3f}" if np.isfinite(ent) else f"{'inf':>8}"
        print(f"  {i:>4}  {tokens:<60}  {ent_txt}  {Y[i]:>8.3f}")
    print(f"\n  {len(Y)} arquitecturas. La columna OBJETIVO es la de validacion;")
    print(f"  la de entrenamiento se carga pero no se usa, y esta rota "
          f"({int(np.isinf(Y_ENTRENAMIENTO).sum())} infinitos, "
          f"{int((Y_ENTRENAMIENTO == 0).sum())} ceros).")
    print(f"  Los arreglos son numpy: usa [:n], no .head(n).")


def describir_dataset():
    """Forma, rangos, duplicados y salud de la variable objetivo."""
    n, d = X_CRUDO.shape
    unicos = len({tuple(f) for f in X_CRUDO})
    return {
        "arquitecturas": int(n),
        "tokens_por_cromosoma": int(d),
        "valores_por_token": {"min": int(X_CRUDO.min()), "max": int(X_CRUDO.max()),
                              "distintos": int(len(np.unique(X_CRUDO)))},
        "cromosomas_unicos": unicos,
        "cromosomas_repetidos": int(n - unicos),
        "objetivo_psnr": {
            "media": round(float(Y.mean()), 4),
            "desviacion": round(float(Y.std()), 4),
            "min": round(float(Y.min()), 4),
            "max": round(float(Y.max()), 4),
            "sospechosos_bajo_20dB": int((Y < 20).sum()),
        },
        "columna_entrenamiento_descartada": {
            "que_es": ("El CSV trae una segunda columna de PSNR, la de "
                       "entrenamiento. NO se usa como objetivo."),
            "infinitos": int(np.isinf(Y_ENTRENAMIENTO).sum()),
            "ceros": int((Y_ENTRENAMIENTO == 0).sum()),
            "por_debajo_de_20dB": int((Y_ENTRENAMIENTO < 20).sum()),
            "por_que_no_se_usa": ("Esta rota, y el codigo de los autores usa la "
                                  "ultima columna como objetivo."),
        },
        "nota": ("Dos problemas que conviene reportar: (1) los cromosomas "
                 "repetidos son la MISMA arquitectura entrenada otra vez, con "
                 "PSNR distinto, asi que si caen en train y test de la misma "
                 "validacion cruzada la metrica sale optimista; (2) la columna "
                 "de PSNR de entrenamiento tiene infinitos y ceros, y por eso "
                 "se descarta."),
    }


def revisar_correlaciones():
    """Cuanta senal lineal tiene cada token por separado."""
    cors = [abs(float(np.corrcoef(X_CRUDO[:, j], Y)[0, 1])) for j in range(X_CRUDO.shape[1])]
    return {
        "correlacion_absoluta_maxima": round(max(cors), 4),
        "token_mas_correlacionado": int(np.argmax(cors)),
        "correlacion_absoluta_media": round(float(np.mean(cors)), 4),
        "nota": ("Correlacion lineal casi nula. Es lo esperable: los tokens son "
                 "codigos Gray categoricos, no magnitudes. Dice que los modelos "
                 "lineales van a ir mal, no que no haya senal."),
    }


# ---------------------------------------------------------------------------
# Las codificaciones. El paper usa 'entero' y deja las otras como trabajo futuro.
# ---------------------------------------------------------------------------
def _codificar(como):
    if como == "entero":
        # Lo que hace el paper: los Gray codes tal cual, como si fueran numeros.
        return X_CRUDO
    if como == "onehot":
        # 28 tokens x 8 valores = 224 columnas binarias. Sin orden implicito.
        return OneHotEncoder(sparse_output=False).fit_transform(X_CRUDO)
    if como == "binario":
        # Gray -> binario natural, 3 bits por token = 84 columnas.
        g = X_CRUDO.astype(int)
        b = g.copy()
        for _ in range(2):
            b = g ^ (b >> 1)
        bits = ((b[:, :, None] >> np.arange(2, -1, -1)) & 1).reshape(len(g), -1)
        return bits.astype(float)
    raise ValueError(f"codificacion desconocida: {como}. "
                     f"Hay: entero, onehot, binario")


CODIFICACIONES = ("entero", "onehot", "binario")


# ---------------------------------------------------------------------------
# Las metricas
# ---------------------------------------------------------------------------
def c_index(y_real, y_pred):
    """
    Concordance index: de todos los pares de arquitecturas, en que fraccion el
    orden que predice el modelo coincide con el real. 0.5 es azar.

    ES LA METRICA QUE IMPORTA AQUI, y no es obvio. En NAS no interesa acertar
    el PSNR exacto: interesa saber cual arquitectura es mejor que cual, porque
    de eso depende a quien selecciona el algoritmo evolutivo. Un predictor que
    se equivoca 2 dB en todo, pero ordena bien, sirve. Uno que acierta el
    promedio y ordena mal, no.

    El paper selecciona por C-index y usa MSE como complemento. Un agente que
    optimice MSE -lo que hace todo tutorial de regresion- elige otro modelo.
    """
    y_real, y_pred = np.asarray(y_real), np.asarray(y_pred)
    i, j = np.triu_indices(len(y_real), k=1)
    dr, dp = y_real[i] - y_real[j], y_pred[i] - y_pred[j]
    v = dr != 0
    return float((np.sign(dr[v]) == np.sign(dp[v])).mean())


# ---------------------------------------------------------------------------
# Los predictores
# ---------------------------------------------------------------------------
class _Hiper(dict):
    """
    Un dict que se acuerda de que claves le preguntaron.

    Existe por un bug real: `_construir` leia solo las claves que conocia y
    tiraba el resto EN SILENCIO. Si pedias extra_trees con
    min_samples_leaf=2, te devolvia un resultado... del modelo por omision,
    identico, sin avisar. Una tool que acepta un argumento y lo ignora es
    peor que una que lo rechaza: el agente -o tu- concluyes que ese
    hiperparametro no sirve de nada, y nunca se probo.
    """

    def __init__(self, origen):
        super().__init__(origen or {})
        self.preguntadas = set()

    def get(self, clave, *omision):
        self.preguntadas.add(clave)
        return super().get(clave, *omision)

    def ignoradas(self):
        return sorted(set(self) - self.preguntadas)


def _construir(nombre, hiper):
    h = _Hiper(hiper)
    fabricas = {
        # Los parametros son los de la Tabla 2 del paper, para que su rejilla
        # se pueda reproducir tal cual.
        "extra_trees": lambda: ExtraTreesRegressor(
            n_estimators=h.get("n_estimators", 200), max_depth=h.get("max_depth"),
            min_samples_split=h.get("min_samples_split", 2),
            min_samples_leaf=h.get("min_samples_leaf", 1),
            max_features=h.get("max_features", 1.0),
            random_state=0, n_jobs=-1),
        "random_forest": lambda: RandomForestRegressor(
            n_estimators=h.get("n_estimators", 200), max_depth=h.get("max_depth"),
            min_samples_split=h.get("min_samples_split", 2),
            min_samples_leaf=h.get("min_samples_leaf", 1),
            max_features=h.get("max_features", 1.0),
            random_state=0, n_jobs=-1),
        "gradient_boosting": lambda: GradientBoostingRegressor(
            n_estimators=h.get("n_estimators", 200),
            learning_rate=h.get("learning_rate", 0.1),
            max_depth=h.get("max_depth", 3),
            subsample=h.get("subsample", 1.0), random_state=0),
        "adaboost": lambda: AdaBoostRegressor(
            n_estimators=h.get("n_estimators", 200),
            learning_rate=h.get("learning_rate", 0.1), random_state=0),
        "decision_tree": lambda: DecisionTreeRegressor(
            max_depth=h.get("max_depth"),
            min_samples_split=h.get("min_samples_split", 2),
            min_samples_leaf=h.get("min_samples_leaf", 1),
            max_features=h.get("max_features"), random_state=0),
        "svr": lambda: SVR(C=h.get("C", 10.0), gamma=h.get("gamma", "auto"),
                           epsilon=h.get("epsilon", 0.1),
                           kernel=h.get("kernel", "rbf"),
                           degree=h.get("degree", 3),
                           shrinking=h.get("shrinking", True)),
        "knn": lambda: KNeighborsRegressor(n_neighbors=h.get("n_neighbors", 5),
                                           weights=h.get("weights", "uniform"),
                                           p=h.get("p", 2)),
        "linear": lambda: LinearRegression(
            fit_intercept=h.get("fit_intercept", True)),
        "ridge": lambda: Ridge(alpha=h.get("alpha", 1.0),
                               fit_intercept=h.get("fit_intercept", True)),
        "lasso": lambda: Lasso(alpha=h.get("alpha", 0.1),
                               max_iter=h.get("max_iter", 5000)),
        "elasticnet": lambda: ElasticNet(alpha=h.get("alpha", 0.1),
                                         l1_ratio=h.get("l1_ratio", 0.5),
                                         max_iter=h.get("max_iter", 5000)),
        # --- los que el paper no probo -------------------------------------
        "hist_gradient_boosting": lambda: HistGradientBoostingRegressor(
            max_iter=h.get("n_estimators", 200),
            learning_rate=h.get("learning_rate", 0.1), random_state=0),
        "bagging": lambda: BaggingRegressor(
            n_estimators=h.get("n_estimators", 50), random_state=0, n_jobs=-1),
        "bayesian_ridge": BayesianRidge,
        "huber": lambda: HuberRegressor(alpha=h.get("alpha", 0.0001), max_iter=500),
        "mlp": lambda: MLPRegressor(
            hidden_layer_sizes=h.get("hidden_layer_sizes", (128, 64)),
            max_iter=h.get("max_iter", 600), early_stopping=True, random_state=0),
        # normalize_y es obligatorio aqui: el PSNR ronda los 30 dB y un GP
        # centrado en cero predice ~0 para todo. Sin esto da un MSE de 900.
        "gaussian_process": lambda: GaussianProcessRegressor(
            kernel=RBF(length_scale=h.get("length_scale", 1.0)) + WhiteKernel(),
            normalize_y=True, random_state=0),
    }
    if HAY_XGBOOST:
        fabricas["xgboost"] = lambda: XGBRegressor(
            n_estimators=h.get("n_estimators", 200),
            learning_rate=h.get("learning_rate", 0.1),
            max_depth=h.get("max_depth", 6),
            subsample=h.get("subsample", 1.0), random_state=0, n_jobs=-1,
            verbosity=0)
    if nombre not in fabricas:
        raise ValueError(f"predictor desconocido: {nombre}")

    modelo = fabricas[nombre]()

    # Si sobro alguna clave, el modelo que acabamos de construir NO la tiene
    # en cuenta. Avisar en vez de callar: ver el docstring de _Hiper.
    sobrantes = h.ignoradas()
    if sobrantes:
        raise ValueError(
            f"{nombre} no usa {sobrantes}. Los que si acepta son "
            f"{sorted(h.preguntadas)}. No te lo ignoro en silencio porque "
            f"entonces creerias que lo probaste.")
    return modelo


# Los once de la Tabla 3 del paper, en el orden en que los reporta. Tenerlos
# todos es lo que permite calificar al agente contra un resultado publicado.
DEL_PAPER = ("extra_trees", "svr", "xgboost", "random_forest", "knn",
             "adaboost", "linear", "ridge", "lasso", "elasticnet",
             "decision_tree")

# Y siete mas, para que el barrido no termine donde termino el paper. Cada uno
# aporta una familia que alli no esta:
#
#   gradient_boosting       boosting clasico de sklearn
#   hist_gradient_boosting  boosting por histogramas, el pariente de xgboost
#   bagging                 bagging sobre arboles, sin la aleatoriedad extra
#                           de random forest
#   bayesian_ridge          lineal, con la regularizacion estimada de los datos
#   huber                   lineal robusto a valores extremos; viene al caso,
#                           porque el dataset trae 27 PSNR por debajo de 20 dB
#   mlp                     una red neuronal, que es la pregunta que siempre
#                           sale: un predictor neuronal gana? (aqui no)
#   gaussian_process        el surrogate clasico de optimizacion bayesiana
EXTRA = ("gradient_boosting", "hist_gradient_boosting", "bagging",
         "bayesian_ridge", "huber", "mlp", "gaussian_process")

NO_DISPONIBLES = {} if HAY_XGBOOST else {
    "xgboost": "no instalado en este ambiente; se habilita con: pip install xgboost"}

PREDICTORES = tuple(n for n in DEL_PAPER + EXTRA if n not in NO_DISPONIBLES)

# Medidos en esta maquina con 10 folds y codificacion entero. Van en la
# respuesta del catalogo porque el Experimentador es el unico agente que gasta
# CPU, y conviene que sepa de antemano cual le va a costar caro.
LENTOS = {"gaussian_process": "~25 s", "mlp": "~6 s", "bagging": "~4 s"}

# Todo lo evaluado en esta sesion. El Estadistico lo necesita para comparar.
PIZARRON = []


def listar_predictores():
    """
    El catalogo: que se puede evaluar, cuales son del paper y que falta.

    Esta tool existe para que el agente no tenga que adivinar nombres. Y la
    respuesta no es fija: cambia con lo que haya instalado y con lo que ya se
    haya evaluado en esta sesion.

    Por eso la descripcion de `evaluar_predictor` NO enumera los nombres. Las
    enumeraba, y entonces esta tool no se llamaba nunca -medido, 0 veces de 4,
    contra 4 de 4 sin la enumeracion-: el modelo no pide un catalogo que ya
    tiene a la vista en otro esquema.
    """
    evaluados = {e["predictor"] for e in PIZARRON}
    # Sin una clave "predictores" con la lista plana: seria una cuarta copia
    # de los mismos 18 nombres, y el contexto real del modelo son 4096 tokens.
    # del_paper + agregados_por_nosotros ya son el catalogo completo.
    return {"del_paper": [n for n in DEL_PAPER if n in PREDICTORES],
            "agregados_por_nosotros": list(EXTRA),
            "no_disponibles": NO_DISPONIBLES,
            "codificaciones": list(CODIFICACIONES),
            "metrica_principal": "c_index (mayor es mejor)",
            "metrica_secundaria": "mse (menor es mejor)",
            "los_lentos": LENTOS,
            "el_resto_tarda": "menos de 2 segundos",
            "ya_evaluados": [f"{e['predictor']}/{e['codificacion']}" for e in PIZARRON],
            "faltan_por_evaluar": [n for n in PREDICTORES if n not in evaluados]}


def _etiqueta(entrada):
    """
    Como se nombra una evaluacion en el pizarron.

    El sufijo +ajustado no es cosmetico: sin el, la version con
    hiperparametros buscados y la de valores por omision se llaman igual, y en
    la tabla de Friedman aparecerian dos filas con el mismo nombre y numeros
    distintos.
    """
    sufijo = "+ajustado" if entrada.get("hiperparametros") else ""
    return f"{entrada['predictor']}/{entrada['codificacion']}{sufijo}"


def _publico(entrada):
    """Lo que ve el agente: sin las claves internas."""
    return {k: v for k, v in entrada.items() if not k.startswith("_")}


def _normalizar_hiper(hiperparametros):
    """
    Los modelos mandan el objeto como CADENA JSON la mitad de las veces.

    Medido: el Experimentador pidio
        evaluar_predictor(predictor="hist_gradient_boosting",
                          hiperparametros='{"max_iter": 1000, ...}')
    y el error que recibio fue "dictionary update sequence element #0 has
    length 1; 2 is required", que no le dice nada ni a el ni a un humano.
    Aceptar las dos formas cuesta tres lineas y le ahorra una vuelta entera.
    """
    if hiperparametros is None or isinstance(hiperparametros, dict):
        return hiperparametros
    if isinstance(hiperparametros, str):
        try:
            cargado = json.loads(hiperparametros)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"hiperparametros no es JSON valido: {e}. Mandalo como objeto, "
                f"no como texto. O usa buscar_hiperparametros, que prueba la "
                f"rejilla sola.") from e
        if not isinstance(cargado, dict):
            raise ValueError("hiperparametros tiene que ser un objeto con "
                             "pares nombre: valor")
        return cargado
    raise ValueError(f"hiperparametros tiene que ser un objeto, no "
                     f"{type(hiperparametros).__name__}")


def _medir(predictor, codificacion, hiperparametros, folds):
    """
    Una evaluacion, SIN anotarla en el pizarron.

    Esta separacion importa: buscar_hiperparametros prueba decenas de
    configuraciones, y si cada una fuera al pizarron, la prueba de Friedman
    del Estadistico acabaria comparando las 26 variantes de SVR entre si en
    vez de comparar predictores. Al pizarron va solo lo que alguien decidio
    anotar.
    """
    try:
        hiperparametros = _normalizar_hiper(hiperparametros)
    except ValueError as e:
        return {"error": str(e)}

    X = _codificar(codificacion)
    t0 = time.time()
    cs, ms = [], []
    try:
        for tr, te in KFold(n_splits=folds, shuffle=True, random_state=42).split(X):
            modelo = _construir(predictor, hiperparametros)
            modelo.fit(X[tr], Y[tr])
            p = modelo.predict(X[te])
            cs.append(c_index(Y[te], p))
            ms.append(float(np.mean((Y[te] - p) ** 2)))
    except Exception as e:
        return {"error": f"fallo entrenando: {type(e).__name__}: {e}"}

    return {
        "predictor": predictor,
        "codificacion": codificacion,
        "hiperparametros": hiperparametros or {},
        "c_index": round(float(np.mean(cs)), 4),
        "c_index_sd": round(float(np.std(cs)), 4),
        "mse": round(float(np.mean(ms)), 3),
        "segundos": round(time.time() - t0, 2),
        "_folds_c": [round(c, 4) for c in cs],
    }


def evaluar_predictor(predictor, codificacion="entero", hiperparametros=None, folds=10):
    """
    Entrena y evalua un predictor con validacion cruzada. Devuelve C-index y MSE.

    Cuesta entre 0.02 y 25 segundos segun el predictor. Esa es toda la gracia:
    el agente puede barrer el catalogo entero mientras el instructor lo explica.
    Las 1193 arquitecturas que entrenan este predictor costaron ~9500 horas de
    GPU; evaluarlo cuesta segundos.
    """
    if predictor not in PREDICTORES:
        return {"error": f"predictor desconocido: '{predictor}'",
                "disponibles": list(PREDICTORES)}
    if codificacion not in CODIFICACIONES:
        return {"error": f"codificacion desconocida: '{codificacion}'",
                "disponibles": list(CODIFICACIONES)}

    entrada = _medir(predictor, codificacion, hiperparametros, folds)
    if "error" in entrada:
        return entrada
    PIZARRON.append(entrada)
    return _publico(entrada)


def ranking(metrica="c_index", top=5):
    """
    El pizarron ordenado. Esta tool existe porque el modelo no ordena.

    Medido: despues de evaluar los 18 predictores -los 18, bien, el mismo-,
    el Experimentador acierta los tres primeros del ranking y se equivoca del
    cuarto en adelante, 3 veces de 3. Siempre se salta xgboost, que es el
    cuarto real. Los numeros los tiene; lo que no tiene es con que ordenarlos.

    Un `sorted()` lo resuelve exacto y en cero segundos. Es la misma leccion
    del bloque 2: lo que la maquina hace bien, que lo haga la maquina, y que
    el modelo se quede con lo que solo el puede hacer, que es decidir que
    pedir y como contarlo.
    """
    if not PIZARRON:
        return {"error": "el pizarron esta vacio; evalua algo primero"}
    if metrica not in ("c_index", "mse"):
        return {"error": f"metrica desconocida: '{metrica}'",
                "disponibles": ["c_index", "mse"]}

    # c_index: mayor es mejor. mse: menor es mejor.
    al_reves = metrica == "c_index"
    orden = sorted(PIZARRON, key=lambda e: e[metrica], reverse=al_reves)
    return {
        "ordenado_por": metrica,
        "criterio": "mayor es mejor" if al_reves else "menor es mejor",
        "total_evaluados": len(PIZARRON),
        "mejores": [{"puesto": i, "predictor": _etiqueta(e),
                     "c_index": e["c_index"], "mse": e["mse"]}
                    for i, e in enumerate(orden[:top], 1)],
        "peor": {"predictor": _etiqueta(orden[-1]),
                 metrica: orden[-1][metrica]},
        "quedan_fuera_de_esta_lista": max(0, len(orden) - top),
    }


# ---------------------------------------------------------------------------
# Busqueda de hiperparametros
#
# Para los once del paper, la rejilla es la de su Tabla 2, tal cual, para que
# sus numeros se puedan reproducir. Para los siete que agregamos nosotros, una
# rejilla chica sobre lo que cada fabrica acepta.
#
# Por que esto es una tool de Python y no algo que el agente itere solo:
# probar 26 configuraciones de SVR serian 26 vueltas del bucle, y el contexto
# real son 4096 tokens -el Experimentador ya llega a 3541 barriendo el
# catalogo-. La busqueda cabe en una sola llamada porque el ganador es UNA
# linea. Es la misma division de siempre: la maquina enumera, el modelo decide
# que enumerar.
# ---------------------------------------------------------------------------
REJILLAS = {
    # --- Tabla 2 del paper ---
    "linear": {"fit_intercept": [True, False]},
    "ridge": {"alpha": [0.01, 0.1, 1, 10, 100]},
    "lasso": {"alpha": [0.01, 0.1, 1, 10, 100]},
    "elasticnet": {"alpha": [0.01, 0.1, 1, 10], "l1_ratio": [0.1, 0.5, 0.9]},
    "decision_tree": {"max_depth": [5, 10, 20], "min_samples_split": [2, 5],
                      "min_samples_leaf": [1, 2], "max_features": ["sqrt", "log2"]},
    "random_forest": {"n_estimators": [200, 500], "max_depth": [5, 10, None],
                      "min_samples_leaf": [1, 2], "max_features": ["sqrt"]},
    "xgboost": {"n_estimators": [200, 500], "max_depth": [1, 3, 5],
                "learning_rate": [0.01, 0.1], "subsample": [0.8]},
    "adaboost": {"n_estimators": [200, 500], "learning_rate": [0.1, 0.5]},
    "extra_trees": {"n_estimators": [200, 500], "max_depth": [10, 20],
                    "min_samples_split": [2, 5], "min_samples_leaf": [1, 2],
                    "max_features": ["sqrt"]},
    "knn": {"n_neighbors": [3, 5, 7], "weights": ["uniform", "distance"],
            "p": [1, 2]},
    "svr": {"C": [0.01, 0.072, 0.52, 3.72, 10.0, 26.8, 71.0, 188.7, 501.2,
                  1335.2], "epsilon": [0.1, 0.01]},
    # --- los nuestros ---
    "gradient_boosting": {"n_estimators": [200], "learning_rate": [0.05, 0.1],
                          "max_depth": [3, 5]},
    "hist_gradient_boosting": {"n_estimators": [200, 500],
                               "learning_rate": [0.05, 0.1]},
    "bagging": {"n_estimators": [50, 200]},
    "huber": {"alpha": [0.0001, 0.01, 1.0]},
    "mlp": {"hidden_layer_sizes": [(128, 64), (256, 128)], "max_iter": [600]},
    "gaussian_process": {"length_scale": [0.5, 1.0, 2.0]},
    "bayesian_ridge": {},
}


def buscar_hiperparametros(predictor, codificacion="entero"):
    """
    Corre la rejilla entera de un predictor y devuelve SOLO el ganador.

    Las configuraciones intermedias no van al pizarron -serian ruido para la
    prueba de Friedman-; solo se anota la mejor, etiquetada como ajustada para
    que no se confunda con la de valores por omision.

    Medido: con la rejilla del paper, knn sube de 0.5686 a 0.6595 y pasa al
    0.6542 publicado. Ese salto es puramente hiperparametros.
    """
    if predictor not in PREDICTORES:
        return {"error": f"predictor desconocido: '{predictor}'",
                "disponibles": list(PREDICTORES)}
    rejilla = REJILLAS.get(predictor)
    if not rejilla:
        return {"error": f"no hay rejilla para '{predictor}'",
                "sugerencia": "evaluarlo con sus valores por omision"}

    import itertools
    claves = list(rejilla)
    combinaciones = list(itertools.product(*(rejilla[k] for k in claves)))

    base = _medir(predictor, codificacion, None, 10)
    if "error" in base:
        return base

    t0 = time.time()
    mejor, fallidas = base, 0
    for valores in combinaciones:
        h = dict(zip(claves, valores))
        r = _medir(predictor, codificacion, h, 10)
        if "error" in r:
            fallidas += 1
            continue
        if r["c_index"] > mejor["c_index"]:
            mejor = r

    mejoro = mejor["hiperparametros"] != {}
    if mejoro:
        PIZARRON.append(mejor)

    resultado = {
        "predictor": predictor,
        "configuraciones_probadas": len(combinaciones) + 1,
        "segundos": round(time.time() - t0, 1),
        "mejor_c_index": mejor["c_index"],
        "mejores_hiperparametros": mejor["hiperparametros"] or "los de omision",
        "c_index_con_omision": base["c_index"],
        "gano": round(mejor["c_index"] - base["c_index"], 4),
        "anotado_en_el_pizarron": bool(mejoro),
    }
    if fallidas:
        resultado["configuraciones_que_fallaron"] = fallidas
    if not mejoro:
        resultado["nota"] = ("Ninguna configuracion de la rejilla le gano a los "
                             "valores por omision. No se anoto nada nuevo.")
    return resultado


def comparar_evaluaciones():
    """
    Prueba de Friedman sobre todo lo evaluado: las diferencias son
    significativas, o cabe en el azar?

    Es el guardrail de honestidad del caso. Reportar el maximo de una lista de
    veinte es casi siempre una afirmacion de mas, y el propio paper lo sabe:
    su diagrama de diferencia critica muestra a Extra Trees, SVR, XGBoost,
    Random Forest y KNN en un mismo grupo indistinguible.
    """
    if len(PIZARRON) < 3:
        return {"error": "hacen falta al menos 3 evaluaciones para comparar",
                "evaluadas": len(PIZARRON)}

    from scipy.stats import friedmanchisquare
    matriz = np.array([e["_folds_c"] for e in PIZARRON])
    etiquetas = [_etiqueta(e) for e in PIZARRON]

    try:
        stat, p = friedmanchisquare(*matriz)
    except Exception as e:
        return {"error": f"no se pudo correr Friedman: {e}"}

    # Ranking medio por fold: 1 = el mejor de esa fold
    ordenes = (-matriz).argsort(axis=0).argsort(axis=0) + 1
    rangos = ordenes.mean(axis=1)

    orden = np.argsort(rangos)
    mejor = etiquetas[int(orden[0])]

    # Dos formas de decir "estos no se distinguen", y conviene tener las dos a
    # la vista porque dan grupos de tamano muy distinto:
    #
    # 1. Un umbral de 1.0 rangos. Es una heuristica, NO un test. Agrupa a los
    #    que quedaron casi pegados en el ranking medio.
    # 2. La distancia critica de Nemenyi, que si es el post-hoc que acompana a
    #    Friedman y es lo que dibuja el diagrama de diferencia critica del
    #    paper (su Figura 2).
    #
    # La de Nemenyi casi siempre da un grupo MAS GRANDE, porque con pocas
    # repeticiones tiene poca potencia: con 18 modelos y 10 folds la CD vale
    # 8.3 rangos, sobre un rango total de 12. Dicho de otro modo: la mitad de
    # la tabla es indistinguible de la mejor, y el umbral de 1.0 es mas
    # optimista que el test.
    #
    # Advertencia honesta: Nemenyi supone muestras independientes, y los folds
    # de una validacion cruzada no lo son -comparten datos de entrenamiento-.
    # Usar folds como repeticiones es lo que se hace en la practica (y lo que
    # permite comparar con el paper), pero infla la confianza. Vale para
    # ordenar la discusion; no para cerrar una.
    empatados = [etiquetas[int(i)] for i in orden
                 if abs(rangos[int(i)] - rangos[int(orden[0])]) < 1.0]

    k, n_folds = len(PIZARRON), matriz.shape[1]
    try:
        from scipy.stats import studentized_range
        q = float(studentized_range.ppf(0.95, k, np.inf)) / np.sqrt(2)
        cd = float(q * np.sqrt(k * (k + 1) / (6.0 * n_folds)))
        por_nemenyi = [etiquetas[int(i)] for i in orden
                       if rangos[int(i)] - rangos[int(orden[0])] <= cd]
    except Exception:            # scipy viejo: sin studentized_range
        cd, por_nemenyi = None, None

    return {
        "evaluadas": len(PIZARRON),
        "friedman_p": round(float(p), 5),
        "hay_diferencia_significativa": bool(p < 0.05),
        "ranking_medio": {etiquetas[int(i)]: round(float(rangos[int(i)]), 2) for i in orden},
        "mejor_por_ranking": mejor,
        "indistinguibles_del_mejor": empatados,
        "criterio_del_grupo_de_arriba": ("rangos medios a menos de 1.0 del mejor; "
                                         "es una heuristica, no un test"),
        "nemenyi": {
            "distancia_critica": round(cd, 2) if cd else None,
            "folds_usados_como_repeticiones": n_folds,
            "indistinguibles_del_mejor": por_nemenyi,
            "lectura": ("El post-hoc formal, el del diagrama de diferencia "
                        "critica del paper. Da un grupo MAS grande que la "
                        "heuristica: con pocas repeticiones tiene poca "
                        "potencia, asi que separar dos modelos cuesta mucho."),
        },
        "nota": ("Si 'indistinguibles_del_mejor' trae mas de uno, decir que "
                 "'gano X' es una afirmacion de mas: lo honesto es nombrar al "
                 "grupo y elegir dentro de el por otro criterio, como el "
                 "tiempo. Y si los dos criterios discrepan, el conservador "
                 "-el de Nemenyi, el grupo grande- es el que no te hace "
                 "afirmar de mas."),
    }


def comparar_con_el_paper(predictor):
    """Lo publicado para ese predictor, para poder calificar al agente."""
    if predictor not in PAPER:
        return {"error": f"el paper no reporta '{predictor}'",
                "reportados": list(PAPER)}
    return {"predictor": predictor, "paper": PAPER[predictor],
            "fuente": "Sarmiento-Rosales et al. (2026), Tabla 3"}


def limpiar_pizarron():
    PIZARRON.clear()
    return {"estado": "pizarron vacio"}
