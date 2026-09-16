# Spirit — *La Grieta*

El Spirit de Spec1 4.1, salvo la lista `characters`, que vive en `characters.md`. Juntos, ambos
ficheros forman el Spirit. Los nueve beats están cerrados en `done`.

```yaml
spirit:
  title: La Grieta
  premise: >
    En la Estación Umbral, perforada en el casquete de hielo de Europa, una ingeniera de
    hidrófonos detecta una señal acústica recurrente en el océano que el sistema de la
    estación reclasifica automáticamente como ruido de instrumento, al amparo de una
    directriz nunca revisada desde un escándalo científico ocurrido doce años atrás.
  tone_and_style: >
    Prosa fría y precisa, ciencia ficción literaria de corte técnico. Tercera persona
    cercana sobre Mara Solís, tiempo pasado. El detalle instrumental antes que la
    explicación; la emoción se transmite por lo que ella mide, no por lo que declara.
    Sin melodrama, sin cursivas para pensamientos.

  main_thread:
    introduction: >
      Mara Solís, ingeniera de hidrófonos en la Estación Umbral, confía en que el catálogo
      oficial del océano de Europa —silencioso salvo por el hielo trabajando contra sí
      mismo— es el registro completo de lo que hay abajo, y su trabajo consiste en vigilar
      que ningún temblor ponga en riesgo el casco.
    development: >
      Un patrón acústico que se repite la lleva a los archivos sin filtrar y a Ezra Lund,
      quien le revela el Protocolo Umbral: una directriz permanente, nunca derogada desde
      un escándalo de falso positivo hace doce años, que reclasifica automáticamente como
      ruido cualquier anomalía recurrente por debajo de un umbral de energía. Cada informe
      que Mara presenta es absorbido y rebajado sin que nadie humano lo revise.
    resolution: >
      Mara no puede derogar el protocolo ni hacer pasar sus datos brutos por la revisión
      automática. Junto con Ezra, recurre al único registro que el clasificador nunca toca
      —la banda de papel del sismógrafo mecánico de respaldo— y se lo lleva a Kade Osei en
      persona, pidiéndole que eleve el hallazgo al comité con su propio nombre. Kade lo
      hace; la señal queda registrada, y la estación empieza, por primera vez, a escuchar
      el océano sin el filtro del protocolo.

  chapters:
    - id: 1
      title: El Eco
      introduction: >
        La Estación Umbral, el ritmo del turno de catálogo, y una ingeniera cuyo oficio
        entero descansa en la idea de que el océano bajo el hielo ya ha dicho todo lo que
        tenía que decir.
      development: >
        Mara encuentra un pulso acústico repetido, no catalogado, y confirma por
        triangulación con un segundo hidrófono que no es un fallo de instrumento.
      resolution: >
        Solicita acceso al archivo bruto completo. Kade lo aprueba de inmediato invocando
        el Protocolo Umbral sin explicarlo, y la rapidez de la aprobación la inquieta más
        de lo que la habría inquietado una negativa.
      target_paragraphs: 10
      beats:
        - id: c1b1
          description: >
            Establecer la Estación Umbral, el trabajo de Mara vigilando el hielo mediante
            el catálogo de sismos, y la premisa no examinada de que el océano de Europa es
            territorio cerrado desde hace doce años.
          status: done
        - id: c1b2
          description: >
            Mara detecta un pulso acústico recurrente y no catalogado en el hidrófono de
            babor, y confirma mediante triangulación con el hidrófono de estribor que no
            es un fallo del instrumento sino una fuente real bajo el hielo.
          status: done
        - id: c1b3
          description: >
            Solicita a Kade acceso al archivo bruto completo. Él lo aprueba de inmediato
            invocando el Protocolo Umbral sin explicarlo. El capítulo cierra con Mara
            inquieta por la velocidad de la aprobación.
          status: done

    - id: 2
      title: Protocolo Umbral
      introduction: null
      development: >
        Mara y Ezra Lund correlacionan dieciocho años de archivo bruto y confirman que la
        señal es estructurada, no atribuible a la flexión de marea. Ezra le revela el
        origen del Protocolo Umbral: un escándalo de falso positivo hace doce años que casi
        costó el programa oceánico, y la directriz de reclasificación automática que siguió.
      resolution: >
        Mara presenta un informe formal con anulación manual de la reclasificación
        automática y lo ve absorbido sin error ni rechazo que pueda apelar, exactamente
        como se absorbió la señal original.
      target_paragraphs: 10
      beats:
        - id: c2b1
          description: >
            Mara y Ezra correlacionan dieciocho años de archivo bruto: la señal es
            estructurada, tres tonos limpios que no encajan con el espectro de fricción de
            la flexión de marea.
          status: done
        - id: c2b2
          description: >
            Ezra revela el origen del Protocolo Umbral —el escándalo de CP-114 hace doce
            años— y confirma que el informe de Mara ya fue reclasificado como ruido la
            misma noche en que ella detectó la señal.
          status: done
        - id: c2b3
          description: >
            Mara presenta un informe formal con anulación manual de la reclasificación. El
            sistema lo absorbe sin error ni rechazo apelable. El capítulo cierra en ese
            silencio administrativo.
          status: done

    - id: 3
      title: La Banda de Papel
      introduction: null
      development: >
        Mara acepta que no puede derogar el Protocolo Umbral ni vencer al clasificador
        automático por la vía digital, y recurre con Ezra al sismógrafo mecánico de
        respaldo, cuyo registro en papel nunca pasa por el sistema.
      resolution: >
        Lleva la banda de papel y el informe reclasificado a Kade en persona y le pide que
        eleve el hallazgo al comité con su propio nombre. Kade lo hace; la señal EU-1 queda
        registrada, el Protocolo Umbral se suspende para ella, y la estación empieza a
        escuchar el océano sin el filtro automático.
      target_paragraphs: 10
      beats:
        - id: c3b1
          description: >
            Mara comprende que cualquier dato que entre por un canal digital pasará por el
            mismo clasificador, y recurre con Ezra al sismógrafo mecánico de respaldo, cuya
            banda de papel nunca ha pasado por el sistema.
          status: done
        - id: c3b2
          description: >
            La correlación entre la banda de papel y los pulsos del hidrófono da una
            segunda fuente independiente. Mara la lleva a Kade y le pide que eleve el
            hallazgo al comité con su propio nombre, no con una casilla del sistema.
          status: done
        - id: c3b3
          description: >
            Kade eleva el hallazgo. El comité suspende el Protocolo Umbral para la señal
            EU-1 en espera de revisión y autoriza una campaña de escucha específica.
            Resolución: la estación empieza, por primera vez, a escuchar el océano sin
            filtro.
          status: done

  current_chapter_id: null   # todos los capítulos cerrados — ejecución completa
```
