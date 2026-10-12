# Sky — Agente de IA para Almacén (Streamlit)

Versión de demostración en Streamlit Community Cloud basada en los módulos reales de Sky. **No incluye secretos, token Gmail, PDFs anteriores, SQLite ni .venv.**

## Funciones
- Chat con Groq y herramientas de análisis de inventario / Supabase.
- Conversaciones independientes **durante la sesión del navegador** (no son persistentes).
- Dashboard con indicadores reales y listado de stock bajo.
- Descarga de PDF desde el chat y sección de reportes.
- Cuatro apariencias seleccionables.
- Acceso mediante una contraseña compartida para demostración (no equivale a cuentas individuales).

## Limitaciones deliberadas de esta primera publicación
- Gmail y sus autorizaciones están **desactivados** por seguridad.
- La memoria mixta permanente y el historial SQLite del proyecto local **no se migran** aquí; requieren almacenamiento remoto, separación por usuario y autenticación.
- Se usa un lock para aislar el estado global del agente de cada sesión; no está diseñado para mucho tráfico.
- La contraseña compartida no separa permisos de lectura por persona. No lo uses con datos sensibles hasta establecer controles apropiados.
- La generación de gráficos visuales del dashboard difiere de Flask; conserva indicadores y tablas básicos.
- Los PDFs en disco pueden desaparecer cuando Streamlit Cloud reinicia la instancia.

## Publicación rápida
1. **Renueva las credenciales** antiguas si estuvieron en el ZIP original: Groq, Supabase y Gmail; nunca publiques `.env`, `credentials.json` ni `token.json`.
2. Revisa los permisos de Supabase: usa una clave de mínimo privilegio con acceso **solo lectura**, nunca `service_role` para una demo pública.
3. Sube el contenido de esta carpeta a un repositorio **privado** de GitHub; confirma que no hay secretos.
4. En https://share.streamlit.io/ selecciona *Create app* y el repositorio, rama principal y `app.py` como main file.
5. En *App settings -> Secrets* pega los nombres de `.streamlit/secrets.toml.example` con tus valores **reales nuevos**; usa una contraseña larga en `APP_PASSWORD`.
6. Despliega, espera la instalación y entra con esa contraseña. Prueba stock bajo, PDF y consultas con una ventana privada.
7. Para que otras personas accedan, envía el enlace, pero comparte la contraseña por un medio separado.

## Ejecutar localmente (PowerShell)
```powershell
cd "RUTA\Sky_Streamlit_GitHub"
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Guarda variables en .env local o configura .streamlit/secrets.toml (NO subirlo)
.\.venv\Scripts\python.exe -m streamlit run app.py
```

La app Flask anterior no se modifica; esta carpeta es independiente.
