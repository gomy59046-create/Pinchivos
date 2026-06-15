import os
import time
import random  # <--- Requerido para la selección de IPs
import requests
from requests.exceptions import RequestException
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import StaleElementReferenceException
from concurrent.futures import ThreadPoolExecutor

def configurar_navegador():
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    
    # Entorno aislado para evitar conflictos de bloqueo de base de datos
    # Entorno aislado dinámico: detecta la carpeta actual donde vive este script
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    ruta_perfil_bot = os.path.join(directorio_actual, "Perfil_Bot")
    chrome_options.add_argument(f"user-data-dir={ruta_perfil_bot}")
    
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def descargar_un_pin(sesion, tarea):
    """Función asignada a cada hilo individual para descargar una imagen"""
    indice, url, carpeta_destino = tarea
    try:
        # Reutiliza la conexión de la sesión con un timeout estricto
        respuesta = sesion.get(url, stream=True, timeout=8)
        
        if respuesta.status_code == 200:
            nombre_archivo = url.split('/')[-1]
            ruta_completa = os.path.join(carpeta_destino, f"pin_{indice}_{nombre_archivo}")
            
            with open(ruta_completa, 'wb') as archivo:
                for bloque in respuesta.iter_content(1024):
                    archivo.write(bloque)
            print(f"[HILO-OK] Descargado: {nombre_archivo}")
        else:
            print(f"[HILO-ERROR] HTTP {respuesta.status_code} en URL: {url}")
            
    except RequestException:
        print(f"[HILO-TIMEOUT] Servidor lento o caído en URL: {url}")
    except Exception as e:
        print(f"[HILO-CRÍTICO] Fallo inesperado: {e}")

def extraer_pines(url_tablero, carpeta_destino, max_pines):
    if not os.path.exists(carpeta_destino):
        os.makedirs(carpeta_destino)

    driver = configurar_navegador()
    driver.get("https://www.pinterest.com/login/")
    
    print("TIENES 60 SEGUNDOS. Asegura la sesión en la ventana automatizada...")
    time.sleep(60)
    
    driver.get(url_tablero)
    time.sleep(5)

    enlaces_imagenes = set()
    altura_anterior = driver.execute_script("return document.body.scrollHeight")
    intentos_sin_crecer = 0

    print("Iniciando escaneo dinámico del DOM...")
    
    while True:
        imagenes = driver.find_elements(By.TAG_NAME, 'img')
        
        for img in imagenes:
            try:
                src = img.get_attribute('src')
                if src and 'pinimg.com' in src:
                    # Sanitización e Ingeniería Inversa de URLs para evadir WebP y 403
                    url_alta = src.replace('236x', 'originals').replace('474x', 'originals').replace('736x', 'originals')
                    if 'webp' in url_alta:
                        url_alta = url_alta.replace('/webp80/', '/').replace('/webp/', '/')
                        url_alta = url_alta.replace('.webp', '.jpg')
                    
                    enlaces_imagenes.add(url_alta)
            except StaleElementReferenceException:
                continue
            except Exception:
                continue

        print(f"-> Telemetría: {len(enlaces_imagenes)} URLs únicas almacenadas en búfer.")

        if len(enlaces_imagenes) >= max_pines:
            print(f"-> Umbral objetivo alcanzado ({max_pines}). Cerrando navegador.")
            break

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2.5)
        
        nueva_altura = driver.execute_script("return document.body.scrollHeight")
        if nueva_altura == altura_anterior:
            intentos_sin_crecer += 1
            if intentos_sin_crecer >= 3:
                print("-> Fin de página verificado por el sistema.")
                break
        else:
            intentos_sin_crecer = 0
            
        altura_anterior = nueva_altura

    driver.quit()
    
    # --- MOTOR DE DESCARGA DE ALTO RENDIMIENTO ---
    lista_tareas = [(i, url, carpeta_destino) for i, url in enumerate(enlaces_imagenes)]
    
    print(f"\nIniciando descarga masiva concurrente de {len(lista_tareas)} elementos...")
    tiempo_inicio = time.time()

    # Inicializamos la Sesión HTTP Persistente
    with requests.Session() as sesion:
        sesion.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.pinterest.com/"
        })

        # Levantamos el Pool de Hilos Concurrentes. Ajustamos a 20 trabajadores simultáneos.
        with ThreadPoolExecutor(max_workers=20) as ejecutor:
            # map ejecuta la función 'descargar_un_pin' pasándole la sesión y la lista de tareas
            ejecutor.map(lambda tarea: descargar_un_pin(sesion, tarea), lista_tareas)

    tiempo_total = time.time() - tiempo_inicio
    print(f"\n[VICTORIA REAL] Proceso finalizado en {tiempo_total:.2f} segundos. Revisa '{carpeta_destino}'.")

if __name__ == "__main__":
    URL_TABLERO = "https://www.pinterest.com/ideas/architecture/924971520124/"
    CARPETA_LOCAL = "pines_descargados"
    LIMITE = 200 
    
    extraer_pines(URL_TABLERO, CARPETA_LOCAL, LIMITE)
