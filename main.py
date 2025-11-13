import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import cv2
import numpy as np
import potrace # Necesitaremos instalar pypotrace
import io
import os

# --- Configuración de la App ---

app = FastAPI()

# Configurar CORS para permitir que tu HTML (desde cualquier dominio)
# se comunique con este backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permite todos los orígenes
    allow_credentials=True,
    allow_methods=["*"], # Permite todos los métodos (POST, GET, etc.)
    allow_headers=["*"], # Permite todas las cabeceras
)

# --- Funciones de Vectorización (La Magia) ---

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

def trace_multilayer_svg(posterized_image, palette_hex):
    """
    Toma la imagen posterizada y traza cada capa de color usando Potrace.
    Ensambla el resultado en un solo SVG.
    """
    svg_paths = []
    height, width, _ = posterized_image.shape

    # Iterar sobre cada color detectado
    for hex_color in palette_hex:
        # Convertir hex a BGR (formato de OpenCV)
        # El posterize_image nos da RGB, así que convertimos de RGB a BGR para cv2.inRange
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        bgr_color = (b, g, r) # Orden BGR para OpenCV
        
        # Crear una máscara en blanco y negro para el color actual
        # Usamos la imagen posterizada en formato BGR
        mask = cv2.inRange(posterized_image, bgr_color, bgr_color)
        
        # Crear un objeto Bitmap de Potrace desde la máscara
        bmp = potrace.Bitmap(mask.astype(np.uint8))
        
        # Trazar el bitmap
        path = bmp.trace(turdsize=2, turnpolicy=potrace.TURNPOLICY_MINORITY, alphamax=1.0)
        
        # Convertir el trazado de potrace a una ruta SVG
        svg_path_data = []
        for curve in path.curves:
            svg_path_data.append(f"M {curve.start_point[0]},{curve.start_point[1]}")
            for segment in curve.segments:
                if segment.is_corner:
                    svg_path_data.append(f"L {segment.c[0]},{segment.c[1]} L {segment.end_point[0]},{segment.end_point[1]}")
                else:
                    svg_path_data.append(f"C {segment.c1[0]},{segment.c1[1]} {segment.c2[0]},{segment.c2[1]} {segment.end_point[0]},{segment.end_point[1]}")
            svg_path_data.append("Z")
            
        # Añadir la ruta SVG completa con su color
        if svg_path_data:
            svg_paths.append(f'<path fill="{hex_color}" d="{" ".join(svg_path_data)}" />')

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

# --- Ejecución del Servidor (para pruebas locales) ---

if __name__ == "__main__":
    # Esto te permite correr el servidor localmente con: python main.py
    # Render usará un comando diferente para producción.
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
