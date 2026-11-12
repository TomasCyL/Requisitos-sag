# Control de requisitos SAG · C&L Fruit (versión online)

App web para que la contraparte SAG controle los requisitos de despacho de cada orden de embarque.

- **Pantalla:** GitHub Pages → https://tomascyl.github.io/Requisitos-sag/ (se entra con la cuenta Microsoft de C&L).
- **Datos:** listas `RQ_Datos`, `RQ_Mercados` y `RQ_Checks` del sitio SharePoint EXPORTADORACYL. Los respaldos de cada check quedan en la biblioteca de documentos del sitio, carpeta `APP REQUISITOS EXPORTACION/Respaldos/<orden>/<requisito>/`.
- **Despachos:** el robot `robot/sincronizar_sdt.py` (GitHub Actions, cada 5 min y a demanda) lee SDT y deja las órdenes en `RQ_Datos`. Ningún dato de SDT queda en este repositorio.
- **Demo sin cuentas ni datos reales:** agregar `?demo` a la dirección.

## Puesta en marcha (una sola vez)

### 1. Publicar la pantalla
Repositorio → Settings → Pages → *Deploy from a branch* → rama `main`, carpeta `/ (root)`.

### 2. Permitir el inicio de sesión desde la nueva dirección
Entra ID → Registros de aplicaciones → **Entregas CyL** → Autenticación → plataforma *Aplicación de página única* → agregar el URI de redirección:

    https://tomascyl.github.io/Requisitos-sag/

(Usa los mismos permisos ya aprobados de Entregas: `Sites.ReadWrite.All` y `User.Read` delegados.)

### 3. Abrir la app y cargar la matriz
Abrir https://tomascyl.github.io/Requisitos-sag/ con una cuenta que pueda editar el sitio EXPORTADORACYL. Las tres listas (`RQ_Datos`, `RQ_Mercados`, `RQ_Checks`) ya están creadas en el sitio y la matriz ya está cargada (12-11-2026). En un sitio nuevo hay que crear antes esas listas, cada una con una columna de varias líneas de texto sin formato (`Valor` en RQ_Datos, `Datos` en las otras dos); recién entonces la app ofrece **Cargar matriz inicial** o **Importar estado.json** (el de la versión local, con lo ya editado).

### 4. App del robot en Entra (requiere un administrador)
La app `Requisitos SAG robot` ya está registrada (Id. de aplicación `5f1a4569-72a5-4eaa-ba0f-2d9e7eaab96c`) con el permiso de aplicación `Sites.Selected`. El inquilino bloquea los secretos de cliente, así que el robot entra con una **credencial federada** de GitHub Actions (sin secreto):

1. Certificados y secretos → **Credenciales federadas** → Agregar credencial → escenario *Acciones de GitHub que implementan recursos de Azure*: organización `TomasCyL`, repositorio `Requisitos-sag`, tipo de entidad *Rama*, rama `main`, nombre `github-main`.
2. Un administrador concede el consentimiento: Permisos de API → *Conceder consentimiento de administrador*.
3. Un administrador le da al robot escritura **solo en el sitio EXPORTADORACYL**. En Graph Explorer (https://developer.microsoft.com/graph/graph-explorer), con `Sites.FullControl.All` consentido:
   - `GET https://graph.microsoft.com/v1.0/sites/cylfruit.sharepoint.com:/sites/EXPORTADORACYL` → copiar el `id`.
   - `POST https://graph.microsoft.com/v1.0/sites/{id}/permissions` con el cuerpo:

         {"roles":["write"],"grantedToIdentities":[{"application":{"id":"5f1a4569-72a5-4eaa-ba0f-2d9e7eaab96c","displayName":"Requisitos SAG robot"}}]}

### 5. Cargar los secretos del robot
Repositorio → Settings → Secrets and variables → Actions → *New repository secret*:

| Secreto | Valor |
|---|---|
| `SDT_USUARIO` | usuario de SDT |
| `SDT_CLAVE` | clave de SDT |

Probar: pestaña Actions → **Sincronizar SDT** → *Run workflow*. Debe terminar en verde con el mensaje `OK: N ordenes de embarque guardadas en SharePoint`.

### 6. Botón «Leer SDT ahora» de la app
GitHub → Settings (del usuario) → Developer settings → Fine-grained tokens → *Generate new token*: solo el repositorio `Requisitos-sag`, permiso **Actions: Read and write**. Pegarlo en la app: Mantenedor → Conexión SDT → *Guardar llave*. Queda en SharePoint, no en el código.

## Notas
- GitHub ejecuta el cron "cada 5 minutos" con atraso variable (a veces 15 a 30 min en horas de carga). Para un dato al momento, usar «Leer SDT ahora» (tarda cerca de un minuto).
- GitHub desactiva los flujos programados si el repositorio pasa 60 días sin cambios; se reactivan desde la pestaña Actions.
- Ajustes del robot (días hacia atrás/adelante, tipos de nave excluidos) al inicio de `robot/sincronizar_sdt.py`.
- Para cambiar el sitio de SharePoint: `CFG.sitio` en `index.html` y `SP_SITIO` en el robot.
