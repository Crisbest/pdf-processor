from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import uuid
import json
from datetime import datetime

app = FastAPI(title="PDF Processor API", version="1.0")

# CORS per permettere richieste dal frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In produzione, sostituire con URL specifico
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simuliamo una "database" in memoria
processes_db = {}

@app.get("/")
async def root():
    return {
        "message": "✅ PDF Processor API is running!",
        "version": "1.0",
        "endpoints": {
            "health": "/health",
            "upload": "POST /upload",
            "status": "GET /status/{id}",
            "info": "GET /info"
        }
    }

@app.get("/health")
async def health_check():
    """Endpoint per verificare che il server sia online"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "pdf-processor-backend"
    }

@app.get("/info")
async def get_info():
    """Informazioni sul server"""
    return {
        "service": "PDF Processor Backend",
        "description": "Processa PDF: traduce PL→IT e rimuove prezzi",
        "status": "operational",
        "processes_count": len(processes_db)
    }

@app.post("/upload")
async def upload_pdf(
    pdf: UploadFile = File(..., description="Il file PDF da processare"),
    config: str = None
):
    """
    Riceve un PDF e restituisce un ID processo.
    In questa versione demo, simula il processamento.
    """
    try:
        # Genera ID univoco per questo processo
        process_id = str(uuid.uuid4())
        
        # Leggi il file (solo per dimostrazione)
        contents = await pdf.read()
        file_size_kb = len(contents) / 1024
        
        # Configurazione
        config_dict = json.loads(config) if config else {
            "translate": True,
            "remove_prices": True,
            "remove_header": True,
            "remove_ref": True
        }
        
        # Simula statistiche di processamento
        import random
        stats = {
            "original_filename": pdf.filename,
            "file_size_kb": round(file_size_kb, 2),
            "pages": random.randint(1, 20),
            "translations_applied": random.randint(5, 25),
            "prices_removed": random.randint(3, 15),
            "processing_time_seconds": random.uniform(1.5, 4.0),
            "status": "completed",
            "config_used": config_dict
        }
        
        # Salva nel "database"
        processes_db[process_id] = {
            "id": process_id,
            "created_at": datetime.now().isoformat(),
            "status": "completed",
            "stats": stats,
            "download_available": False,  # In demo, non creiamo file reali
            "message": "PDF elaborato con successo (demo mode)"
        }
        
        return JSONResponse({
            "success": True,
            "process_id": process_id,
            "message": "PDF ricevuto. Processamento simulato in modalità demo.",
            "stats": stats,
            "note": "Questa è una versione demo. In produzione, qui verrebbe creato il PDF modificato.",
            "next_steps": [
                f"Controlla stato: GET /status/{process_id}",
                "In produzione: qui verrebbe generato il download link"
            ]
        })
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore durante l'upload: {str(e)}"
        )

@app.get("/status/{process_id}")
async def get_process_status(process_id: str):
    """Restituisce lo stato di un processo specifico"""
    if process_id not in processes_db:
        raise HTTPException(
            status_code=404,
            detail=f"Processo {process_id} non trovato"
        )
    
    return JSONResponse(processes_db[process_id])

@app.get("/processes")
async def list_all_processes():
    """Lista tutti i processi"""
    return {
        "total": len(processes_db),
        "processes": [
            {
                "id": pid,
                "created_at": data["created_at"],
                "status": data["status"]
            }
            for pid, data in processes_db.items()
        ]
    }

@app.delete("/cleanup")
async def cleanup_all():
    """Pulisce tutti i processi (per testing)"""
    global processes_db
    count = len(processes_db)
    processes_db = {}
    return {
        "message": f"Puliti {count} processi",
        "remaining": 0
    }

# Avvio server
if __name__ == "__main__":
    import uvicorn
    
    # Porta: usa variabile d'ambiente o default 8000
    port = int(os.environ.get("PORT", 8000))
    
    print("=" * 50)
    print("🚀 PDF PROCESSOR BACKEND - DEMO VERSION")
    print(f"📡 Porta: {port}")
    print(f"🌐 Accesso: http://0.0.0.0:{port}")
    print("=" * 50)
    
    uvicorn.run(
        app,
        host="0.0.0.0",  # Importante per Railway
        port=port,
        log_level="info"
    )
