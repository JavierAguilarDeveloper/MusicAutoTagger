# 🎵 Music Auto Tagger

Etiquetá tu biblioteca de música automáticamente usando solo los nombres de los archivos.

Apuntá la app a una carpeta y ella buscará el título, artista, álbum, año, género y portada de cada archivo — luego escribirá todos los tags directamente en los archivos de audio.

![demo](https://i.imgur.com/placeholder.png)

## ✨ Características

- Parsea nombres de archivo automáticamente — soporta formatos como `Artista - Título`, `01 - Título` o simplemente `Título`
- Limpieza inteligente: elimina sufijos de YouTube como `(Official Video)`, `(Audio)`, `(En Vivo)` antes de buscar
- Cascada de búsqueda en 3 fuentes: **iTunes Search API → Deezer API → MusicBrainz** (sin necesidad de API keys)
- Descarga y embebe portadas de álbum en **600×600**
- Soporta **MP3**, **FLAC**, **M4A** y **AAC**
- Progreso en tiempo real en el navegador con previsualizaciones de portadas
- Tabla de resultados completa al finalizar con filtros (todos / etiquetados / no encontrados)
- Compatible con macOS, Windows y Linux

## 📋 Requisitos

- Python 3.9+
- Conexión a internet (para consultar las APIs de metadata)

## 🚀 Inicio rápido

### macOS / Linux

```bash
git clone https://github.com/JavierAguilarDeveloper/MusicAutoTagger.git
cd MusicAutoTagger
./start.sh
```

### Windows

```
Doble clic en start.bat
```

Luego abrí el navegador en **http://localhost:8000**

El script de inicio crea un entorno virtual e instala las dependencias automáticamente en el primer arranque.

## ⚙️ ¿Cómo funciona?

1. Ingresá la ruta a tu carpeta de música (o usá el botón 📂 para explorar)
2. La app escanea los archivos de audio de forma recursiva
3. Por cada archivo limpia y parsea el nombre para extraer artista y título
4. Consulta en cascada: iTunes → Deezer → MusicBrainz
5. Descarga la portada del álbum
6. Escribe todos los tags en el archivo usando [mutagen](https://mutagen.readthedocs.io/)
7. Muestra un resumen completo con portadas al finalizar

## 🛠️ Stack tecnológico

- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) + [uvicorn](https://www.uvicorn.org/)
- **Tagging**: [mutagen](https://mutagen.readthedocs.io/)
- **Fuentes de metadata**: iTunes Search API · Deezer API · MusicBrainz
- **Frontend**: HTML/CSS/JS vanilla — sin build, sin dependencias

## 👨‍💻 Sobre el desarrollador

Hecho con 🎵 por **Javier Aguilar** — desarrollador Full Stack especializado en Angular y construcción de herramientas open source.

- 🌐 Portafolio: [javieraguilar.dev](https://javieraguilar.dev)
- 💼 GitHub: [@JavierAguilarDeveloper](https://github.com/JavierAguilarDeveloper)

## ☕ ¿Te resultó útil?

Si esta herramienta te ahorró tiempo y querés apoyar el proyecto, podés invitarme un café:

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-buymeacoffee.com%2Fjavieraguilar-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/javieraguilar)

¡Cualquier apoyo es muy apreciado y motiva a seguir construyendo herramientas open source! 🙌

## 📄 Licencia

MIT
