# evals/

Los casos de prueba del bloque 5. Existen para sostener una afirmación del
taller que de otro modo suena a eslogan: **un agente no se prueba como se
prueba una función.**

La temperatura hace que la misma entrada dé salidas distintas, así que comparar
cadenas no sirve. Lo que se verifica es el **efecto**: dada esta petición en
lenguaje natural, ¿el sistema terminó en el estado correcto, y usó las
tools que correspondían?

```
caso:      "Necesito 3 kilos de café para el cliente 7"
espera:    que exista un pedido del cliente 7 con 3 unidades de CAFE-500
           y que se haya llamado consultar_stock antes de crear_pedido
no espera: ninguna llamada a cancelar_pedido
```

Esa última línea es la que más enseña. Lo que un agente **no** debe hacer es
más difícil de verificar, y más caro de equivocar, que lo que debe hacer.

**Pendiente del caso de estudio.** Cuando cierre, aquí van `casos.yaml` y un
`correr_evals.py` de unas cincuenta líneas — sin framework, igual que todo lo
demás.
