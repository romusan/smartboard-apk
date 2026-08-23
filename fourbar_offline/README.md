# Síntesis inversa de mecanismos — Android sin conexión

Aplicación autónoma para tabletas Samsung/Android. El usuario dibuja una curva cerrada y el motor PSO sintetiza un mecanismo plano de cuatro barras, calcula sus dimensiones y anima el punto trazador.

## Arquitectura extensible

La interfaz `MechanismSynthesizer<S>` separa el optimizador y la cinemática de la interfaz Compose. Una futura implementación `SixBarSynthesizer` puede devolver sus propias poses sin modificar el capturador de curvas.

## Privacidad y funcionamiento

- No contiene permiso `INTERNET`.
- No usa servidor, Python, WebView ni almacenamiento externo.
- Toda la síntesis y la simulación se ejecutan en Kotlin dentro de la tableta.

## Construcción

Requiere JDK 17 y Android SDK 35:

```text
gradle testDebugUnitTest assembleDebug
```

La APK queda en `app/build/outputs/apk/debug/app-debug.apk`.

