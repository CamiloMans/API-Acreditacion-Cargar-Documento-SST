# Instalación de Python 3.11

Este proyecto requiere **Python 3.11.0** para funcionar correctamente. Python 3.14 tiene problemas de compatibilidad con las dependencias.

## Opción 1: Instalar Python 3.11 desde python.org (Recomendado)

1. Ve a https://www.python.org/downloads/release/python-3110/
2. Descarga "Windows installer (64-bit)"
3. Ejecuta el instalador
4. **IMPORTANTE**: Marca la opción "Add Python 3.11 to PATH"
5. Completa la instalación

## Opción 2: Instalar usando winget (Windows 10/11)

```powershell
winget install Python.Python.3.11
```

## Después de instalar Python 3.11

1. Cierra y vuelve a abrir tu terminal
2. Verifica la instalación:
   ```powershell
   py -3.11 --version
   ```
   Debería mostrar: `Python 3.11.0`

3. Elimina el entorno virtual actual:
   ```powershell
   Remove-Item -Recurse -Force .venv
   ```

4. Crea un nuevo entorno virtual con Python 3.11:
   ```powershell
   py -3.11 -m venv .venv
   ```

5. Activa el entorno virtual:
   ```powershell
   .venv\Scripts\activate
   ```

6. Instala las dependencias:
   ```powershell
   pip install -r requirements.txt
   ```

7. Ejecuta la aplicación:
   ```powershell
   uvicorn app.main:app --reload
   ```

## Verificar que todo funciona

```powershell
python --version  # Debería mostrar Python 3.11.0
pip list  # Debería mostrar todas las dependencias instaladas
```

