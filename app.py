# Sky para Streamlit Community Cloud. Ejecutar: streamlit run app.py
import os
import hmac
import uuid
from collections import Counter
from pathlib import Path
import streamlit as st
from config import configurar_secrets_streamlit

st.set_page_config(page_title='Sky — Agente de IA para Almacén',page_icon='📦',layout='wide',initial_sidebar_state='expanded')
configurar_secrets_streamlit(st)

# Nunca servir inventario si falta una contraseña de acceso al despliegue.
if not os.environ.get('APP_PASSWORD'):
    st.error('Falta configurar APP_PASSWORD en los secretos de Streamlit Cloud.')
    st.stop()

if not st.session_state.get('autorizado', False):
    st.title('🔐 Acceso a Sky')
    with st.form('login'):
        clave=st.text_input('Contraseña de acceso',type='password')
        enviar=st.form_submit_button('Entrar',use_container_width=True)
    if enviar:
        if hmac.compare_digest(clave,os.environ['APP_PASSWORD']):
            st.session_state.autorizado=True
            st.rerun()
        else: st.error('Contraseña incorrecta')
    st.stop()

# Estas estructuras están aisladas en st.session_state, NO son SQLite persistente.
if 'conversaciones' not in st.session_state:st.session_state.conversaciones={}
if 'chat_actual' not in st.session_state:st.session_state.chat_actual=None
if 'tema' not in st.session_state:st.session_state.tema='Negro AMOLED'

TEMAS={
 'Negro AMOLED':('#000000','#101010','#f4f4f4','#202020'),
 'Azul medianoche':('#111927','#192335','#e8eef8','#243249'),
 'Gris grafito':('#181a1e','#22252b','#f1f3f5','#30343b'),
 'Blanco minimalista':('#f7f7f8','#ffffff','#202633','#e9edf3'),
}
# Estilo deliberadamente acotado a contenedores de Streamlit.
fondo,panel,texto,burbuja=TEMAS[st.session_state.tema]
st.markdown(f'''<style>
.stApp{{background:{fondo};color:{texto}}}
[data-testid="stSidebar"]{{background:{panel}}}
[data-testid="stChatMessage"]{{background:{burbuja};border-radius:14px;margin-bottom:7px}}
</style>''',unsafe_allow_html=True)

with st.sidebar:
    st.title('📦 Sky')
    st.caption('Agente de IA para Almacén · Streamlit')
    st.selectbox('🎨 Apariencia',list(TEMAS),key='tema')
    if st.button('＋ Nuevo chat',use_container_width=True):
        st.session_state.chat_actual=None
        st.rerun()
    st.divider()
    st.caption('CONVERSACIONES DE ESTA SESIÓN')
    for chat_id, datos in reversed(list(st.session_state.conversaciones.items())):
        c1,c2=st.columns([5,1])
        with c1:
            if st.button(datos['titulo'][:38],key='abrir_'+chat_id,use_container_width=True):
                st.session_state.chat_actual=chat_id
                st.rerun()
        with c2:
            if st.button('🗑',key='borrar_'+chat_id,help='Eliminar conversación de esta sesión'):
                st.session_state.conversaciones.pop(chat_id,None)
                if st.session_state.chat_actual==chat_id:st.session_state.chat_actual=None
                st.rerun()
    st.divider()
    if st.button('Cerrar sesión',use_container_width=True):
        for k in ('autorizado','conversaciones','chat_actual'):
            st.session_state.pop(k,None)
        st.rerun()
    st.caption('Demo protegida. Los chats no son permanentes; Gmail está desactivado.')

pagina=st.tabs(['💬 Asistente IA','📊 Indicadores','📄 Reportes PDF'])
with pagina[0]:
    st.header('Sky — Tu asistente de almacén')
    st.caption('Consulta inventario, Kardex, clasificación ABC, stock bajo y consumo.')
    chat=st.session_state.conversaciones.get(st.session_state.chat_actual)
    if chat:
        for msg in chat['mensajes']:
            with st.chat_message('assistant' if msg['rol']=='sky' else 'user'):
                st.markdown(msg['texto'])
                for pdf in msg.get('pdfs',[]):
                    if Path(pdf).is_file():
                        st.download_button('⬇️ '+Path(pdf).name,data=Path(pdf).read_bytes(),file_name=Path(pdf).name,mime='application/pdf',key='pdf_'+str(msg['id'])+'_'+Path(pdf).name)
    else: st.info('Bienvenido. Este chat se guardará en la sesión después de enviar tu primera pregunta.')
    pregunta=st.chat_input('Pregúntale a Sky sobre tu almacén...')
    if pregunta:
        if not os.getenv('GROQ_API_KEY') or not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_KEY'):
            st.error('Faltan las claves de Groq o Supabase en Streamlit Secrets.')
        else:
            if chat is None:
                cid=str(uuid.uuid4())
                chat={'titulo':pregunta[:45],'mensajes':[],'contexto':[]}
                st.session_state.conversaciones[cid]=chat
                st.session_state.chat_actual=cid
            chat['mensajes'].append({'id':str(uuid.uuid4()),'rol':'usuario','texto':pregunta})
            with st.spinner('Sky está analizando tu consulta...'):
                try:
                    from agente import responder
                    respuesta,historial,pdfs=responder(pregunta,chat['contexto'])
                    chat['contexto']=historial
                    chat['mensajes'].append({'id':str(uuid.uuid4()),'rol':'sky','texto':respuesta,'pdfs':[str(x) for x in pdfs]})
                except Exception:
                    chat['mensajes'].append({'id':str(uuid.uuid4()),'rol':'sky','texto':'No se pudo realizar la consulta. Verifica conexión y configuración; consulta los logs del servidor.'})
            st.rerun()

with pagina[1]:
    st.header('📊 Panel de inventario')
    st.caption('Lecturas en tiempo real de Supabase; nunca modifica existencias.')
    if st.button('Actualizar indicadores'):
        st.session_state.pop('indicadores_cargados',None)
    if 'indicadores_cargados' not in st.session_state:
        try:
            from herramientas_inventario import consultar_resumen_inventario, consultar_valor_inventario, consultar_stock_bajo
            st.session_state.indicadores_cargados=(consultar_resumen_inventario(), consultar_valor_inventario(), consultar_stock_bajo())
        except Exception:
            st.session_state.indicadores_cargados=({'error':'Error de conexión'},{},{})
    resumen,valor,bajos=st.session_state.indicadores_cargados
    if 'error' in resumen: st.error('No se pudieron cargar los indicadores de Supabase.')
    else:
        a,b,c=st.columns(3)
        a.metric('Productos distintos',resumen.get('total_productos_distintos','—'))
        b.metric('Unidades almacenadas',f"{resumen.get('total_unidades_stock',0):,.0f}")
        c.metric('Valor del inventario',f"S/ {valor.get('valor_inventario_soles',0):,.2f}")
        registros=bajos.get('productos',[]) if isinstance(bajos,dict) else []
        if registros:
            st.subheader('Productos con stock bajo')
            st.dataframe(registros,use_container_width=True,hide_index=True)
        else: st.info('No hay productos de stock bajo en la respuesta o no se pudo consultar esa vista.')
with pagina[2]:
    st.header('📄 Generación de reportes')
    st.caption('Descarga el documento desde tu navegador; Gmail no está disponible en esta demo.')
    opciones={'Inventario general':'inventario','Stock bajo':'stock_bajo','ABC monetario':'abc_monetario','ABC por movimientos':'abc_movimientos'}
    tipo_etiqueta=st.selectbox('Tipo de informe',list(opciones))
    if st.button('Generar PDF',type='primary'):
        if not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_KEY'):
            st.error('Faltan las credenciales de Supabase.')
        else:
            try:
                import agente_inventario as ia
                import threading
                from agente import _LOCK
                with _LOCK: d=ia.generar_reporte_pdf(opciones[tipo_etiqueta])
                if d.get('ok'):
                    path=Path(d['ruta'])
                    st.download_button('⬇️ Descargar '+path.name,path.read_bytes(),file_name=path.name,mime='application/pdf')
                else:st.error(str(d.get('error','No se generó el archivo.')))
            except Exception:st.error('No se pudo generar el reporte. Verifica los logs del servidor.')
