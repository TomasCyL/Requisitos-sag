#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robot de sincronizacion: lee de SDT las ordenes de embarque y los despachos
(las mismas APIs de la Agenda de Despachos) y deja el resultado en la lista
RQ_Datos de SharePoint, de donde lo toma la app web. Nada de SDT queda en GitHub.

Lo ejecuta GitHub Actions cada 10 min y a demanda. Solo libreria estandar.
Variables de entorno (secretos del repositorio):
  SDT_USUARIO, SDT_CLAVE                         usuario y clave de SDT
  GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET   app de Entra del robot
"""
import json, os, sys, base64, datetime, unicodedata, urllib.request, urllib.parse, urllib.error

# ─────────────────────────── CONFIG ───────────────────────────
SP_SITIO          = "https://cylfruit.sharepoint.com/sites/EXPORTADORACYL"
LISTA             = "RQ_Datos"
ORDENES_API_URL   = "https://apicloudfruit.cylfruit.com/produccion/cb/CB_GenerarDataReportes/InformeOrdenEmbarque/%20/%20/%20/%20/json/10125/%20"
DESPACHO_API_URL  = "https://apicloudfruit.cylfruit.com/produccion/cb/CB_GenerarDataReportes/InformeDespachoFrutaPuerto/1/%20/%20/%20/json/10125/0/%20/%20/%20/&20/%20/%20/DFP/%20/%20/%20/%20/false"
TIMEOUT_S         = 150
DIAS_ATRAS        = 2
DIAS_ADELANTE     = 7
MAX_CAJAS_VALID   = 100000
TIPOS_NAVE        = {"MARITIMO": "Marítimo", "AEREO": "Aéreo", "TERRESTRE": "Terrestre", "CHARTER": "Chárter"}
EXCLUIR_TIPO_NAVE = ("CAJAS MUESTRA", "SINIESTRO", "VENTA NACIONAL")

MAP = {
    "fecha_carga":  ["FechaCarga", "fechaCarga"],
    "planilla":     ["NumeroPlanilla", "numeroPlanilla"],
    "codnave":      ["CodNave", "codNave"],
    "recibidor":    ["NomRecibidor", "nomRecibidor"],
    "transportista":["NomTransportista", "nomTransportista"],
    "tipo_nave":    ["NomTipoNave", "nomTipoNave"],
    "puerto":       ["NomPuertoArribo", "nomPuertoArribo", "NomPuertoDestino", "NomPuerto"],
    "naviera":      ["NomNaviera", "nomNaviera"],
    "nave":         ["NomNave", "nomNave"],
    "especie":      ["NomEspecie", "nomEspecie"],
    "cajas":        ["CantidadCajas", "cantidadCajas"],
}
# ───────────────────────────────────────────────────────────────

try:
    from zoneinfo import ZoneInfo
    def ahora():
        return datetime.datetime.now(ZoneInfo("America/Santiago")).replace(tzinfo=None)
except Exception:                                   # sin base de zonas: UTC-3
    def ahora():
        return datetime.datetime.utcnow() - datetime.timedelta(hours=3)


def norm(s):
    s = unicodedata.normalize("NFD", str(s or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").upper().strip()


def pick(rec, key):
    for cand in MAP[key]:
        if cand in rec and rec[cand] not in (None, ""):
            return rec[cand]
    return ""


def parse_dt(s):
    if not s:
        return None
    s = str(s).strip().replace("Z", "")
    try:
        return datetime.datetime.fromisoformat(s[:19])
    except Exception:
        for fmt, n in (("%d-%m-%Y %H:%M:%S", 19), ("%d-%m-%Y", 10), ("%d/%m/%Y %H:%M:%S", 19), ("%d/%m/%Y", 10)):
            try:
                return datetime.datetime.strptime(s[:n], fmt)
            except Exception:
                continue
    return None


def to_int(v):
    try:
        return int(float(v))
    except Exception:
        try:
            return int(float(str(v).replace(".", "").replace(",", ".")))
        except Exception:
            return 0


# ─────────────────────────── SDT ───────────────────────────
def sdt(url):
    u, p = os.environ.get("SDT_USUARIO", ""), os.environ.get("SDT_CLAVE", "")
    if not u or not p:
        raise RuntimeError("Faltan los secretos SDT_USUARIO y SDT_CLAVE.")
    h = {"Accept": "application/json", "Authorization": "Basic " + base64.b64encode(("%s:%s" % (u, p)).encode("utf-8")).decode("ascii")}
    with urllib.request.urlopen(urllib.request.Request(url, method="GET", headers=h), timeout=TIMEOUT_S) as r:
        data = json.loads(r.read().decode("utf-8"))
    cols = []
    if isinstance(data, dict):
        cols = [c.strip() for c in str(data.get("Columns") or "").split(",") if c.strip()]
        for k in ("Data", "data", "value", "result", "items"):
            if isinstance(data.get(k), list):
                return data[k], cols
        raise ValueError("SDT devolvio un objeto sin lista de registros.")
    if isinstance(data, list):
        return data, cols
    raise ValueError("Formato de respuesta inesperado de SDT.")


def armar_despachos(registros, despachados):
    """Una fila por orden de embarque (CodNave + planilla), con sus especies."""
    excluir = set(norm(x) for x in EXCLUIR_TIPO_NAVE)
    hoy = ahora().date()
    desde, hasta = hoy - datetime.timedelta(days=DIAS_ATRAS), hoy + datetime.timedelta(days=DIAS_ADELANTE)
    out = {}
    for rec in registros:
        tnave = str(pick(rec, "tipo_nave")).strip()
        if norm(tnave) in excluir:
            continue
        dt = parse_dt(pick(rec, "fecha_carga"))
        if dt is None or not (desde <= dt.date() < hasta):
            continue
        cn, pl = str(pick(rec, "codnave")).strip(), str(pick(rec, "planilla")).strip()
        did = "-".join(x for x in (cn, pl) if x) or dt.isoformat()
        did = "".join(c if (c.isalnum() or c in "-_") else "_" for c in did)
        cajas = to_int(pick(rec, "cajas"))
        cajas = cajas if 0 <= cajas <= MAX_CAJAS_VALID else 0
        esp = str(pick(rec, "especie")).strip()
        d = out.get(did)
        if d is None:
            sin_hora = dt.hour == 0 and dt.minute == 0
            d = out[did] = {
                "id": did, "codnave": cn, "planilla": pl, "fecha": dt.date().isoformat(),
                "hora": "" if sin_hora else dt.strftime("%H:%M"), "tipoNave": TIPOS_NAVE.get(norm(tnave), tnave.title()),
                "puerto": str(pick(rec, "puerto")).strip(),
                "naviera": str(pick(rec, "naviera")).strip(), "nave": str(pick(rec, "nave")).strip(),
                "recibidor": str(pick(rec, "recibidor")).strip(), "transportista": str(pick(rec, "transportista")).strip(),
                "especies": [], "cajas": 0,
                "cargado": bool(despachados is not None and cn and cn in despachados),
            }
        if esp and esp not in d["especies"]:
            d["especies"].append(esp)
        d["cajas"] += cajas
    return sorted(out.values(), key=lambda x: (x["fecha"], x["hora"] or "99", x["id"]))


# ─────────────────────────── SharePoint (Microsoft Graph) ───────────────────────────
class Graph:
    def __init__(self):
        t, c, s = (os.environ.get(k, "") for k in ("GRAPH_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET"))
        if not (t and c and s):
            raise RuntimeError("Faltan los secretos GRAPH_TENANT_ID, GRAPH_CLIENT_ID y GRAPH_CLIENT_SECRET.")
        body = urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": c, "client_secret": s,
                                       "scope": "https://graph.microsoft.com/.default"}).encode()
        with urllib.request.urlopen(urllib.request.Request("https://login.microsoftonline.com/%s/oauth2/v2.0/token" % t, data=body), timeout=60) as r:
            self.token = json.loads(r.read().decode())["access_token"]
        m = urllib.parse.urlparse(SP_SITIO)
        self.site = self.call("GET", "/sites/%s:%s" % (m.netloc, m.path))["id"]
        listas = self.call("GET", "/sites/%s/lists?$select=id,displayName&$top=200" % self.site)["value"]
        self.lista = next((l["id"] for l in listas if l["displayName"] == LISTA), None)
        if not self.lista:
            raise RuntimeError("No existe la lista %s en el sitio: abre la app web una vez para que la cree." % LISTA)
        items = self.call("GET", "/sites/%s/lists/%s/items?$expand=fields($select=Title)&$top=999" % (self.site, self.lista))["value"]
        self.ids = {(i.get("fields") or {}).get("Title"): i["id"] for i in items}

    def call(self, method, path, body=None):
        url = path if path.startswith("http") else "https://graph.microsoft.com/v1.0" + urllib.parse.quote(path, safe="/:?=&$(),")
        h = {"Authorization": "Bearer " + self.token, "Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            h["Content-Type"] = "application/json"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method, headers=h), timeout=60) as r:
                t = r.read().decode("utf-8")
                return json.loads(t) if t else None
        except urllib.error.HTTPError as e:
            raise RuntimeError("Graph %s en %s: %s" % (e.code, path.split("?")[0], e.read().decode("utf-8", "ignore")[:300]))

    def guardar(self, clave, valor):
        txt = json.dumps(valor, ensure_ascii=False)
        if clave in self.ids:
            self.call("PATCH", "/sites/%s/lists/%s/items/%s/fields" % (self.site, self.lista, self.ids[clave]), {"Valor": txt})
        else:
            j = self.call("POST", "/sites/%s/lists/%s/items" % (self.site, self.lista), {"fields": {"Title": clave, "Valor": txt}})
            self.ids[clave] = j["id"]


def main():
    g = Graph()
    marca = ahora().strftime("%d-%m-%Y %H:%M")
    try:
        regs, cols = sdt(ORDENES_API_URL)
        desp = None
        if DESPACHO_API_URL:
            dregs, _ = sdt(DESPACHO_API_URL)
            desp = set(str(pick(x, "codnave")).strip() for x in dregs if pick(x, "codnave"))
        lista = armar_despachos(regs, desp)
    except Exception as e:
        g.guardar("sdt", {"ok": False, "at": "", "intento": marca, "error": str(e)[:300], "columnas": []})
        print("ERROR al leer SDT: %s" % e)
        sys.exit(1)
    g.guardar("despachos", lista)
    g.guardar("sdt", {"ok": True, "at": marca, "intento": marca, "error": "", "columnas": cols})
    print("OK: %d ordenes de embarque guardadas en SharePoint (%s)." % (len(lista), marca))


if __name__ == "__main__":
    main()
