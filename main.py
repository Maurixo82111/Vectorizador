import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import cv2
import numpy as np
import io
import os
import subprocess
import tempfile
from PIL import Image

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def posterize_image(image, num_colors):
    """
    Reduce la imagen al número de colores especificado usando K-Means en OpenCV.
    Devuelve la imagen posterizada y la paleta de colores detectada.
    """
    # Convertir la imagen a un formato que OpenCV K-Means pueda usar
    pixels = np.float32(image.reshape(-1, 3))
    
    # Definir criterios y aplicar K-Means
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centers = cv2.kmeans(pixels, num_colors, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
    
    # Convertir los centros (colores) a 8-bit
    centers = np.uint8(centers)
    
    # Mapear los píxeles a los colores del centro
    posterized_data = centers[labels.flatten()]
    
    # Reformar la imagen a sus dimensiones originales
    posterized_image = posterized_data.reshape(image.shape)
    
    # Convertir la paleta a una lista de hex
    palette_hex = []
    for color in centers:
        # OpenCV usa RGB, así que el orden es R, G, B
        palette_hex.append(f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}")
        
    return posterized_image, palette_hex

def trace_with_potrace(mask, color_hex):
    """Usa potrace como binario del sistema para trazar"""
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_png:
        with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as temp_svg:
            try:
                # Guardar máscara como PNG (invertir colores para potrace)
                # Potrace espera negro sobre blanco, así que invertimos si es necesario
                mask_inverted = 255 - mask if np.mean(mask) > 127 else mask
                Image.fromarray(mask_inverted).save(temp_png.name)
                
                # Ejecutar potrace como comando del sistema
                subprocess.run([
                    'potrace', 
                    temp_png.name, 
                    '--svg', 
                    '--output', temp_svg.name,
                    '--turdsize', '2',
                    '--alphamax', '1.0',
                    '--opttolerance', '0.2'
                ], check=True, capture_output=True)
                
                # Leer el SVG resultante
                with open(temp_svg.name, 'r') as f:
                    svg_content = f.read()
                
                # Extraer solo el path del SVG y aplicar el color
                start = svg_content.find('<path')
                end = svg_content.find('</svg>')
                if start != -1 and end != -1:
                    path_content = svg_content[start:end]
                    # Reemplazar el color (potrace genera fill="#000000" por defecto)
                    path_content = path_content.replace('fill="#000000"', f'fill="{color_hex}"')
                    path_content = path_content.replace('fill="black"', f'fill="{color_hex}"')
                    path_content = path_content.replace('stroke="black"', f'stroke="{color_hex}"')
                    return path_content
                
            except subprocess.CalledProcessError as e:
                print(f"Error ejecutando potrace: {e}")
                print(f"stdout: {e.stdout}")
                print(f"stderr: {e.stderr}")
                return ""
            finally:
                # Limpiar archivos temporales
                if os.path.exists(temp_png.name):
                    os.unlink(temp_png.name)
                if os.path.exists(temp_svg.name):
                    os.unlink(temp_svg.name)
    
    return ""

def trace_multilayer_svg(posterized_image, palette_hex):
    """
    Toma la imagen posterizada y traza cada capa de color usando Potrace del sistema.
    Ensambla el resultado en un solo SVG.
    """
    svg_paths = []
    height, width, _ = posterized_image.shape

    # Iterar sobre cada color detectado
    for hex_color in palette_hex:
        # Convertir hex a BGR (formato de OpenCV)
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        bgr_color = (b, g, r) # Orden BGR para OpenCV
        
        # Crear una máscara en blanco y negro para el color actual
        mask = cv2.inRange(posterized_image, bgr_color, bgr_color)
        
        # Solo procesar máscaras no vacías
        if np.any(mask):
            path_svg = trace_with_potrace(mask, hex_color)
            if path_svg:
                svg_paths.append(path_svg)

    # Ensamblar el SVG final
    svg_header = f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
    svg_footer = '</svg>'
    
    return svg_header + "\n" + "\n".join(svg_paths) + "\n" + svg_footer

# --- Endpoints de la API ---

@app.get("/")
def read_root():
    """ Endpoint de prueba para saber que el servidor está vivo. """
    return {"status": "Vectorizador Backend está en línea"}

@app.post("/vectorize/")
async def vectorize_image(
    num_colors: int = 8,
    image_file: UploadFile = File(...)
):
    """
    Endpoint principal. Recibe una imagen y un número de colores,
    devuelve un SVG vectorizado.
    """
    try:
        # Leer la imagen subida
        contents = await image_file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img_bgr is None:
            return JSONResponse(status_code=400, content={"error": "No se pudo decodificar la imagen"})

        # Convertir a RGB para el posterizado
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        # 1. Posterizar la imagen
        posterized_img_rgb, palette = posterize_image(img_rgb, num_colors)
        
        # Convertir de vuelta a BGR para el trazado (OpenCV usa BGR)
        posterized_img_bgr = cv2.cvtColor(posterized_img_rgb, cv2.COLOR_RGB2BGR)

        # 2. Trazar cada capa de color y ensamblar el SVG
        svg_result = trace_multilayer_svg(posterized_img_bgr, palette)
        
        # Devolver el SVG como texto plano
        return StreamingResponse(io.StringIO(svg_result), media_type="image/svg+xml")

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# --- Ejecución del Servidor ---

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
