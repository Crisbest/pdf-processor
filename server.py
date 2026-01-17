from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import os
import uuid
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

app = FastAPI(title="PDF Processor API", version="1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directory
UPLOAD_FOLDER = Path("uploads")
PROCESSED_FOLDER = Path("processed")
UPLOAD_FOLDER.mkdir(exist_ok=True)
PROCESSED_FOLDER.mkdir(exist_ok=True)

# Cache processi
processes: Dict[str, Dict] = {}

# Endpoint base
@app.get("/")
async def root():
    return {
        "message": "PDF Processor API v1.0",
        "status": "online",
        "endpoints": ["/health", "/upload", "/status/{id}", "/download/{id}"]
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy", 
        "service": "pdf-processor",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/upload")
async def upload_pdf(
    pdf: UploadFile = File(...),
    config: Optional[str] = None
):
    """
    Endpoint per caricare e processare PDF
    """
    try:
        # Genera ID univoco
        process_id = str(uuid.uuid4())
        
        # Salva file originale
        input_path = UPLOAD_FOLDER / f"{process_id}_input.pdf"
        with open(input_path, "wb") as f:
            shutil.copyfileobj(pdf.file, f)
        
        # Simula elaborazione (per test)
        # In produzione qui andrebbe la vera logica di processamento
        output_path = PROCESSED_FOLDER / f"{process_id}_output.pdf"
        
        # Per ora copiamo il file (simulazione)
        shutil.copy(input_path, output_path)
        
        # Calcola statistiche (simulate)
        import random
        stats = {
            "pages": random.randint(1, 10),
            "translations": random.randint(5, 20),
            "prices_removed": random.randint(3, 15),
            "processing_time": 2.5,
            "file_size_kb": os.path.getsize(output_path) / 1024
        }
        
        # Salva info processo
        processes[process_id] = {
            "id": process_id,
            "status": "completed",
            "message": "PDF elaborato con successo",
            "progress": 100,
            "original_filename": pdf.filename,
            "input_size": os.path.getsize(input_path),
            "output_file": str(output_path),
            "download_url": f"/download/{process_id}",
            "created_at": datetime.now().isoformat(),
            "stats": stats
        }
        
        return JSONResponse({
            "process_id": process_id,
            "status": "completed",
            "message": "PDF caricato e processato",
            "download_url": f"/download/{process_id}",
            "stats": stats
        })
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Errore durante l'elaborazione: {str(e)}"
        )

@app.get("/status/{process_id}")
async def get_status(process_id: str):
    """Ottieni stato di un processo"""
    if process_id not in processes:
        raise HTTPException(status_code=404, detail="Processo non trovato")
    
    return JSONResponse(processes[process_id])

@app.get("/download/{process_id}")
async def download_pdf(process_id: str):
    """Scarica PDF processato"""
    if process_id not in processes:
        raise HTTPException(status_code=404, detail="Processo non trovato")
    
    process = processes[process_id]
    output_file = process.get("output_file")
    
    if not output_file or not os.path.exists(output_file):
        raise HTTPException(status_code=404, detail="File non trovato")
    
    filename = f"MODIFICATO_{process['original_filename']}"
    return FileResponse(
        path=output_file,
        filename=filename,
        media_type='application/pdf'
    )

@app.get("/processes")
async def list_processes():
    """Lista tutti i processi"""
    return {
        "count": len(processes),
        "processes": list(processes.keys())
    }

@app.delete("/cleanup/{process_id}")
async def cleanup_process(process_id: str):
    """Pulisci file di un processo"""
    if process_id in processes:
        process = processes[process_id]
        
        # Rimuovi file
        for file_key in ["input_file", "output_file"]:
            if file_key in process:
                file_path = process[file_key]
                if os.path.exists(file_path):
                    os.remove(file_path)
        
        # Rimuovi dalla cache
        del processes[process_id]
        
        return {"message": f"Processo {process_id} rimosso"}
    
    raise HTTPException(status_code=404, detail="Processo non trovato")

# Server startup
if __name__ == "__main__":
    import uvicorn
    
    # Ottieni porta da variabile d'ambiente (Railway usa PORT)
    port = int(os.environ.get("PORT", 8000))
    
    print(f"🚀 Starting PDF Processor API on port {port}")
    print(f"📁 Upload folder: {UPLOAD_FOLDER.absolute()}")
    print(f"📁 Processed folder: {PROCESSED_FOLDER.absolute()}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",  # Importante per Railway
        port=port,
        log_level="info"
    )
