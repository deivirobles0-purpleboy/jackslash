# PurpleSlash: primer ensayo

Este directorio es el clon de pruebas. No reutilizar el token ni la base de datos
de PurpleJack. Square Cloud debe inyectar estas variables de entorno:

- `PURPLESLASH_DISCORD_TOKEN`: token del bot de pruebas.
- `PURPLESLASH_DATABASE_URL`: PostgreSQL **separado** de producción.
- `PURPLESLASH_GUILD_ID`: ID del servidor donde se probarán los slash commands.

`squarecloud.app` y `requirements.txt` se incluyeron en la copia. El modo de
pruebas permanece activado: los workers automáticos de cofres, logs, cargos,
purga y eventos no actúan sobre los canales del bot principal. Las partidas,
las jornadas y los recordatorios usan la base de datos de pruebas.

Pruebas manuales sugeridas antes de avanzar con más comandos:

1. Con y sin el rol `1527103455313793136`, probar `/jugar`, `/trabajar` y
   `/consultar`. Sin rol no debe abrirse el panel.
2. En `/jugar apuesta:100`, abrir los cuatro juegos. El panel debe permanecer
   privado y cada tablero o resultado tradicional debe aparecer en el canal.
3. En Ruleta probar Black, Red, Par, Impar y Número (0, 36 y un valor inválido).
4. Completar una partida de cada juego. El cooldown debe empezar después de
   la liquidación. Pulsar 🔕 para activar 🔔 y verificar el mensaje privado al
   terminar el cooldown; repetir tras reiniciar el bot.
5. Probar Trabajar, Aplicar, Renunciar, Oficina, y cada botón de Consultar.
6. Probar `/work`, `/crime`, `/collect` y `/tienda`; el resultado conserva el
   formato y la economía de PurpleJack. `/tienda` mantiene su espera de 30 s.
7. Probar `/rob usuario`, `/carrera apuesta` y `/retar usuario apuesta`. En
   un mensaje ajeno, probar **Apps → Robar**. `/rob` sin usuario muestra una
   indicación: Discord no entrega el mensaje respondido a un slash command.
   Las posiciones del Top ya no sirven como objetivo de robo.

Los comandos de texto `!` están desactivados. `/ayuda_nave` se conserva sin
cambios por solicitud; por ahora aún describe el bot original.
