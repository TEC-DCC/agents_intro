# Los datos del caso MDM

Dos fuentes de clientes que se traslapan. El mismo cliente está en las dos,
capturado distinto, y además repetido dentro de su propia fuente. El trabajo es
dejar **un registro por persona**.

Todo es inventado. Los nombres, los RFC y los correos no corresponden a nadie.

## Los archivos

| Archivo | Qué es | Filas |
|---|---|---|
| `bronce_crm.csv` | Fuente 1. Ventas, captura manual | 43 |
| `bronce_facturacion.csv` | Fuente 2. Sistema contable | 42 |
| `personas.csv` | **La verdad.** Las personas que de veras existen | 55 |
| `verdad.csv` | **La respuesta.** Qué registro es de qué persona | 85 |

`personas.csv` y `verdad.csv` no se le dan al agente: son la clave con la que se
califica lo que produjo.

## Los números que tienen que salir

| | |
|---|---|
| registros de entrada | **85** |
| golden records correctos | **55** |
| fusiones correctas | **30** |
| pares entre las dos fuentes | 20 |
| duplicados dentro de CRM | 5 |
| duplicados dentro de facturación | 5 |
| personas en una sola fuente | 35 (25 únicas + las 10 de las trampas) |

**Un solo número dice cómo salió la corrida.** Si el resultado trae menos de 55
golden records, el agente fusionó de más y cayó en alguna trampa. Si trae más de
55, se le escaparon pares. Las dos cosas importan, pero no cuestan lo mismo:
fusionar de más destruye la distinción entre dos personas y no se deshace.

## Por qué las dos fuentes no se parecen

Las diferencias son las de dos sistemas reales, no ruido al azar.

| | `bronce_crm.csv` | `bronce_facturacion.csv` |
|---|---|---|
| columnas | `nombre, correo, telefono, rfc, ciudad, alta` | `razon_social, email, tel, rfc, estado, registro` |
| orden del nombre | nombre primero | **apellidos primero**, en mayúsculas |
| acentos | irregulares | ninguno |
| RFC | la raíz de 10, **sin homoclave**; a veces vacío | siempre los 13 completos |
| teléfono | con espacios, a veces `+52` | 10 dígitos pelones |
| lugar | ciudad, en texto libre (`CDMX`, `Mexico DF`, `Gdl`) | estado completo |
| correo | personal | corporativo en la mayoría |

El cruce de columnas es determinista y va en una tool. Lo que no es
determinista es decidir si dos registros son la misma persona.

## Las cinco trampas

Son pares que **se parecen y no son la misma persona**. Cada una ataca una
señal distinta, para que ninguna regla sola las resuelva todas.

| # | Registros | Qué los hace parecer iguales | Por qué no lo son |
|---|---|---|---|
| 1 | `C021` / `F021` y `C041` / `F021` | **La raíz de 10 del RFC es idéntica**: `RASJ900714` | Son Juan Carlos Ramírez Soto y Javier Ramírez Salinas, nacidos el mismo día |
| 2 | `C022` / `F022` | Nombre completo idéntico y la misma ciudad | Distinta fecha de nacimiento, y por eso distinto RFC. Dos José Luis Morales Ruiz de Puebla |
| 3 | `C023` / `F023` | Mismo nombre y **el mismo teléfono** | Padre e hijo. El teléfono es el de la casa |
| 4 | `C024` / `F024` | Mismos apellidos, **mismo teléfono**, nombre casi igual | Hermanas: Ana Patricia y Ana Lucía |
| 5 | `C025` / `F025` | **Mismo correo y mismo teléfono** | Socios de la misma panadería. El contacto es del negocio |

La trampa 1 es la que justifica el caso entero. La raíz de 10 del RFC se forma
con las iniciales y la fecha de nacimiento, así que **dos personas distintas
pueden compartirla** — para eso existe la homoclave. Una regla determinista
llega a "candidato" y nunca a "es el mismo".

**La trampa 1 aparece en dos pares, y no son el mismo ejercicio.** `C021` viene
del CRM sin homoclave, así que en `C021` / `F021` la regla no se puede aplicar y
la respuesta honesta es que no se sabe por el RFC. El duplicado interno `C041`
sí trae los 13 completos, y en `C041` / `F021` la homoclave decide: `A15` contra
`B82`.

Las trampas 3, 4 y 5 atacan la señal contraria: un teléfono o un correo
compartido no identifica a una persona, identifica a una casa o a un negocio.

### Qué tan difícil es cada una

Medido sobre la evidencia que produce `maestro.comparar()`, contando cuántas
señales apuntan a "la misma persona" cuando no lo son.

| # | Señales a favor | Dificultad |
|---|---|---|
| 3 | nombre idéntico, teléfono idéntico, mismo lugar | **la más difícil**: casi todo dice que sí, y solo el RFC dice que no |
| 4 | apellidos idénticos, teléfono idéntico, mismo lugar | difícil |
| 5 | correo idéntico, teléfono idéntico, mismo lugar | media: los nombres no se parecen en nada |
| 2 | nombre idéntico, mismo lugar | media |
| 1 | la raíz del RFC | **la más fácil**: el resto de la evidencia también dice que son distintas |

La 1 es la más fácil de acertar y la más fácil de acertar **por la razón
equivocada**. Un agente puede decir "personas distintas" porque los apellidos no
coinciden, sin haber entendido la homoclave. Vale la pena leer su justificación,
no solo su veredicto.

## Los pares difíciles que sí hay que fusionar

Para que no baste con "fusiona solo si el RFC coincide":

| Registros | Qué los separa |
|---|---|
| `C007` / `F007` | El CRM no trae RFC y los teléfonos no coinciden |
| `C013` / `F013`, `C016` / `F016` | El teléfono cambió entre un sistema y el otro, y el correo también |
| `C003` / `C039` | Duplicado interno con otro correo y otro teléfono con formato distinto |
| `C028` / `C042` | Duplicado interno con el nombre abreviado y la ciudad como `Gdl` |
| `F005` / `F038` | Duplicado interno con el apellido mal escrito: `SANCHES` |
