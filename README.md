# Vantarmor Commands

Bot de Discord con web de cuenta, acceso OAuth2, comandos y funciones Premium.

## Acceso a comandos

Solo estos comandos slash son gratuitos:
- `/lockdown`: requiere además ser propietario o administrador del servidor y los permisos del bot para administrar canales.
- `/filtro-cuentas`: requiere además ser propietario o administrador del servidor; puedes configurar un rol de revisión.

**Todos los demás comandos slash requieren que quien los use tenga Premium activo.** Si una persona sin Premium intenta usarlos, el bot responde con un aviso privado y no ejecuta el comando. Los permisos administrativos propios de cada comando siguen aplicándose.

El acceso Premium se comprueba por la cuenta de Discord del usuario. Se puede conceder mediante el panel web de administración, canjeando una key, o usando `PREMIUM_USER_IDS` para IDs permanentes.

## Variables de Railway

Obligatorias para iniciar el bot:
- `DISCORD_TOKEN`: token privado del bot.

Para login web de Discord:
- `DISCORD_CLIENT_ID`: ID de aplicación del bot.
- `DISCORD_CLIENT_SECRET`: secreto OAuth de esa aplicación; nunca lo publiques.
- `DISCORD_REDIRECT_URI`: URL pública exacta terminada en `/auth/callback`.
- `PUBLIC_BASE_URL`: dominio HTTPS público de Railway (opcional, para cookies seguras si no está `RAILWAY_PUBLIC_DOMAIN`).

Para administración de keys y datos:
- `PREMIUM_MANAGER_IDS`: IDs de Discord autorizados para administrar Premium, separados por comas.
- `PREMIUM_USER_IDS`: IDs con Premium manual permanente, separados por comas.
- `VANTARMOR_DATA_DIR`: ruta de datos persistente montada en Railway; monta un volumen en esa ruta para conservar Premium, ajustes de seguridad, tickets y estadísticas entre despliegues.
- `BOT_INVITE_URL`: opcional; URL personalizada de invitación.

Configura en el portal de Discord OAuth2 la misma URL `DISCORD_REDIRECT_URI` como Redirect URI y usa el scope `identify guilds`. La web arranca junto al bot en el puerto `PORT` de Railway.

## Funciones de seguridad

- `/anti-raid activar umbral ventana`: detecta ráfagas de miembros y activa el modo pánico.
- `/anti-nuke activar umbral ventana`: vigila borrados de canales/roles y baneos en audit log; al alcanzar umbral bloquea el envío para `@everyone` y notifica. No banea ni quita permisos a administradores automáticamente.
- `/anti-bot accion bot`: lista autorizada; los bots no autorizados nuevos se expulsan si el bot tiene `Kick Members`.
- `/filtro-cuentas dias rol_revision`: asigna un rol de revisión a cuentas más recientes que el umbral; el administrador debe configurar ese rol con permisos restringidos.
- `/lockdown activar`: congela el envío de `@everyone` en canales de texto y guarda sus permisos anteriores; al desactivarlo restaura los permisos.
- `/captcha-panel canal rol_verificado`: publica un botón con un reto aritmético modal. Configura los permisos de `@everyone` para limitar el acceso hasta verificar.
- `/security-log canal` y `/security-status`: permiten configurar alertas y consultar el estado.

Los comandos de seguridad requieren permisos apropiados de Discord. Anti-Raid, Anti-Nuke, Anti-Bot, captcha y los registros de seguridad requieren Premium; `/lockdown` y `/filtro-cuentas` son gratuitos, con acceso administrativo al servidor.

El bot necesita permisos acordes a las funciones usadas, incluyendo Ver registro de auditoría, Administrar canales/roles y Expulsar miembros. Revisa cuidadosamente la jerarquía de roles.

## Copias Premium

`/seguridad-copia` guarda estructura de categorías/canales del servidor donde se ejecuta. La restauración recrea categorías y canales que falten y no elimina los existentes. No conserva mensajes.
