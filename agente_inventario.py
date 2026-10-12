"""T22 - Agente conversacional con consultas y reportes PDF.
Ejecutar: python agente_inventario.py
Requiere: herramientas_inventario.py, instrucciones_agente.py y .env.
"""
import json
import os
import re
from datetime import date, datetime, timedelta
from openai import OpenAI
from dotenv import load_dotenv

from instrucciones_agente import INSTRUCCIONES_AGENTE
from herramientas_inventario import (
    consultar_producto,
    consultar_stock_bajo,
    consultar_movimientos,
    consultar_kardex,
    consultar_abc,
    consultar_resumen_inventario,
    consultar_valor_inventario,
    consultar_todos_productos,
    consultar_kardex_general,
    analizar_consumo,
    comparar_consumo,
    analizar_sobrestock,
    analizar_inventario_sin_salidas,
    recomendar_reposicion,
    auditar_calidad_inventario,
)

from generador_reportes import (
    generar_reporte_stock_bajo,
    generar_reporte_inventario,
    generar_reporte_movimientos,
    generar_reporte_kardex,
    generar_reporte_kardex_general,
    generar_reporte_abc,
)
from pathlib import Path
def enviar_pdf(*args, **kwargs):
    raise RuntimeError("El envío por Gmail está desactivado en la versión pública.")

# Una solicitud pendiente como máximo; ejecución local de un usuario.
pendiente = None
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
CONFIRMACIONES = {"si confirmo", "sí confirmo", "confirmo el envio", "confirmo el envío", "confirmar envio", "confirmar envío"}
CANCELACIONES = {"cancelar", "no", "no enviar", "cancela el envio", "cancela el envío"}


def preparar_correo_pdf(destinatario, tipo, fecha_inicio=None, fecha_fin=None, codigo=None, clasificacion="TODAS"):
    """Genera y pone en espera un PDF. No envía correos."""
    global pendiente
    if not isinstance(destinatario, str) or len(destinatario) > 254 or not EMAIL.fullmatch(destinatario.strip()):
        return {"error": "Indica una dirección de correo válida en la solicitud."}
    resultado = generar_reporte_pdf(tipo, fecha_inicio, fecha_fin, codigo, clasificacion)
    if not resultado.get("ok"):
        return resultado
    pendiente = {"destinatario": destinatario.strip(), "ruta": resultado["ruta"],
                 "archivo": resultado["archivo"], "vence": datetime.now() + timedelta(minutes=15)}
    return {"ok": True, "pendiente_confirmacion": True, "destinatario": pendiente["destinatario"],
            "archivo": pendiente["archivo"], "ruta": pendiente["ruta"]}


def generar_reporte_pdf(tipo, fecha_inicio=None, fecha_fin=None,
                        codigo=None, clasificacion="TODAS"):
    """Genera un PDF autorizado. No modifica datos ni envía correos."""
    if tipo not in {"inventario", "stock_bajo", "entradas", "salidas", "kardex",
                    "abc_monetario", "abc_movimientos", "kardex_general"}:
        return {"error": "Tipo de reporte no admitido."}

    if tipo in {"entradas", "salidas", "kardex", "kardex_general"}:
        if not fecha_inicio or not fecha_fin:
            return {"error": "Indica fecha inicial y final con formato AAAA-MM-DD."}
        try:
            inicio = date.fromisoformat(fecha_inicio)
            fin = date.fromisoformat(fecha_fin)
            if inicio > fin:
                return {"error": "La fecha inicial no puede superar a la final."}
        except (ValueError, TypeError):
            return {"error": "Las fechas deben tener formato AAAA-MM-DD y ser válidas."}

    if tipo == "kardex":
        if not isinstance(codigo, str) or not codigo.strip():
            return {"error": "Indica el código exacto del producto para el Kardex."}
        if len(codigo) > 80:
            return {"error": "El código del producto es demasiado largo."}

    if tipo.startswith("abc_"):
        if not isinstance(clasificacion, str) or clasificacion.upper() not in {"A", "B", "C", "TODAS"}:
            return {"error": "La clasificación debe ser A, B, C o TODAS."}

    try:
        if tipo == "inventario":
            ruta = generar_reporte_inventario()
        elif tipo == "stock_bajo":
            ruta = generar_reporte_stock_bajo()
        elif tipo in {"entradas", "salidas"}:
            ruta = generar_reporte_movimientos(tipo, fecha_inicio, fecha_fin)
        elif tipo == "kardex":
            ruta = generar_reporte_kardex(codigo.strip().upper(), fecha_inicio, fecha_fin)
        elif tipo == "kardex_general":
            ruta = generar_reporte_kardex_general(fecha_inicio, fecha_fin)
        else:
            subtipo = "monetario" if tipo == "abc_monetario" else "movimientos"
            ruta = generar_reporte_abc(subtipo, clasificacion.upper())
        archivo = Path(ruta)
        if not archivo.is_file() or archivo.suffix.lower() != ".pdf":
            return {"error": "El generador no produjo un archivo PDF válido."}
        return {"ok": True, "tipo": tipo, "archivo": archivo.name, "ruta": str(archivo.resolve())}
    except Exception as exc:
        return {"error": f"No se pudo generar el PDF: {exc}"}


load_dotenv()
API_KEY = os.getenv('GROQ_API_KEY')
MODELO = os.getenv('LLM_MODEL', 'openai/gpt-oss-20b')
if not API_KEY:
    raise RuntimeError('Falta GROQ_API_KEY en el archivo .env')

cliente = OpenAI(
    api_key=API_KEY,
    base_url='https://api.groq.com/openai/v1',
    timeout=45.0,
    max_retries=1,
)

# La herramienta de correo SOLO prepara un envío. El envío ocurre fuera del modelo
# después de una confirmación textual exacta del usuario.
FUNCIONES = {
    'consultar_producto': consultar_producto,
    'consultar_stock_bajo': consultar_stock_bajo,
    'consultar_movimientos': consultar_movimientos,
    'consultar_kardex': consultar_kardex,
    'consultar_abc': consultar_abc,
    'consultar_resumen_inventario': consultar_resumen_inventario,
    'consultar_valor_inventario': consultar_valor_inventario,
    'consultar_todos_productos': consultar_todos_productos,
    'consultar_kardex_general': consultar_kardex_general,
    'analizar_consumo': analizar_consumo,
    'comparar_consumo': comparar_consumo,
    'analizar_sobrestock': analizar_sobrestock,
    'analizar_inventario_sin_salidas': analizar_inventario_sin_salidas,
    'recomendar_reposicion': recomendar_reposicion,
    'auditar_calidad_inventario': auditar_calidad_inventario,
    'generar_reporte_pdf': generar_reporte_pdf,
    # Gmail deshabilitado en la nube por seguridad.
}

HERRAMIENTAS = [
    {'type': 'function', 'function': {
        'name': 'auditar_calidad_inventario',
        'description': ('Audita calidad del catálogo: precios, stock negativo, mínimos/máximos, '
                        'ubicaciones y proveedores faltantes; opcionalmente coherencia de movimientos '
                        'de Kardex si se proporcionan ambas fechas. Solo lectura. '
                        'Para diagnóstico general NO necesita fechas.'),
        'parameters': {'type': 'object', 'properties': {
            'fecha_inicio': {'type': 'string', 'description': 'AAAA-MM-DD, junto con fecha_fin, opcional'},
            'fecha_fin': {'type': 'string', 'description': 'AAAA-MM-DD, junto con fecha_inicio, opcional'},
            'limite': {'type': 'integer', 'minimum': 1, 'maximum': 100},
        }, 'additionalProperties': False},
    }},
    {'type': 'function', 'function': {
        'name': 'recomendar_reposicion',
        'description': ('Propone reposición sin comprar. Método minmax utiliza mínimos y máximos del catálogo; '
                        'método demanda usa salidas históricas y exige dias_entrega dado expresamente '
                        'por el usuario (nunca inventarlo). No asume pedidos en tránsito.'),
        'parameters': {'type': 'object', 'properties': {
            'metodo': {'type': 'string', 'enum': ['minmax', 'demanda']},
            'dias_entrega': {'type': 'integer', 'minimum': 1, 'maximum': 365},
            'dias_historial': {'type': 'integer', 'minimum': 7, 'maximum': 365},
            'limite': {'type': 'integer', 'minimum': 1, 'maximum': 100},
        }, 'additionalProperties': False},
    }},
    {'type': 'function', 'function': {
        'name': 'analizar_sobrestock',
        'description': ('Detecta productos cuyo stock actual supera el stock maximo configurado; '
                        'calcula unidades excedentes y valor excedente a precio de compra. '
                        'No necesita fechas. Es distinto de productos sin salidas.'),
        'parameters': {'type': 'object', 'properties': {
            'limite': {'type': 'integer', 'minimum': 1, 'maximum': 100},
        }, 'additionalProperties': False},
    }},
    {'type': 'function', 'function': {
        'name': 'analizar_inventario_sin_salidas',
        'description': ('Diagnostica productos con existencias actuales positivas SIN salidas '
                        'ordinarias en el periodo y valoriza el stock; no confundir con '
                        'obsolescencia, perdidas o sobrestock. Necesita fechas de inicio y fin.'),
        'parameters': {'type': 'object', 'properties': {
            'fecha_inicio': {'type': 'string', 'description': 'AAAA-MM-DD'},
            'fecha_fin': {'type': 'string', 'description': 'AAAA-MM-DD inclusive'},
            'limite': {'type': 'integer', 'minimum': 1, 'maximum': 100},
        }, 'required': ['fecha_inicio','fecha_fin'], 'additionalProperties': False},
    }},
    {'type': 'function', 'function': {
        'name': 'analizar_consumo',
        'description': ('Analiza salidas de unidades por producto en un periodo. Rankings mayor/menor, '
                        'productos sin salidas, promedio diario; no es rotación contable. '
                        'Modo menor excluye productos con cero; para cero usa sin_salidas.'),
        'parameters': {'type': 'object', 'properties': {
            'fecha_inicio': {'type': 'string', 'description': 'AAAA-MM-DD'},
            'fecha_fin': {'type': 'string', 'description': 'AAAA-MM-DD inclusive'},
            'modo': {'type': 'string', 'enum': ['mayor', 'menor', 'sin_salidas', 'todos']},
            'limite': {'type': 'integer', 'minimum': 1, 'maximum': 100},
        }, 'required': ['fecha_inicio', 'fecha_fin'], 'additionalProperties': False},
    }},
    {'type': 'function', 'function': {
        'name': 'comparar_consumo',
        'description': ('Compara salidas de unidades de dos periodos. Emplea promedio diario para '
                        'porcentaje entre periodos de duraciones diferentes.'),
        'parameters': {'type': 'object', 'properties': {
            'inicio_1': {'type': 'string', 'description': 'AAAA-MM-DD inicio primer periodo'},
            'fin_1': {'type': 'string', 'description': 'AAAA-MM-DD fin primer periodo'},
            'inicio_2': {'type': 'string', 'description': 'AAAA-MM-DD inicio segundo periodo'},
            'fin_2': {'type': 'string', 'description': 'AAAA-MM-DD fin segundo periodo'},
            'limite': {'type': 'integer', 'minimum': 1, 'maximum': 100},
        }, 'required': ['inicio_1', 'fin_1', 'inicio_2', 'fin_2'], 'additionalProperties': False},
    }},

{'type': 'function', 'function': {
    'name': 'consultar_valor_inventario',
    'description': 'Calcula la valorización monetaria total del inventario en soles: suma de stock actual por precio de compra; no es total de ventas.',
    'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False}
}},
    {'type': 'function', 'function': {
        'name': 'consultar_todos_productos',
        'description': 'Lista TODOS los productos registrados en el almacén, sin nombre ni código de búsqueda. Para solicitudes de lista completa usa esta función sin pedir filtros.',
        'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False}
    }},
    {'type': 'function', 'function': {
        'name': 'consultar_resumen_inventario',
        'description': 'Cuenta productos distintos (códigos únicos) y unidades totales del inventario. Úsala para cuántos productos hay.',
        'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False}
    }},
    {'type': 'function', 'function': {
        'name': 'consultar_kardex_general',
        'description': 'Consulta movimientos de Kardex de TODOS los productos en un rango de fechas. No necesita código de producto.',
        'parameters': {'type': 'object', 'properties': {
            'fecha_inicio': {'type': 'string', 'description': 'AAAA-MM-DD'},
            'fecha_fin': {'type': 'string', 'description': 'AAAA-MM-DD'}
        }, 'required': ['fecha_inicio', 'fecha_fin'], 'additionalProperties': False}
    }},
    {
        'type': 'function',
        'function': {
            'name': 'consultar_producto',
            'description': 'Busca productos del inventario por nombre o código.',
            'parameters': {
                'type': 'object',
                'properties': {'texto': {'type': 'string', 'description': 'Texto de búsqueda'}},
                'required': ['texto'],
                'additionalProperties': False,
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_stock_bajo',
            'description': 'Obtiene los productos con stock bajo desde la vista de Supabase.',
            'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False},
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_movimientos',
            'description': 'Resume entradas o salidas durante un periodo. Distingue operaciones y líneas de detalle.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'tipo': {'type': 'string', 'enum': ['entradas', 'salidas']},
                    'fecha_inicio': {'type': 'string', 'description': 'AAAA-MM-DD'},
                    'fecha_fin': {'type': 'string', 'description': 'AAAA-MM-DD'},
                },
                'required': ['tipo', 'fecha_inicio', 'fecha_fin'],
                'additionalProperties': False,
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_kardex',
            'description': 'Consulta Kardex de un producto por código y rango de fechas.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'codigo': {'type': 'string'},
                    'fecha_inicio': {'type': 'string', 'description': 'AAAA-MM-DD'},
                    'fecha_fin': {'type': 'string', 'description': 'AAAA-MM-DD'},
                },
                'required': ['codigo', 'fecha_inicio', 'fecha_fin'],
                'additionalProperties': False,
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_abc',
            'description': 'Consulta clasificación ABC monetaria o por movimientos.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'tipo': {'type': 'string', 'enum': ['monetario', 'movimientos']},
                    'clasificacion': {'type': 'string', 'enum': ['A', 'B', 'C', 'TODAS']},
                },
                'required': ['tipo', 'clasificacion'],
                'additionalProperties': False,
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'generar_reporte_pdf',
            'description': ('Genera y guarda un archivo PDF en la carpeta reportes. '
                            'Usar SOLO cuando el usuario pida explícitamente generar, crear, '
                            'guardar o descargar un PDF/reporte. '
                            'Para entradas, salidas y Kardex requiere rango de fechas; '
                            'para Kardex individual requiere código exacto; para Kardex general NO requiere código. '
                            'Si falta algún dato, pregunta antes de llamar. '
                            'No sirve para enviar correos.'),
            'parameters': {
                'type': 'object',
                'properties': {
                    'tipo': {'type': 'string', 'enum': [
                        'inventario', 'stock_bajo', 'entradas', 'salidas',
                        'kardex', 'kardex_general', 'abc_monetario', 'abc_movimientos']},
                    'fecha_inicio': {'type': 'string', 'description': 'AAAA-MM-DD. Obligatorio en entradas, salidas y kardex.'},
                    'fecha_fin': {'type': 'string', 'description': 'AAAA-MM-DD inclusive. Obligatorio en entradas, salidas y kardex.'},
                    'codigo': {'type': 'string', 'description': 'Código exacto únicamente para Kardex individual; omitir para kardex_general.'},
                    'clasificacion': {'type': 'string', 'enum': ['A', 'B', 'C', 'TODAS']},
                },
                'required': ['tipo'],
                'additionalProperties': False,
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'preparar_correo_pdf',
            'description': ('Prepara PDF para enviarlo por Gmail cuando el usuario pide explícitamente enviar '
                            'un reporte a una dirección de correo indicada. SOLO prepara y pide confirmación; '
                            'NUNCA envía. Solicita campos faltantes antes de llamar.'),
            'parameters': {
                'type': 'object',
                'properties': {
                    'destinatario': {'type': 'string', 'description': 'Email escrito explícitamente por el usuario'},
                    'tipo': {'type': 'string', 'enum': ['inventario','stock_bajo','entradas','salidas','kardex','kardex_general','abc_monetario','abc_movimientos']},
                    'fecha_inicio': {'type': 'string', 'description': 'AAAA-MM-DD si se requiere'},
                    'fecha_fin': {'type': 'string', 'description': 'AAAA-MM-DD si se requiere'},
                    'codigo': {'type': 'string', 'description': 'Código exacto si Kardex'},
                    'clasificacion': {'type': 'string', 'enum': ['A','B','C','TODAS']},
                },
                'required': ['destinatario','tipo'],
                'additionalProperties': False,
            },
        },
    },
]


# El modelo no debe poder solicitar preparaciones de correo desde la versión pública.
HERRAMIENTAS = [h for h in HERRAMIENTAS if h['function']['name'] != 'preparar_correo_pdf']

def ejecutar_herramienta(nombre, argumentos):
    """Ejecuta exclusivamente funciones permitidas con errores controlados."""
    funcion = FUNCIONES.get(nombre)
    if funcion is None:
        return {'error': 'Herramienta no autorizada'}
    try:
        return funcion(**argumentos)
    except (ValueError, TypeError) as exc:
        return {'error': f'Argumentos inválidos: {exc}'}
    except Exception:
        return {'error': 'No se pudo completar la consulta.'}


def reducir_resultado(nombre, resultado):
    """Limita datos enviados al LLM; mantiene totales, estados y advertencias."""
    if not isinstance(resultado, dict):
        return {'error': 'Respuesta inesperada de la herramienta'}
    salida = dict(resultado)
    # Mantener totales de la herramienta; limitar los registros individuales.
    if isinstance(salida.get('productos'), list):
        n = len(salida['productos'])
        salida['productos'] = salida['productos'][:12]
        salida['filas_enviadas_al_modelo'] = min(n, 12)
        if n > 12:
            salida['nota_llm'] = 'Solo se envió una muestra de 12 filas al modelo; no afirma que sea el listado completo.'
    if nombre in ('analizar_consumo', 'comparar_consumo') and isinstance(salida.get('productos'), list):
        salida['productos'] = salida['productos'][:12]
    if isinstance(salida.get('hallazgos'), list):
        salida['hallazgos'] = salida['hallazgos'][:12]
    if isinstance(salida.get('productos_resumen'), list):
        salida['productos_resumen'] = salida['productos_resumen'][:15]
    if isinstance(salida.get('movimientos'), list):
        n = len(salida['movimientos'])
        salida['movimientos'] = salida['movimientos'][:10]
        salida['filas_enviadas_al_modelo'] = min(n, 10)
        if n > 10:
            salida['nota_llm'] = 'Solo se envió una muestra de 10 movimientos al modelo.'
    if isinstance(salida.get('productos_por_lineas'), list):
        salida['productos_por_lineas'] = salida['productos_por_lineas'][:10]
    # Límite de respaldo para evitar error 413 en Groq.
    texto = json.dumps(salida, ensure_ascii=False, default=str)
    if len(texto) > 14000:
        resumen = {k: v for k, v in salida.items() if not isinstance(v, list)}
        resumen['nota_llm'] = 'Demasiados datos para mostrar detalles; usa filtros más específicos.'
        return resumen
    return salida


# Historial de usuario y respuestas finales, sin respuestas extensas de herramientas.
# Se limita tanto por cantidad de turnos como por tamaño total.
MAX_TURNOS = 6
MAX_CARACTERES_HISTORIAL = 4500
historial = []


def preparar_historial():
    """Recupera los últimos turnos completos sin superar el límite."""
    pares = []
    # Cada turno tiene un mensaje del usuario y uno del asistente.
    for i in range(0, len(historial), 2):
        if i + 1 < len(historial):
            pares.append(historial[i:i+2])

    seleccionados = []
    acumulado = 0
    for par in reversed(pares[-MAX_TURNOS:]):
        costo = sum(len(m['content']) for m in par)
        if acumulado + costo > MAX_CARACTERES_HISTORIAL:
            break
        seleccionados.insert(0, par)
        acumulado += costo
    return [m.copy() for par in seleccionados for m in par]


def guardar_turno(pregunta, respuesta):
    """Registra un turno ya finalizado; nunca conserva credenciales ni tool calls."""
    historial.extend([
        {'role': 'user', 'content': pregunta[:1200]},
        {'role': 'assistant', 'content': respuesta[:1800]},
    ])
    if len(historial) > MAX_TURNOS * 2:
        del historial[:-MAX_TURNOS * 2]


def _listar_catalogo_completo():
    """Respuesta completa construida en Python; no consume tokens de Groq."""
    datos = consultar_todos_productos()
    if datos.get('error'):
        return 'No pude recuperar los productos: ' + str(datos['error'])
    productos = datos['productos']
    encabezado = f"### Productos registrados en el almacén ({len(productos)})"
    if not productos:
        return encabezado + '\n\nNo hay productos registrados.'
    lineas = [encabezado, '', '| Código | Producto | Categoría | Stock | Estado |',
              '|:---:|:---:|:---:|---:|:---:|']
    for p in productos:
        def limpio(valor):
            return str(valor if valor is not None else '—').replace('|', '/').replace('\n', ' ')
        lineas.append('| ' + ' | '.join([
            limpio(p.get('cod_producto')),
            limpio(p.get('nombre')),
            limpio(p.get('categoria')),
            limpio(p.get('stock_actual')),
            limpio(p.get('estado_stock')),
        ]) + ' |')
    return '\n'.join(lineas)


def _es_seguimiento(pregunta):
    """Evita que las explicaciones/correcciones disparen atajos por palabras sueltas."""
    import unicodedata
    t = ''.join(c for c in unicodedata.normalize('NFD', pregunta.casefold())
                if unicodedata.category(c) != 'Mn').strip(' ¿?¡!.')
    return bool(re.search(
        r'\b(por que|porque|te equivocaste|estas equivocado|no pedi|no te pedi|'
        r'eso no|no era|no es lo que|respuesta anterior|me respondiste|'
        r'me diste|me das|corrige|explica tu respuesta|no entendiste|'
        r'vuelve a leer|eso esta mal)\b', t))


def _responder_consulta_directa(pregunta):
    """Resuelve intenciones inequívocas sin gastar tokens ni pedir aclaraciones."""
    t = pregunta.casefold().strip()
    # Una aclaración, queja o referencia a la respuesta anterior nunca es una orden de listado.
    if _es_seguimiento(pregunta):
        return None

    # Consultas inequívocas al valor TOTAL del inventario: respuesta exacta sin LLM.
    # No interferir con solicitudes de reportes ni con preguntas de productos individuales.
    normal = ''.join(c for c in __import__('unicodedata').normalize('NFD', t)
                     if __import__('unicodedata').category(c) != 'Mn')
    valor_total = (bool(re.search(r'\b(valor|valorizacion|valuacion|costo|coste)\b', normal))
                   and bool(re.search(r'\b(total|global|general|todo|completo)\b', normal))
                   and bool(re.search(r'\b(inventario|almacen|existencias|stock)\b', normal))
                   and not re.search(r'\b(pdf|reporte|envia|correo|email|descarga|abc|kardex)\b|@', normal))
    if valor_total:
        datos = consultar_valor_inventario()
        if datos.get('error'):
            return 'No pude calcular el valor del inventario: ' + str(datos['error'])
        monto = f"{datos['valor_inventario_soles']:,.2f}"
        respuesta = (f"El **valor monetario total del inventario** es **S/ {monto}** "
                     f"(sobre {datos['total_productos']} productos).\n\n"
                     "Se calculó multiplicando el stock actual de cada producto por su precio de compra registrado.")
        if datos['productos_sin_precio_compra']:
            respuesta += (f"\n\n**Advertencia:** {datos['productos_sin_precio_compra']} "
                          "productos no tienen precio de compra registrado; su valoración se tomó como cero.")
        return respuesta

    # Ubicación o proveedor de un artículo con código expresamente mencionado.
    # No confundir estas preguntas con informes, correos u otras funcionalidades.
    codigo_match = re.search(r'\b[A-Z]{2,5}-\d+\b', pregunta, re.IGNORECASE)
    requiere_campo = ('ubicacion' if re.search(r'\b(ubicacion|donde esta|donde se encuentra|localizacion)\b', normal)
                      else 'proveedor' if re.search(r'\b(proveedor|abastece|suministra)\b', normal)
                      else None)
    if codigo_match and requiere_campo and not re.search(r'\b(pdf|reporte|correo|email|envia|kardex)\b|@', normal):
        codigo = codigo_match.group(0).upper()
        encontrados = consultar_producto(codigo)
        if encontrados.get('error'):
            return 'No pude consultar el producto: ' + str(encontrados['error'])
        p = next((x for x in encontrados.get('productos', [])
                  if str(x.get('cod_producto', '')).upper() == codigo), None)
        if not p:
            return f'No encontré el producto **{codigo}** en Supabase.'
        nombre = p.get('nombre') or codigo
        if requiere_campo == 'ubicacion':
            ubicacion = p.get('ubicacion')
            return (f"El producto **{codigo} — {nombre}** está ubicado en **{ubicacion}**."
                    if ubicacion else f"El producto **{codigo} — {nombre}** no tiene una ubicación registrada.")
        proveedor = p.get('proveedor')
        cod_prov = p.get('cod_proveedor')
        if proveedor:
            return f"El proveedor registrado de **{codigo} — {nombre}** es **{proveedor}**."
        if cod_prov:
            return (f"El producto **{codigo} — {nombre}** tiene el proveedor con código "
                    f"**{cod_prov}**, pero su nombre no está disponible en la consulta.")
        return f"El producto **{codigo} — {nombre}** no tiene un proveedor asociado en los datos consultados."

    # La petición de catálogo completo es inequívoca y debe resolverse sin filtros.
    # No interceptar PDFs, correos, movimientos, ABC ni búsquedas concretas.
    # Solo listar el catálogo ante una solicitud explícita de TODOS los productos.
    # No usar "cuáles son" ni "inventario" como prueba suficiente.
    pide_lista = bool(re.search(r'\b(lista(?:do)?|muestrame|mostrar|dame|ver|ensename|cuales son|quiero|necesito)\b', normal))
    producto_generico = bool(re.search(r'\bproductos?\b', normal))
    totalidad = bool(re.search(r'\b(todos? los productos|lista completa|listado completo|catalogo completo|inventario completo|productos registrados|productos del almacen|productos en el almacen)\b', normal))
    analitica = bool(re.search(r'\b(rotacion|consumo|ranking|top|mayor|menor|mas|menos|movimiento|salidas|entradas|abc|stock bajo|agotados|categoria|proveedor|precio|costos|promedio|frecuencia|sin salidas|reponer|reposicion|sobrestock|comparar|comparacion|ultimos|primeros|mejores|peores)\b', normal))
    excluir = bool(re.search(r'\b(pdf|reporte|descarg|envia|correo|email|kardex)\b|@', normal))
    if pide_lista and producto_generico and totalidad and not analitica and not excluir:
        return _listar_catalogo_completo()
    # Respuesta corta a la aclaración anterior sobre lista completa.
    if t.strip(' .!?¿¡') in {'todos', 'todos los productos', 'lista completa', 'completa'}:
        pares = preparar_historial()
        if pares and any(re.search(r'\b(lista|listado|productos)\b', str(m.get('content','')).casefold()) for m in pares[-2:]):
            return _listar_catalogo_completo()
    if (re.search(r'(cu[aá]ntos?|n[uú]mero|total)', t)
        and re.search(r'productos?', t)
        and re.search(r'(inventario|registrados?|distintos?|almac[eé]n|hay)', t)
        and not re.search(r'(stock bajo|agotados?|categor[ií]a|proveedor)', t)):
        datos = consultar_resumen_inventario()
        if datos.get('error'):
            return 'No pude consultar el total de productos: ' + datos['error']
        return (f"Hay **{datos['total_productos_distintos']} productos distintos** registrados "
                f"en el inventario (códigos únicos).\n\n"
                f"La suma de existencias registradas es **{datos['total_unidades_stock']:g} unidades**.")

    # Las peticiones explícitas de PDF de Kardex general se resuelven sin pedir código.
    pdf_general = ('kardex' in t and re.search(r'(todos|general|completo|cada producto|almac[eé]n)', t)
                   and re.search(r'(pdf|reporte|descarg|gener|crea|guardar)', t)
                   and not re.search(r'(env[ií]a|correo|email|@)', t))
    if pdf_general:
        hoy = date.today()
        if 'este año' in t or 'año actual' in t:
            inicio, fin = date(hoy.year, 1, 1), date(hoy.year, 12, 31)
        elif 'este mes' in t or 'mes actual' in t:
            inicio = hoy.replace(day=1)
            siguiente = date(hoy.year + 1, 1, 1) if hoy.month == 12 else date(hoy.year, hoy.month + 1, 1)
            fin = siguiente - timedelta(days=1)
        else:
            return None  # Solicitudes con otras fechas pasan a herramientas del modelo.
        d = generar_reporte_pdf('kardex_general', inicio.isoformat(), fin.isoformat())
        if not d.get('ok'):
            return 'No se pudo generar el Kardex general: ' + str(d.get('error', 'Error desconocido'))
        return f"PDF generado correctamente: {d['archivo']}\nUbicación: {d['ruta']}"

    general = ('kardex' in t and re.search(r'(todos|general|completo|cada producto|almac[eé]n)', t)
               and not re.search(r'\b[A-Z]{2,5}-\d+\b', pregunta, re.IGNORECASE))
    if general and not re.search(r'\b(pdf|reporte|descarga|env[ií]a|correo)\b', t):
        hoy = date.today()
        if 'este año' in t or 'año actual' in t:
            inicio, fin = date(hoy.year, 1, 1), date(hoy.year, 12, 31)
        elif 'este mes' in t or 'mes actual' in t or not re.search(r'\d{4}-\d{2}-\d{2}|\b(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b', t):
            inicio = hoy.replace(day=1)
            siguiente = date(hoy.year+1, 1, 1) if hoy.month == 12 else date(hoy.year, hoy.month+1, 1)
            fin = siguiente - timedelta(days=1)
        else:
            return None  # Dejar al modelo interpretar fechas específicas.
        d = consultar_kardex_general(inicio.isoformat(), fin.isoformat())
        if d.get('error'):
            return 'No pude consultar el Kardex general: ' + d['error']
        lineas = [f"### Kardex general — {inicio:%d/%m/%Y} al {fin:%d/%m/%Y}",
                  f"**Movimientos:** {d['total_movimientos']} · **Productos con movimientos:** {d['total_productos_con_movimientos']}",
                  f"**Entradas:** {d['cantidad_entradas_sin_ajustes']:g} unidades · **Salidas:** {d['cantidad_salidas_sin_ajustes']:g} unidades · **Ajustes:** {d['total_ajustes_detectados']}"]
        if d['productos_resumen']:
            lineas += ['', '| Código | Producto | Movimientos | Entradas | Salidas |',
                       '|---|---|---:|---:|---:|']
            for row in d['productos_resumen'][:15]:
                nombre = str(row['producto']).replace('|', '/')
                lineas.append(f"| {row['codigo']} | {nombre} | {row['movimientos']} | {row['entradas']:g} | {row['salidas']:g} |")
            if d['total_productos_con_movimientos'] > 15:
                lineas.append('\n*Se muestran 15 productos; el total considera todos los registros consultados.*')
        else:
            lineas.append('\nNo hay movimientos registrados en este periodo.')
        return '\n'.join(lineas)
    return None


def conversar(pregunta):
    """Resuelve consultas y confirmaciones con envío independiente de la IA."""
    global pendiente
    texto_limpio = pregunta.strip().lower().rstrip('.!')
    if pendiente is not None:
        if datetime.now() > pendiente['vence']:
            pendiente = None
            return 'La solicitud de correo caducó. Solicita un reporte nuevo.'
        if texto_limpio in CANCELACIONES:
            pendiente = None
            return 'Envío cancelado. No se envió ningún correo.'
        if texto_limpio in CONFIRMACIONES:
            envio = pendiente
            pendiente = None  # Evitar repetir el envío incluso ante errores de red.
            try:
                resultado = enviar_pdf(envio['destinatario'], envio['ruta'])
                return f"Gmail aceptó el mensaje para {resultado['destinatario']}.\nAdjunto: {resultado['archivo']}\nID: {resultado['id']}"
            except Exception as exc:
                return (f'No pude confirmar que Gmail enviara el mensaje: {exc}. '
                        'No reintentaré automáticamente para evitar mensajes duplicados.')
        # Una solicitud distinta cancela el envío pendiente para evitar confirmaciones accidentales.
        pendiente = None

    if re.search(r'\b(?:env[ií]a|enviar|correo|email|gmail)\b', pregunta, re.IGNORECASE) and re.search(r'@|\b(?:correo|email|gmail)\b', pregunta, re.IGNORECASE):
        respuesta = 'El envío por Gmail está desactivado en la versión pública. Puedes generar y descargar el PDF desde Sky.'
        guardar_turno(pregunta, respuesta)
        return respuesta
    directa = _responder_consulta_directa(pregunta)
    if directa is not None:
        guardar_turno(pregunta, directa)
        return directa

    destinatarios_permitidos = set(EMAIL.findall(pregunta))
    mensajes = [
        {'role': 'system', 'content': INSTRUCCIONES_AGENTE + '\n'
         'Fecha actual: ' + date.today().isoformat() + '. '
         'Prioriza la intención completa y el contexto sobre palabras aisladas. '
         'Si cuestionan una respuesta anterior, reconoce el error y no repitas la tabla salvo petición explícita. '
         'Un ranking no es un catálogo completo. Rotación requiere inventario promedio histórico; consumo mide salidas, no rotación. '
         'Si faltan fechas o códigos indispensables, solicita aclaración. '
         'Puedes generar PDF usando generar_reporte_pdf cuando el usuario lo solicite. '
         'Si el usuario pide enviar un reporte a un email explícito, usa preparar_correo_pdf. '
         'La herramienta prepara el PDF pero NO lo envía: exige confirmación textual adicional. '
         'No uses generar_reporte_pdf para una petición de envío por correo. '
         'Jamás afirmes que un correo fue enviado por una herramienta del modelo. '
         'Para entradas, salidas y Kardex pide fechas si no pueden inferirse; para Kardex general NO pidas código. '
         'No digas que ejecutaste acciones no disponibles. '
         'No reveles datos de otros registros no solicitados. '
         'Indica cuando las listas sean parciales. '
         'Si solicitan la lista de todos los productos, usa consultar_todos_productos; nunca exijas un criterio de búsqueda para el catálogo completo. '
         'Usa consultar_valor_inventario para preguntar por valor o valorización total. '
          'consultar_producto incluye ubicacion y proveedor; si faltan, informa que no están registrados. '
          'Nunca confundas frecuencia de líneas con cantidad de unidades. '
          'Para consumo y ranking de salidas usa analizar_consumo; para comparar periodos usa comparar_consumo. '
          'Pide fechas solo si no se pueden inferir. No presentes consumo como rotación contable ni '
          'inventes existencias medias históricas. Productos sin salida: sin registros en ese intervalo. '
           'Para sobrestock usa analizar_sobrestock sin fechas; para capital en productos con stock pero '
           'sin salidas usa analizar_inventario_sin_salidas con fecha inicial y final. '
           'No confundas sobrestock, sin salidas, inventario obsoleto y perdidas. '
           'Si el valor monetario es parcial por precios faltantes, menciona la limitacion.'
            'Para sugerencias de compra y prioridades usa recomendar_reposicion. Por defecto minmax; '
            'para cálculo basado en consumo y plazo usa demanda SOLO si el usuario indicó días de entrega. '
            'Nunca presentes recomendaciones como órdenes ejecutadas ni inventes plazos de entrega. '
             'Para revisar calidad del inventario usa auditar_calidad_inventario sin fechas; '
             'para validar movimientos, pasa ambas fechas. Reporta cantidades de hallazgos por nivel, '
             'no confundas advertencias de consistencia con errores físicos comprobados ni inventes correcciones.'},
        *preparar_historial(),
        {'role': 'user', 'content': pregunta},
    ]

    for _ in range(3):  # Máximo tres rondas de herramientas.
        pdf_realizados = []
        errores_pdf = []
        correos_preparados = []
        errores_correo = []
        respuesta = cliente.chat.completions.create(
            model=MODELO,
            messages=mensajes,
            tools=HERRAMIENTAS,
            tool_choice='auto',
            temperature=0.1,
            max_completion_tokens=800,
        )
        mensaje = respuesta.choices[0].message
        solicitudes = mensaje.tool_calls or []
        if not solicitudes:
            texto = (mensaje.content or 'El modelo no devolvió una respuesta.').strip()
            guardar_turno(pregunta, texto)
            return texto

        # Convertir llamada de modelo a estructura de mensajes compatible.
        mensajes.append({
            'role': 'assistant',
            'content': mensaje.content,
            'tool_calls': [
                {'id': t.id, 'type': 'function',
                 'function': {'name': t.function.name, 'arguments': t.function.arguments}}
                for t in solicitudes
            ],
        })
        for llamada in solicitudes[:5]:
            try:
                argumentos = json.loads(llamada.function.arguments or '{}')
                if not isinstance(argumentos, dict):
                    raise ValueError('Argumentos no son un objeto')
                if llamada.function.name == 'preparar_correo_pdf' and argumentos.get('destinatario') not in destinatarios_permitidos:
                    datos = {'error': 'Escribe el destinatario completo en tu solicitud actual, sin que el agente lo invente.'}
                else:
                    datos = ejecutar_herramienta(llamada.function.name, argumentos)
            except (ValueError, TypeError, json.JSONDecodeError):
                datos = {'error': 'El modelo proporcionó argumentos inválidos.'}
            if llamada.function.name == 'preparar_correo_pdf':
                if datos.get('pendiente_confirmacion'):
                    correos_preparados.append(datos)
                else:
                    errores_correo.append(datos.get('error', 'No se pudo preparar el correo.'))
            if llamada.function.name == 'generar_reporte_pdf':
                if datos.get('ok'):
                    pdf_realizados.append(datos)
                else:
                    errores_pdf.append(datos.get('error', 'Error al generar el PDF.'))
            reducido = reducir_resultado(llamada.function.name, datos)
            mensajes.append({
                'role': 'tool',
                'tool_call_id': llamada.id,
                'content': json.dumps(reducido, ensure_ascii=False, default=str),
            })
        # Las rutas y la confirmación proceden del resultado real, no de una
        # afirmación del modelo. Evita otra llamada innecesaria al LLM.
        if correos_preparados:
            d = correos_preparados[-1]
            respuesta_previa = (f"PDF preparado: {d['archivo']}\nDestino: {d['destinatario']}\n"
                               "NO se ha enviado ningún correo.\n"
                               "Para enviarlo responde exactamente: SI CONFIRMO\n"
                               "Para cancelar responde: CANCELAR (vence en 15 minutos).")
            guardar_turno(pregunta, respuesta_previa)
            return respuesta_previa
        if errores_correo:
            respuesta_error = 'No se preparó el correo: ' + ' | '.join(errores_correo)
            guardar_turno(pregunta, respuesta_error)
            return respuesta_error
        if pdf_realizados:
            respuesta_pdf = '\n'.join(
                f"PDF generado correctamente: {d['archivo']}\nUbicación: {d['ruta']}"
                for d in pdf_realizados
            )
            if errores_pdf:
                respuesta_pdf += '\nAviso: ' + ' | '.join(errores_pdf)
            guardar_turno(pregunta, respuesta_pdf)
            return respuesta_pdf
        if errores_pdf:
            texto_error = 'No se generó el PDF: ' + ' | '.join(errores_pdf)
            guardar_turno(pregunta, texto_error)
            return texto_error

        # Responder incluso si el modelo solicita más de cinco llamadas: evitar
        # mensajes tool faltantes en el siguiente envío.
        for llamada in solicitudes[5:]:
            mensajes.append({
                'role': 'tool', 'tool_call_id': llamada.id,
                'content': json.dumps({'error': 'Límite de herramientas por turno'})
            })
    return 'Se alcanzó el límite de consultas para esta pregunta. Intenta una pregunta más específica.'


if __name__ == '__main__':
    print('AGENTE DE INVENTARIOS - T23 (consultas, PDF y Gmail con confirmación)')
    print('Escribe /limpiar para reiniciar el historial, o salir para terminar.\n')
    while True:
        pregunta = input('Tú: ').strip()
        if pregunta.lower() in ('salir', 'exit'):
            break
        if pregunta.lower() == '/limpiar':
            pendiente = None
            historial.clear()
            print('Historial temporal borrado.\n')
            continue
        if not pregunta:
            continue
        try:
            print('\nAgente:', conversar(pregunta), '\n')
        except Exception as exc:
            print('\nNo se pudo consultar el modelo:', str(exc), '\n')
