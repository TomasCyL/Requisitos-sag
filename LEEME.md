# Control de requisitos SAG · C&L Fruit (versión online)

App web para que la contraparte SAG controle los requisitos de despacho de cada orden de embarque.

- **Pantalla:** GitHub Pages → https://tomascyl.github.io/Requisitos-sag/ (se entra con la cuenta Microsoft de C&L).
- **Datos:** listas `RQ_Datos`, `RQ_Mercados` y `RQ_Checks` del sitio SharePoint EXPORTADORACYL. Los respaldos de cada check quedan en la biblioteca de documentos del sitio, carpeta `APP REQUISITOS EXPORTACION/Respaldos/<orden>/<requisito>/`.
- **Despachos:** el robot `robot/sincronizar_sdt.py` (GitHub Actions, cada 10 min y a demanda) lee SDT y deja las órdenes en `RQ_Datos`. Ningún dato de SDT queda en este repositorio.
- **Demo sin cuentas ni datos reales:** agregar `?demo` a la dirección.

## Puesta en marcha (una sola vez)

### 1. Publicar la pantalla
Repositorio → Settings → Pages → *Deploy from a branch* → rama `main`, carpeta `/ (root)`.

### 2. Permitir el inicio de sesión desde la nueva dirección
Entra ID → Registros de aplicaciones → **Entregas CyL** → Autenticación → plataforma *Aplicación de página única* → agregar el URI de redirección:

    https://tomascyl.github.io/Requisitos-sag/

(Usa los mismos permisos ya aprobados de Entregas: `Sites.ReadWrite.All` y `User.Read` delegados.)

### 3. Abrir la app y cargar la matriz
Abrir https://tomascyl.github.io/Requisitos-sag/ con una cuenta que pueda editar el sitio EXPORTADORACYL. La primera vez crea las tres listas y ofrece **Cargar matriz inicial** o **Importar estado.json** (el de la versión local, con lo ya editado).

### 4. Crear la app del robot en Entra (requiere un administrador)
1. Registros de aplicaciones → Nuevo registro → nombre `Requisitos SAG robot` (sin URI de redirección).
2. Permisos de API → Microsoft Graph → **Permisos de aplicación** → `Sites.Selected` → *Conceder consentimiento de administrador*.
3. Certificados y secretos → Nuevo secreto de cliente → copiar el **valor**.
4. Un administrador le da al robot permiso de escritura **solo en el sitio EXPORTADORACYL**. En Graph Explorer (https://developer.microsoft.com/graph/graph-explorer), con `Sites.FullControl.All` consentido:
   - `GET https://graph.microsoft.com/v1.0/sites/cylfruit.sharepoint.com:/sites/EXPORTADORACYL` → copiar el `id`.
   - `POST https://graph.microsoft.com/v1.0/sites/{id}/permissions` con el cuerpo:

         {"roles":["write"],"grantedToIdentities":[{"application":{"id":"<Id. de aplicación del robot>","displayName":"Requisitos SAG robot"}}]}

   Alternativa más simple pero más amplia: darle al robot el permiso de aplicación `Sites.ReadWrite.All` (escribe en todos los sitios) y omitir este punto 4.

### 5. Cargar los secretos del robot
Repositorio → Settings → Secrets and variables → Actions → *New repository secret*:

| Secreto | Valor |
|---|---|
| `SDT_USUARIO` | usuario de SDT |
| `SDT_CLAVE` | clave de SDT |
| `GRAPH_TENANT_ID` | `5946134b-9789-4d13-86c4-e01684301b6a` |
| `GRAPH_CLIENT_ID` | Id. de aplicación (cliente) de `Requisitos SAG robot` |
| `GRAPH_CLIENT_SECRET` | valor del secreto del paso 4.3 |

Probar: pestaña Actions → **Sincronizar SDT** → *Run workflow*. Debe terminar en verde con el mensaje `OK: N ordenes de embarque guardadas en SharePoint`.

### 6. Botón «Leer SDT ahora» de la app
GitHub → Settings (del usuario) → Developer settings → Fine-grained tokens → *Generate new token*: solo el repositorio `Requisitos-sag`, permiso **Actions: Read and write**. Pegarlo en la app: Mantenedor → Conexión SDT → *Guardar llave*. Queda en SharePoint, no en el código.

## Notas
- GitHub ejecuta el cron "cada 10 minutos" con atraso variable (a veces 15 a 30 min en horas de carga). Para un dato al momento, usar «Leer SDT ahora» (tarda cerca de un minuto).
- GitHub desactiva los flujos programados si el repositorio pasa 60 días sin cambios; se reactivan desde la pestaña Actions.
- Ajustes del robot (días hacia atrás/adelante, tipos de nave excluidos) al inicio de `robot/sincronizar_sdt.py`.
- Para cambiar el sitio de SharePoint: `CFG.sitio` en `index.html` y `SP_SITIO` en el robot.
